# -*- coding: utf-8 -*-
"""合成数据离线测试：验证 筛选/匹配/指标 引擎逻辑（不依赖网络）"""
import os, sys, random, math, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QUANT_DB_PATH"] = os.path.join(tempfile.gettempdir(), "quant_synth_test.db")
if os.path.exists(os.environ["QUANT_DB_PATH"]):
    os.remove(os.environ["QUANT_DB_PATH"])

import numpy as np
from datetime import datetime, timedelta
from server import database as db, cache
from server.screener import run as screen_run, describe
from server.pattern import match

random.seed(42)
np.random.seed(42)

db.init_db()

N_STOCKS = 80
N_DAYS = 140
# 生成交易日期（工作日，倒推）
base = datetime(2026, 8, 26)
dates = []
d = base
while len(dates) < N_DAYS:
    if d.weekday() < 5:
        dates.append(d.strftime("%Y-%m-%d"))
    d -= timedelta(days=1)
dates = dates[::-1]

stocks = []
frames = []
for i in range(N_STOCKS):
    code = f"{600000 + i:06d}"
    name = f"测试股{i:02d}"
    stocks.append((code, name, "SH" if code.startswith("6") else "SZ", 0, db.now_str()))
    price = 10 + random.uniform(-3, 40)
    rows = []
    vols = []
    # 随机游走生成收盘价
    closes = [price]
    for t in range(1, N_DAYS):
        drift = random.uniform(-0.02, 0.022)
        price = max(1.0, price * (1 + drift))
        closes.append(price)
    closes = np.array(closes)
    # 成交量：基础量 + 噪声
    base_vol = random.uniform(1e6, 5e6)
    vols = [base_vol * (1 + random.uniform(-0.3, 0.3)) for _ in range(N_DAYS)]
    for t in range(N_DAYS):
        c = closes[t]
        o = c * (1 + random.uniform(-0.01, 0.01))
        hi = max(o, c) * (1 + random.uniform(0, 0.02))
        lo = min(o, c) * (1 - random.uniform(0, 0.02))
        v = vols[t]
        amount = v * c
        prev = closes[t - 1] if t > 0 else c
        pct = (c / prev - 1) * 100 if t > 0 else 0
        amp = (hi / lo - 1) * 100 if lo else 0
        turnover = v / (base_vol * 30) * 100  # 伪换手率
        rows.append((code, dates[t], round(o,2), round(hi,2), round(lo,2), round(c,2),
                     round(v,0), round(amount,0), round(turnover,2), round(pct,2), round(amp,2)))
    frames.extend(rows)

# 植入 3 只"先跌后涨、近期MA5金叉MA20 + 末端放量"的确定性形态
def inject(idx, frames):
    code = f"{600000 + idx:06d}"
    idxs = [frames.index(r) for r in frames if r[0] == code]
    # 仅改写最后 60 天
    tail = idxs[-60:]
    base_p = frames[tail[0]][5]   # 起点收盘价
    n = len(tail)
    for j, fi in enumerate(tail):
        r = frames[fi]
        if j < 45:
            # 前段缓跌：P*1.0 -> P*0.80
            c = base_p * (1.0 - 0.20 * j / 44)
        else:
            # 后段急涨：P*0.80 -> P*1.06，制造金叉
            c = base_p * (0.80 + 0.26 * (j - 45) / 14)
        vol_mult = 3.5 if j == n - 1 else 1.0   # 仅最后一天放量，确保量比>2
        frames[fi] = (r[0], r[1], round(c*0.99,2), round(c*1.01,2),
                      round(c*0.98,2), round(c,2),
                      round(r[6]*vol_mult,0), round(r[6]*vol_mult*c,0),
                      round(r[8]*vol_mult,2), r[9], r[10])

for idx in [10, 25, 60]:
    inject(idx, frames)

db.executemany(
    "INSERT INTO stocks(code,name,market,is_st,updated_at) VALUES(?,?,?,?,?)", stocks)
db.executemany(
    "INSERT INTO daily(code,date,open,high,low,close,volume,amount,turnover,pct_chg,amplitude) "
    "VALUES(?,?,?,?,?,?,?,?,?,?,?)", frames)

print(f"[合成] 生成 {N_STOCKS} 只 × {N_DAYS} 天，共 {len(frames)} 行")

# ---- 筛选：MA5上穿MA20 且 量比>2 ----
cache.invalidate()
cond = [
    {"type": "ma_cross", "params": {"fast": 5, "slow": 20, "direction": "golden", "within": 15}},
    {"type": "volume_ratio", "params": {"min": 2.0, "max": None}},
]
res = screen_run(cond, logic="and", limit=50)
print(f"\n[筛选] MA5金叉MA20 且 量比>2 → 命中 {res['total']} 只")
for x in res["results"][:10]:
    print(f"  {x['code']} {x['name']} 收盘{x['close']} 量比{x['volume_ratio']} 涨幅{x['pct_chg']}%")
hit_codes = {x["code"] for x in res["results"]}
print("  植入的10/25/60是否命中:", [c for c in ["600010","600025","600060"] if c in hit_codes])

# ---- 形态匹配：取10号股最近15日作模板 ----
def get_series(code, n=15):
    rows = db.query(f"SELECT close, volume FROM daily WHERE code=? ORDER BY date DESC LIMIT {n}", (code,))
    rows = list(reversed(rows))
    if len(rows) < n: return None
    return (np.array([r["close"] for r in rows], float), np.array([r["volume"] for r in rows], float))

ser = get_series("600010", 15)
if ser is not None:
    mres = match(ser[0], ser[1], match_volume=True, top=10)
    hits = mres["results"] if mres.get("ok") else []
    print(f"\n[匹配] 模板600010，top5:", [(h["code"], round(h["score"],3)) for h in hits[:5]])
    # 600010 自身应排名靠前
    print("  600010 是否在结果中:", any(h["code"] == "600010" for h in hits))
else:
    print("[匹配] 模板数据不足")

print("\n引擎离线测试完成。")
