# -*- coding: utf-8 -*-
"""FastAPI 主入口：全部 API + 静态前端"""
import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List

from . import auth
from . import calendar_module
from . import database as db
from . import fetcher
from . import news
from . import pattern
from . import scheduler
from . import screener
from .config import BASE_DIR, CONFIG

app = FastAPI(title="量化选股系统")

WEB_DIR = os.path.join(BASE_DIR, "web")


def _reset_stale_fetch_state():
    """进程重启后，上次未跑完的抓取会残留 running=True，
    导致界面一直显示"抓取中"却毫无进度。启动时统一复位。"""
    st = db.get_state("fetch")
    if isinstance(st, dict) and st.get("running"):
        st["running"] = False
        st["phase"] = "已中断"
        st["message"] = "上次抓取未正常结束（进程退出），已自动复位"
        st["finished_at"] = st.get("finished_at") or db.now_str()
        db.set_state("fetch", st)


@app.on_event("startup")
def startup():
    db.init_db()
    _reset_stale_fetch_state()
    scheduler.start()


# ---------------- 鉴权 ----------------
class LoginBody(BaseModel):
    password: str


@app.post("/api/login")
def api_login(body: LoginBody):
    t = auth.login(body.password)
    if not t:
        return JSONResponse({"ok": False, "msg": "密码错误"}, status_code=401)
    return {"ok": True, "token": t}


@app.get("/api/ping")
def api_ping():
    return {"ok": True}


@app.post("/api/logout")
def api_logout(request: Request, token=Depends(auth.verify)):
    auth.logout(token)
    return {"ok": True}


# ---------------- 股票与行情 ----------------
@app.get("/api/search")
def api_search(q: str = "", limit: int = 20, _=Depends(auth.verify)):
    q = (q or "").strip()
    if not q:
        return {"ok": True, "results": []}
    rows = db.query(
        "SELECT code, name, is_st FROM stocks WHERE code LIKE ? OR name LIKE ? LIMIT ?",
        (q + "%", "%" + q + "%", limit))
    return {"ok": True, "results": rows}


@app.get("/api/kline")
def api_kline(code: str, days: int = 120, _=Depends(auth.verify)):
    rows = db.query(
        "SELECT date, open, high, low, close, volume, amount, turnover, pct_chg, amplitude "
        "FROM daily WHERE code=? ORDER BY date DESC LIMIT ?", (code, days))
    rows.reverse()
    stock = db.query_one("SELECT code, name, is_st FROM stocks WHERE code=?", (code,))
    return {"ok": True, "stock": stock, "bars": rows}


# ---------------- 数据抓取 ----------------
@app.post("/api/fetch/start")
def api_fetch_start(mode: str = "incremental", _=Depends(auth.verify)):
    from . import fetcher as f
    st = f.status()
    if st.get("running"):
        return {"ok": False, "msg": "已有抓取任务在运行"}
    import threading
    threading.Thread(target=f.fetch_all, args=(mode,), daemon=True).start()
    return {"ok": True, "msg": "已启动"}


@app.get("/api/fetch/status")
def api_fetch_status(_=Depends(auth.verify)):
    return {"ok": True, **fetcher.status()}


# ---------------- 条件选股 ----------------
@app.get("/api/screen/types")
def api_screen_types(_=Depends(auth.verify)):
    return {"ok": True, "types": screener.CONDITION_TYPES}


class ScreenBody(BaseModel):
    conditions: List[dict]
    logic: str = "and"
    exclude_st: bool = True
    limit: int = 200


@app.post("/api/screen")
def api_screen(body: ScreenBody, _=Depends(auth.verify)):
    out = screener.run(body.conditions, body.logic, body.exclude_st, body.limit)
    for c in body.conditions:
        c["desc"] = screener.describe(c)
    out["conditions"] = body.conditions
    out["logic"] = body.logic
    return out


# ---------------- 策略保存 ----------------
class StrategyBody(BaseModel):
    name: str
    logic: str = "and"
    conditions: List[dict]


@app.get("/api/strategies")
def api_strategies(_=Depends(auth.verify)):
    rows = db.query("SELECT * FROM strategies ORDER BY id DESC")
    for r in rows:
        try:
            import json
            r["conditions"] = json.loads(r["conditions"])
        except Exception:
            r["conditions"] = []
    return {"ok": True, "results": rows}


@app.post("/api/strategies")
def api_save_strategy(body: StrategyBody, _=Depends(auth.verify)):
    import json
    db.execute(
        "INSERT INTO strategies(name, logic, conditions, created_at) VALUES(?,?,?,?)",
        (body.name, body.logic, json.dumps(body.conditions, ensure_ascii=False), db.now_str()))
    return {"ok": True}


@app.delete("/api/strategies/{sid}")
def api_del_strategy(sid: int, _=Depends(auth.verify)):
    db.execute("DELETE FROM strategies WHERE id=?", (sid,))
    return {"ok": True}


# ---------------- 形态匹配 ----------------
class PatternBody(BaseModel):
    template_close: List[float]
    template_vol: Optional[List[float]] = None
    match_volume: bool = False
    top: int = 50
    scan_windows: bool = False
    exclude_code: str = ""
    exclude_st: bool = True


@app.post("/api/pattern/match")
def api_pattern_match(body: PatternBody, _=Depends(auth.verify)):
    out = pattern.match(
        body.template_close, body.template_vol, body.match_volume,
        body.top, body.scan_windows, body.exclude_code, body.exclude_st)
    return out


@app.post("/api/pattern/upload")
async def api_pattern_upload(request: Request, _=Depends(auth.verify)):
    import tempfile
    form = await request.form()
    up = form.get("file")
    if up is None:
        return {"ok": False, "msg": "未收到文件"}
    suffix = os.path.splitext(up.filename or "")[1] or ".png"
    tmp = os.path.join(tempfile.gettempdir(), f"kl_{next(_counter)}.{suffix}")
    with open(tmp, "wb") as f:
        f.write(await up.read())
    return pattern.extract_from_image(tmp)


def _gen_counter():
    i = 0
    while True:
        i += 1
        yield i


_counter = _gen_counter()


# ---------------- 财经日历 ----------------
@app.get("/api/calendar")
def api_calendar(start: str, end: str, region: str = "", importance: int = 0,
                 _=Depends(auth.verify)):
    rows = calendar_module.get_events(start, end, region or None,
                                      importance if importance > 0 else None)
    return {"ok": True, "results": rows}


@app.post("/api/calendar/refresh")
def api_calendar_refresh(_=Depends(auth.verify)):
    n = calendar_module.refresh()
    return {"ok": True, "msg": f"已生成 {n} 条日程"}


class EventBody(BaseModel):
    date: str
    title: str
    region: str = "CN"
    importance: int = 2
    time: str = ""
    note: str = ""


@app.post("/api/calendar/event")
def api_add_event(body: EventBody, _=Depends(auth.verify)):
    calendar_module.add_manual(body.date, body.title, body.region,
                               body.importance, body.time, body.note)
    return {"ok": True}


@app.delete("/api/calendar/event/{eid}")
def api_del_event(eid: int, _=Depends(auth.verify)):
    calendar_module.delete_event(eid)
    return {"ok": True}


# ---------------- 新闻热榜 ----------------
@app.get("/api/news/hotlist")
def api_hotlist(day: str = "", category: str = "全部", _=Depends(auth.verify)):
    rows = news.hotlist(day or None, category)
    return {"ok": True, "results": rows, "status": news.status()}


@app.post("/api/news/refresh")
def api_news_refresh(_=Depends(auth.verify)):
    return news.refresh()


# ---------------- 自选池 ----------------
@app.get("/api/watchlist")
def api_watchlist(_=Depends(auth.verify)):
    rows = db.query("SELECT * FROM watchlist ORDER BY added_at DESC")
    for r in rows:
        last = db.query_one(
            "SELECT close, pct_chg, turnover, date FROM daily WHERE code=? ORDER BY date DESC LIMIT 1",
            (r["code"],))
        if last:
            r.update(last)
    return {"ok": True, "results": rows}


class WatchBody(BaseModel):
    code: str
    name: str = ""


@app.post("/api/watchlist")
def api_watch_add(body: WatchBody, _=Depends(auth.verify)):
    db.execute(
        "INSERT OR IGNORE INTO watchlist(code, name, added_at) VALUES(?,?,?)",
        (body.code, body.name, db.now_str()))
    return {"ok": True}


@app.delete("/api/watchlist/{code}")
def api_watch_del(code: str, _=Depends(auth.verify)):
    db.execute("DELETE FROM watchlist WHERE code=?", (code,))
    return {"ok": True}


# ---------------- 系统 ----------------
@app.get("/api/system/stats")
def api_stats(_=Depends(auth.verify)):
    stocks = db.query_one("SELECT COUNT(*) AS c FROM stocks")
    daily = db.query_one("SELECT COUNT(*) AS c, MAX(date) AS d FROM daily")
    news_state = db.get_state("news") or {}
    cal = db.query_one("SELECT COUNT(*) AS c FROM calendar_events WHERE date>=date('now')")
    fetch = db.get_state("fetch") or {}
    return {
        "ok": True,
        "stock_count": stocks["c"] if stocks else 0,
        "daily_count": daily["c"] if daily else 0,
        "last_date": daily["d"] if daily else "",
        "news_last": news_state.get("last_refresh", ""),
        "calendar_today": cal["c"] if cal else 0,
        "fetch": fetch,
        "config": {k: v for k, v in CONFIG.items() if k != "password"},
    }


@app.post("/api/jobs/{key}")
def api_run_job(key: str, _=Depends(auth.verify)):
    return scheduler.run_job(key)


# ---------------- 静态前端 ----------------
if os.path.exists(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))
