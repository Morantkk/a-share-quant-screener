# -*- coding: utf-8 -*-
"""小批量全链路实测：抓取 -> 筛选 -> 形态匹配"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import database as db, fetcher
from server.screener import run as screen_run
from server import indicators as ind

db.init_db()

# ---- 1) 小批量抓取（20 只，控制并发，避免东财限流）----
ak = fetcher._ak()
from datetime import datetime, timedelta
start = (datetime.now() - timedelta(days=140)).strftime("%Y%m%d")
end = datetime.now().strftime("%Y%m%d")

codes = [r["code"] for r in db.query("SELECT code FROM stocks WHERE is_st=0 LIMIT 20")]
t0 = time.time()
ok = 0
for c in codes:
    try:
        df = fetcher._fetch_one(ak, c, start, end)
        fetcher._save_daily(c, df)
        ok += 1
    except Exception as e:
        print("失败", c, type(e).__name__, str(e)[:60])
print(f"[抓取] 20只耗时 {time.time()-t0:.1f}s, 成功{ok}")
r = db.query_one("SELECT COUNT(*) c, MIN(date) mn, MAX(date) mx FROM daily")
print("[DB] daily:", r)

# ---- 2) 指标筛选：MA5 上穿 MA20 且 量比>2 ----
print("\n[筛选] MA5上穿MA20 且 量比>2 ...")
cond = [
    {"type": "ma_cross", "params": {"fast": 5, "slow": 20, "direction": "golden", "within": 5}},
    {"type": "volume_ratio", "params": {"min": 2.0, "max": None}},
]
res = screen_run(cond, logic="and", limit=30)
if res.get("ok"):
    print(f"  命中 {res['total']} 只:", [f"{x['code']} {x['name']}" for x in res["results"][:10]])
else:
    print("  筛选失败:", res)

# ---- 3) 形态匹配：用其中一只的近期K线当模板，去其他股票找相似 ----
print("\n[形态匹配] 取第一只最近15日作为模板 ...")
import numpy as np
def get_series(code, n=15):
    rows = db.query(f"SELECT close, volume, date FROM daily WHERE code=? ORDER BY date DESC LIMIT {n}", (code,))
    rows = list(reversed(rows))
    if len(rows) < n:
        return None
    close = np.array([r["close"] for r in rows], float)
    vol = np.array([r["volume"] for r in rows], float)
    return close, vol

tmpl_code = codes[0]
ser = get_series(tmpl_code, 15)
from server.pattern import match
if ser is not None:
    hits = match(ser[0], ser[1], match_volume=True, top=10)
    print(f"  模板 {tmpl_code}，匹配前5:", [(h["code"], round(h["score"],3)) for h in hits[:5]])
else:
    print("  模板数据不足，跳过")

print("\n全链路测试完成。")
