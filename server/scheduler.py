# -*- coding: utf-8 -*-
"""每日定时调度：行情增量更新 / 热榜抓取 / 日历刷新（后台线程）"""
import threading
import time
import traceback
from datetime import datetime

from . import database as db
from .config import CONFIG

_started = False
_lock = threading.Lock()


def _parse_hm(s):
    try:
        h, m = s.strip().split(":")
        return int(h), int(m)
    except Exception:
        return None, None


def _already_done_today(key):
    st = db.get_state(key) or {}
    done = st.get("last_done_date", "")
    return done == datetime.now().strftime("%Y-%m-%d")


def _mark_done(key):
    st = db.get_state(key) or {}
    st["last_done_date"] = datetime.now().strftime("%Y-%m-%d")
    st["last_done_at"] = db.now_str()
    db.set_state(key, st)


def _run_quotes():
    from . import fetcher
    fetcher.fetch_all("incremental")


def _run_news():
    from . import news
    news.refresh()


def _run_calendar():
    from . import calendar_module
    calendar_module.refresh()


JOBS = {
    "quotes": _run_quotes,
    "news": _run_news,
    "calendar": _run_calendar,
}


def _loop():
    while True:
        try:
            now = datetime.now()
            if now.weekday() < 6:  # 周日不执行任何任务
                for key, func in JOBS.items():
                    cfg_key = {"quotes": "quotes_time", "news": "news_time",
                               "calendar": "calendar_time"}[key]
                    h, m = _parse_hm(CONFIG.get(cfg_key, ""))
                    if h is None:
                        continue
                    if key == "quotes" and now.weekday() >= 5:
                        continue  # 行情更新仅工作日（周末无新数据）
                    due = (now.hour, now.minute) >= (h, m)
                    # news: 每个自然日一次; quotes/calendar: 工作日
                    if due and not _already_done_today(key):
                        t = threading.Thread(target=_safe_run, args=(key, func), daemon=True)
                        t.start()
                        _mark_done(key)
        except Exception:
            traceback.print_exc()
        time.sleep(30)


def _safe_run(key, func):
    try:
        func()
    except Exception:
        traceback.print_exc()


def start():
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, daemon=True, name="scheduler").start()


def run_job(key):
    """手动触发某个任务"""
    func = JOBS.get(key)
    if not func:
        return {"ok": False, "msg": "未知任务"}
    if key == "quotes":
        from . import fetcher
        if (fetcher.status() or {}).get("running"):
            return {"ok": False, "msg": "行情抓取正在进行中"}
        threading.Thread(target=_safe_run, args=(key, func), daemon=True).start()
        return {"ok": True, "msg": "已启动行情增量更新"}
    threading.Thread(target=_safe_run, args=(key, func), daemon=True).start()
    return {"ok": True, "msg": "已启动"}
