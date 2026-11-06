# -*- coding: utf-8 -*-
"""多线程 A 股日 K 数据抓取（数据源：akshare / 东方财富，免费）"""
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from . import database as db
from . import akshare_compat  # noqa: F401  注入UA，必须在akshare使用前导入
from .config import CONFIG

_fetch_lock = threading.Lock()
_running = False


def _ak():
    import akshare as ak
    return ak


def refresh_stock_list(force=False):
    """刷新全 A 股股票列表（含名称、是否 ST）。
    force=False 且本地已有时效内数据时直接返回，避免东财限流时挂起。"""
    existing = db.query_one("SELECT COUNT(*) c, MAX(updated_at) AS u FROM stocks")
    has = existing and existing["c"] and existing["c"] > 0
    if not force and has:
        # 7 天内已刷新过则跳过
        last = existing.get("u") or ""
        if last and (db.now_str()[:10] <= last[:10]):
            return existing["c"]
        from datetime import datetime as _dt
        try:
            if (_dt.now() - _dt.strptime(last[:19], "%Y-%m-%d %H:%M:%S")).days < 7:
                return existing["c"]
        except Exception:
            pass
    ak = _ak()
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        if has:
            return existing["c"]  # 刷新失败但已有数据，兜底返回
        raise
    rows = []
    ts = db.now_str()
    for _, r in df.iterrows():
        code = str(r["代码"]).zfill(6)
        name = str(r["名称"])
        rows.append((
            code, name,
            "SH" if code.startswith("6") else ("BJ" if code.startswith(("4", "8")) else "SZ"),
            1 if "ST" in name.upper() else 0,
            ts,
        ))
    db.executemany(
        "INSERT INTO stocks(code, name, market, is_st, updated_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name, market=excluded.market, "
        "is_st=excluded.is_st, updated_at=excluded.updated_at",
        rows,
    )
    return len(rows)


def _progress(**kw):
    state = db.get_state("fetch") or {}
    state.update(kw)
    db.set_state("fetch", state)
    return state


def _fetch_eastmoney(ak, code, start_date, end_date):
    """东方财富日 K（字段全）。内部使用 py_mini_racer，需全局锁串行"""
    from .akshare_compat import AKSHARE_LOCK
    with AKSHARE_LOCK:
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start_date, end_date=end_date, adjust="qfq",
        )
    if df is None or df.empty or "日期" not in df.columns:
        return None
    return df


def _sina_symbol(code):
    return ("sh" if code.startswith("6") else "sz") + code


def _fetch_sina(ak, code, start_date, end_date):
    """新浪日 K（兜底源）"""
    try:
        df = ak.stock_zh_a_daily(
            symbol=_sina_symbol(code),
            start_date=start_date, end_date=end_date, adjust="qfq",
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    # 统一列名（新浪返回：date,open,high,low,close,volume,amount/turnover/outstanding_share）
    df = df.rename(columns={
        "date": "日期", "open": "开盘", "high": "最高", "low": "最低",
        "close": "收盘", "volume": "成交量",
        "amount": "成交额", "turnover": "换手率",
    })
    if "成交额" not in df.columns:
        df["成交额"] = float("nan")
    if "换手率" not in df.columns:
        df["换手率"] = float("nan")
    if "振幅" not in df.columns and {"最高", "最低"}.issubset(df.columns):
        hi, lo = df["最高"].astype(float), df["最低"].astype(float)
        prev = lo.shift(1)
        df["振幅"] = ((hi / prev - 1) * 100).fillna(0)
    if "涨跌幅" not in df.columns and {"收盘"}.issubset(df.columns):
        close = df["收盘"].astype(float)
        df["涨跌幅"] = (close / close.shift(1) - 1) * 100
        df["涨跌幅"] = df["涨跌幅"].fillna(0)
    return df


def _fetch_one(ak, code, start_date, end_date, retries=3, use_eastmoney=True):
    """抓取单只股票日 K（东财优先，新浪兜底，失败指数退避）。返回 DataFrame 或 None"""
    last_err = None
    for i in range(retries):
        # 1) 主源：东方财富
        if use_eastmoney:
            try:
                df = _fetch_eastmoney(ak, code, start_date, end_date)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                last_err = e
        # 2) 兜底源：新浪
        try:
            df = _fetch_sina(ak, code, start_date, end_date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
        # 退避：0.5s, 1s, 2s + 抖动
        time.sleep(min(0.5 * (2 ** i), 3) + random.random())
    if last_err:
        raise last_err
    return None


def _save_daily(code, df):
    """把单只股票的日 K 写入数据库"""
    if df is None or df.empty:
        return 0
    rows = []
    for _, r in df.iterrows():
        d = str(r["日期"])[:10]
        def num(v):
            try:
                f = float(v)
                return None if f != f else f  # NaN 判断
            except (TypeError, ValueError):
                return None
        rows.append((
            code, d, num(r.get("开盘")), num(r.get("最高")), num(r.get("最低")),
            num(r.get("收盘")), num(r.get("成交量")), num(r.get("成交额")),
            num(r.get("换手率")), num(r.get("涨跌幅")), num(r.get("振幅")),
        ))
    db.executemany(
        "INSERT INTO daily(code, date, open, high, low, close, volume, amount, "
        "turnover, pct_chg, amplitude) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(code, date) DO UPDATE SET open=excluded.open, high=excluded.high, "
        "low=excluded.low, close=excluded.close, volume=excluded.volume, "
        "amount=excluded.amount, turnover=excluded.turnover, pct_chg=excluded.pct_chg, "
        "amplitude=excluded.amplitude",
        rows,
    )
    return len(rows)


def _trim_old(code, keep_from):
    db.execute("DELETE FROM daily WHERE code=? AND date<?", (code, keep_from))


def fetch_all(mode="incremental"):
    """全市场抓取。mode: incremental=增量补抓, full=清空重抓"""
    global _running
    with _fetch_lock:
        if _running:
            return {"ok": False, "msg": "已有抓取任务在运行"}
        _running = True
    try:
        return _fetch_all_impl(mode)
    finally:
        _running = False


def _fetch_all_impl(mode):
    ak = _ak()
    threads = int(CONFIG.get("fetch_threads", 12))
    hist_days = int(CONFIG.get("history_days", 140))
    today = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=hist_days)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")
    keep_from = (datetime.now() - timedelta(days=hist_days)).strftime("%Y-%m-%d")

    _progress(running=True, phase="刷新股票列表", total=0, done=0, failed=0,
              started_at=db.now_str(), finished_at="", message="", mode=mode)
    try:
        n_stocks = refresh_stock_list()
    except Exception as e:
        _progress(running=False, phase="失败", message=f"获取股票列表失败: {e}",
                  finished_at=db.now_str())
        return {"ok": False, "msg": f"获取股票列表失败: {e}"}

    stocks = db.query("SELECT code FROM stocks")
    codes = [s["code"] for s in stocks]
    if mode == "full":
        db.execute("DELETE FROM daily")
    # 已有最新日期的股票：增量模式下从次日开始抓
    last_dates = {r["code"]: r["d"] for r in db.query(
        "SELECT code, MAX(date) AS d FROM daily GROUP BY code")}

    # ---- 数据源熔断探测：先测东方财富是否可用，被限流则整批直走新浪 ----
    use_em = bool(CONFIG.get("use_eastmoney", True))
    if use_em and codes:
        try:
            probe = _fetch_eastmoney(ak, codes[0], start, end)
            if probe is None or probe.empty:
                use_em = False
                _progress(message="东方财富暂不可用（疑似限流），本次改用新浪源")
        except Exception:
            use_em = False
            _progress(message="东方财富探测失败，本次改用新浪源")

    _progress(running=True, phase="抓取日K数据", total=len(codes), done=0, failed=0,
              message=f"数据源：{'东方财富' if use_em else '新浪'}", mode=mode)

    done = [0]
    failed = [0]
    failed_codes = []
    lock = threading.Lock()

    def work(code):
        nonlocal failed_codes
        try:
            ld = last_dates.get(code)
            s = start
            if mode == "incremental" and ld and ld >= keep_from:
                nxt = (datetime.strptime(ld, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
                if nxt > end:  # 已是最新
                    return
                s = nxt
            df = _fetch_one(ak, code, s, end, use_eastmoney=use_em)
            _save_daily(code, df)
            if mode == "full":
                _trim_old(code, keep_from)
            elif ld and ld < keep_from:
                _trim_old(code, keep_from)
        except Exception:
            with lock:
                failed_codes.append(code)
                failed[0] += 1
        finally:
            with lock:
                done[0] += 1
                if done[0] % 20 == 0 or done[0] == len(codes):
                    _progress(done=done[0], failed=failed[0],
                              message=f"进度 {done[0]}/{len(codes)}，失败 {failed[0]}")

    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = [pool.submit(work, c) for c in codes]
        for _ in as_completed(futures):
            pass

    msg = f"完成：共 {len(codes)} 只，成功 {len(codes) - failed[0]}，失败 {failed[0]}（源：{'东方财富' if use_em else '新浪'}）"
    if failed_codes:
        db.set_state("fetch_failed_codes", failed_codes[:200])
    _progress(running=False, phase="完成", message=msg, finished_at=db.now_str())
    try:
        from .cache import invalidate
        invalidate()
    except Exception:
        pass
    return {"ok": True, "msg": msg}


def status():
    st = db.get_state("fetch") or {}
    total = db.query_one("SELECT COUNT(DISTINCT code) AS c FROM daily")
    last = db.query_one("SELECT MAX(date) AS d FROM daily")
    st["stock_count"] = total["c"] if total else 0
    st["last_date"] = last["d"] if last else ""
    return st
