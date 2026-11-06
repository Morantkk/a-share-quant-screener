# -*- coding: utf-8 -*-
"""条件选股引擎：固定指标积木块组合筛选（无自然语言，口径确定）"""
import numpy as np
import pandas as pd

from . import indicators as ind
from . import cache


# ---------------- 条件类型定义（前端动态渲染表单） ----------------
CONDITION_TYPES = [
    {
        "type": "ma_cross", "label": "均线交叉",
        "params": [
            {"key": "fast", "label": "快线", "type": "number", "default": 5,
             "options": [5, 10, 20, 30, 60]},
            {"key": "slow", "label": "慢线", "type": "number", "default": 20,
             "options": [5, 10, 20, 30, 60]},
            {"key": "direction", "label": "方向", "type": "select", "default": "golden",
             "options": ["golden:金叉", "dead:死叉"]},
            {"key": "within", "label": "近几日内发生", "type": "number", "default": 5},
        ],
    },
    {
        "type": "ma_position", "label": "股价与均线位置",
        "params": [
            {"key": "ma", "label": "均线", "type": "number", "default": 20,
             "options": [5, 10, 20, 30, 60]},
            {"key": "relation", "label": "关系", "type": "select", "default": "above",
             "options": ["above:收盘价在均线上方", "below:收盘价在均线下方"]},
        ],
    },
    {
        "type": "ma_trend", "label": "均线排列",
        "params": [
            {"key": "relation", "label": "形态", "type": "select", "default": "bull",
             "options": ["bull:多头排列(MA5>MA10>MA20)", "bear:空头排列(MA5<MA10<MA20)"]},
        ],
    },
    {
        "type": "macd_cross", "label": "MACD金叉死叉",
        "params": [
            {"key": "direction", "label": "方向", "type": "select", "default": "golden",
             "options": ["golden:DIF上穿DEA(金叉)", "dead:DIF下穿DEA(死叉)"]},
            {"key": "within", "label": "近几日内发生", "type": "number", "default": 5},
        ],
    },
    {
        "type": "macd_state", "label": "MACD状态",
        "params": [
            {"key": "state", "label": "状态", "type": "select", "default": "dif_above_zero",
             "options": ["dif_above_zero:DIF在零轴上方", "dif_below_zero:DIF在零轴下方",
                          "bar_rising:红柱放大/绿柱缩小", "bar_falling:红柱缩小/绿柱放大"]},
        ],
    },
    {
        "type": "kdj_cross", "label": "KDJ金叉死叉",
        "params": [
            {"key": "direction", "label": "方向", "type": "select", "default": "golden",
             "options": ["golden:K上穿D(金叉)", "dead:K下穿D(死叉)"]},
            {"key": "within", "label": "近几日内发生", "type": "number", "default": 5},
        ],
    },
    {
        "type": "kdj_state", "label": "KDJ状态",
        "params": [
            {"key": "state", "label": "状态", "type": "select", "default": "k_above_d",
             "options": ["k_above_d:K在D上方", "k_below_d:K在D下方",
                          "overbought:超买(K>80)", "oversold:超卖(K<20)"]},
        ],
    },
    {
        "type": "rsi_range", "label": "RSI区间",
        "params": [
            {"key": "period", "label": "周期", "type": "number", "default": 14,
             "options": [6, 14, 24]},
            {"key": "min", "label": "最小值(可空)", "type": "number", "default": None},
            {"key": "max", "label": "最大值(可空)", "type": "number", "default": None},
        ],
    },
    {
        "type": "boll_state", "label": "布林带",
        "params": [
            {"key": "state", "label": "状态", "type": "select", "default": "break_upper",
             "options": ["break_upper:突破上轨", "break_lower:跌破下轨",
                          "above_mid:收盘在中轨上方", "below_mid:收盘在中轨下方"]},
            {"key": "within", "label": "近几日内(仅突破类)", "type": "number", "default": 3},
        ],
    },
    {
        "type": "volume_ratio", "label": "量比(今量/前5日均量)",
        "params": [
            {"key": "min", "label": "最小", "type": "number", "default": 2.0},
            {"key": "max", "label": "最大(可空)", "type": "number", "default": None},
        ],
    },
    {
        "type": "turnover", "label": "换手率%",
        "params": [
            {"key": "min", "label": "最小", "type": "number", "default": 5},
            {"key": "max", "label": "最大(可空)", "type": "number", "default": 10},
        ],
    },
    {
        "type": "consecutive_volume", "label": "连续放量/缩量",
        "params": [
            {"key": "days", "label": "连续天数", "type": "number", "default": 3},
            {"key": "kind", "label": "类型", "type": "select", "default": "up",
             "options": ["up:放量(量>前5日均量x1.2)", "down:缩量(量<前5日均量x0.8)"]},
        ],
    },
    {
        "type": "breakout", "label": "突破平台",
        "params": [
            {"key": "days", "label": "平台天数", "type": "number", "default": 20},
        ],
    },
    {
        "type": "pullback_ma", "label": "回踩均线",
        "params": [
            {"key": "ma", "label": "均线", "type": "number", "default": 20,
             "options": [5, 10, 20, 30, 60]},
            {"key": "tolerance", "label": "触及容差%", "type": "number", "default": 2},
        ],
    },
    {
        "type": "pct_chg", "label": "涨跌幅%",
        "params": [
            {"key": "days", "label": "天数(0=今日,N=近N日累计)", "type": "number", "default": 0},
            {"key": "min", "label": "最小", "type": "number", "default": None},
            {"key": "max", "label": "最大(可空)", "type": "number", "default": None},
        ],
    },
    {
        "type": "price_range", "label": "股价区间",
        "params": [
            {"key": "min", "label": "最低价", "type": "number", "default": None},
            {"key": "max", "label": "最高价(可空)", "type": "number", "default": None},
        ],
    },
    {
        "type": "new_extreme", "label": "创N日新高/新低",
        "params": [
            {"key": "days", "label": "N日", "type": "number", "default": 60},
            {"key": "kind", "label": "类型", "type": "select", "default": "high",
             "options": ["high:新高", "low:新低"]},
        ],
    },
]

TYPES_INDEX = {t["type"]: t for t in CONDITION_TYPES}


def describe(cond):
    """条件的可读描述，用于条件卡展示"""
    t = TYPES_INDEX.get(cond.get("type"))
    if not t:
        return str(cond)
    p = cond.get("params", {})
    if t["type"] == "ma_cross":
        d = "上穿" if p.get("direction") == "golden" else "下穿"
        return f"MA({p.get('fast', 5)}) {d} MA({p.get('slow', 20)})，近{p.get('within', 5)}日内"
    if t["type"] == "ma_position":
        r = "上方" if p.get("relation") == "above" else "下方"
        return f"收盘价在 MA({p.get('ma', 20)}) {r}"
    if t["type"] == "ma_trend":
        return "多头排列(MA5>MA10>MA20)" if p.get("relation") == "bull" else "空头排列(MA5<MA10<MA20)"
    if t["type"] == "macd_cross":
        d = "金叉" if p.get("direction") == "golden" else "死叉"
        return f"MACD {d}，近{p.get('within', 5)}日内"
    if t["type"] == "macd_state":
        m = {"dif_above_zero": "DIF在零轴上方", "dif_below_zero": "DIF在零轴下方",
             "bar_rising": "红柱放大/绿柱缩小", "bar_falling": "红柱缩小/绿柱放大"}
        return "MACD " + m.get(p.get("state"), "")
    if t["type"] == "kdj_cross":
        d = "金叉" if p.get("direction") == "golden" else "死叉"
        return f"KDJ {d}，近{p.get('within', 5)}日内"
    if t["type"] == "kdj_state":
        m = {"k_above_d": "K在D上方", "k_below_d": "K在D下方", "overbought": "超买(K>80)", "oversold": "超卖(K<20)"}
        return "KDJ " + m.get(p.get("state"), "")
    if t["type"] == "rsi_range":
        lo, hi = p.get("min"), p.get("max")
        rng = f"{lo if lo is not None else '-∞'} ~ {hi if hi is not None else '+∞'}"
        return f"RSI({p.get('period', 14)}) 在 {rng}"
    if t["type"] == "boll_state":
        m = {"break_upper": "突破上轨", "break_lower": "跌破下轨", "above_mid": "中轨上方", "below_mid": "中轨下方"}
        return "布林带" + m.get(p.get("state"), "")
    if t["type"] == "volume_ratio":
        lo, hi = p.get("min"), p.get("max")
        rng = f"{lo if lo is not None else '-∞'} ~ {hi if hi is not None else '+∞'}"
        return f"今日量比 {rng}"
    if t["type"] == "turnover":
        lo, hi = p.get("min"), p.get("max")
        rng = f"{lo if lo is not None else '-∞'} ~ {hi if hi is not None else '+∞'}"
        return f"今日换手率 {rng}%"
    if t["type"] == "consecutive_volume":
        k = "放量" if p.get("kind") == "up" else "缩量"
        return f"连续{p.get('days', 3)}日{k}"
    if t["type"] == "breakout":
        return f"收盘突破近{p.get('days', 20)}日高点"
    if t["type"] == "pullback_ma":
        return f"回踩MA({p.get('ma', 20)})±{p.get('tolerance', 2)}%且收在上方"
    if t["type"] == "pct_chg":
        n = p.get("days", 0)
        lo, hi = p.get("min"), p.get("max")
        rng = f"{lo if lo is not None else '-∞'} ~ {hi if hi is not None else '+∞'}"
        return ("今日" if n == 0 else f"近{n}日累计") + f"涨跌幅 {rng}%"
    if t["type"] == "price_range":
        lo, hi = p.get("min"), p.get("max")
        rng = f"{lo if lo is not None else '-∞'} ~ {hi if hi is not None else '+∞'}"
        return f"收盘价 {rng} 元"
    if t["type"] == "new_extreme":
        k = "新高" if p.get("kind") == "high" else "新低"
        return f"创{p.get('days', 60)}日{k}"
    return t["label"]


# ---------------- 条件求值 ----------------
def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _eval(b: ind.Bundle, cond):
    t = cond.get("type")
    p = cond.get("params", {})
    df = b.df
    n = len(df)
    if n < 5:
        return False

    if t == "ma_cross":
        f = int(p.get("fast", 5)); s = int(p.get("slow", 20))
        if f >= s or n < s + 1:
            return False
        fa, sa = b.ma[f], b.ma[s]
        w = int(p.get("within", 5))
        return b.crossed_up(fa, sa, w) if p.get("direction", "golden") == "golden" \
            else b.crossed_down(fa, sa, w)

    if t == "ma_position":
        m = int(p.get("ma", 20))
        if n < m:
            return False
        c, mv = b.last(b.close), b.last(b.ma[m])
        if c is None or mv is None:
            return False
        return (c > mv) if p.get("relation", "above") == "above" else (c < mv)

    if t == "ma_trend":
        if n < 21:
            return False
        m5, m10, m20 = b.last(b.ma[5]), b.last(b.ma[10]), b.last(b.ma[20])
        if None in (m5, m10, m20):
            return False
        return (m5 > m10 > m20) if p.get("relation", "bull") == "bull" else (m5 < m10 < m20)

    if t == "macd_cross":
        w = int(p.get("within", 5))
        return b.crossed_up(b.dif, b.dea, w) if p.get("direction", "golden") == "golden" \
            else b.crossed_down(b.dif, b.dea, w)

    if t == "macd_state":
        st = p.get("state", "dif_above_zero")
        if st == "dif_above_zero":
            return (b.last(b.dif) or 0) > 0
        if st == "dif_below_zero":
            return (b.last(b.dif) or 0) < 0
        b1, b2 = b.last(b.bar), b.last(b.bar, 1)
        if b1 is None or b2 is None:
            return False
        if st == "bar_rising":
            return abs(b1) > abs(b2) if b1 > 0 else b1 > b2
        return abs(b1) < abs(b2) if b1 > 0 else b1 < b2

    if t == "kdj_cross":
        w = int(p.get("within", 5))
        return b.crossed_up(b.k, b.d, w) if p.get("direction", "golden") == "golden" \
            else b.crossed_down(b.k, b.d, w)

    if t == "kdj_state":
        st = p.get("state", "k_above_d")
        k, d = b.last(b.k), b.last(b.d)
        if st == "k_above_d":
            return k is not None and d is not None and k > d
        if st == "k_below_d":
            return k is not None and d is not None and k < d
        if st == "overbought":
            return k is not None and k > 80
        return k is not None and k < 20

    if t == "rsi_range":
        per = int(p.get("period", 14))
        v = b.last(b.rsi[per])
        if v is None:
            return False
        lo, hi = _num(p.get("min")), _num(p.get("max"))
        return (lo is None or v >= lo) and (hi is None or v <= hi)

    if t == "boll_state":
        st = p.get("state", "break_upper")
        if st in ("above_mid", "below_mid"):
            c, mid = b.last(b.close), b.last(b.boll_mid)
            if c is None or mid is None:
                return False
            return c > mid if st == "above_mid" else c < mid
        w = int(p.get("within", 3))
        if st == "break_upper":
            return b.crossed_up(b.close, b.boll_up, w)
        return b.crossed_down(b.close, b.boll_low, w)

    if t == "volume_ratio":
        if n < 7:
            return False
        v_today = b.last(b.volume)
        vm = b.last(b.vol_ma5, 1)  # 前5日均量（不含今日）
        if v_today is None or not vm:
            return False
        vr = v_today / vm
        lo, hi = _num(p.get("min")), _num(p.get("max"))
        return (lo is None or vr >= lo) and (hi is None or vr <= hi)

    if t == "turnover":
        v = b.last(df["turnover"])
        if v is None:
            return False
        lo, hi = _num(p.get("min")), _num(p.get("max"))
        return (lo is None or v >= lo) and (hi is None or v <= hi)

    if t == "consecutive_volume":
        days = int(p.get("days", 3))
        if n < days + 6:
            return False
        vols = b.volume
        for i in range(days):
            idx = n - 1 - i
            v = vols.iloc[idx]
            vm = vols.iloc[max(0, idx - 5):idx].mean()
            if pd.isna(v) or pd.isna(vm) or vm == 0:
                return False
            if p.get("kind", "up") == "up":
                if v <= vm * 1.2:
                    return False
            else:
                if v >= vm * 0.8:
                    return False
        return True

    if t == "breakout":
        d = int(p.get("days", 20))
        if n < d + 2:
            return False
        closes = b.close
        c = closes.iloc[-1]
        prev_high = b.df["high"].iloc[-d - 1:-1].max()
        prev_close = closes.iloc[-2]
        return prev_high == prev_high and c > prev_high and prev_close <= prev_high

    if t == "pullback_ma":
        m = int(p.get("ma", 20))
        tol = float(p.get("tolerance", 2))
        if n < m + 1:
            return False
        c, lo, mv = b.last(b.close), b.last(df["low"]), b.last(b.ma[m])
        if None in (c, lo, mv) or mv == 0:
            return False
        return abs(lo - mv) / mv * 100 <= tol and c > mv

    if t == "pct_chg":
        d = int(p.get("days", 0))
        if d == 0:
            v = b.last(df["pct_chg"])
        else:
            if n < d + 1:
                return False
            c0 = b.close.iloc[-1 - d]
            c1 = b.close.iloc[-1]
            if not c0:
                return False
            v = (c1 / c0 - 1) * 100
        if v is None:
            return False
        lo, hi = _num(p.get("min")), _num(p.get("max"))
        return (lo is None or v >= lo) and (hi is None or v <= hi)

    if t == "price_range":
        c = b.last(b.close)
        if c is None:
            return False
        lo, hi = _num(p.get("min")), _num(p.get("max"))
        return (lo is None or c >= lo) and (hi is None or c <= hi)

    if t == "new_extreme":
        d = int(p.get("days", 60))
        if n < d + 1:
            return False
        if p.get("kind", "high") == "high":
            window = df["high"].iloc[-d - 1:-1]
            return df["high"].iloc[-1] >= window.max()
        window = df["low"].iloc[-d - 1:-1]
        return df["low"].iloc[-1] <= window.min()

    return False


def run(conditions, logic="and", exclude_st=True, limit=200):
    """执行筛选，返回命中列表"""
    if not conditions:
        return {"ok": False, "msg": "未添加任何条件"}
    frames, names = cache.load()
    results = []
    for code, df in frames.items():
        if exclude_st:
            nm = names.get(code, "")
            if "ST" in nm.upper() or "退" in nm:
                continue
        if len(df) < 30:
            continue
        try:
            b = ind.bundle(df, code)
            checks = [_eval(b, c) for c in conditions]
            if logic == "or":
                hit = any(checks)
            else:
                hit = all(checks)
            if not hit:
                continue
            vm = b.last(b.vol_ma5, 1)
            vr = round(b.last(b.volume) / vm, 2) if vm else None
            results.append({
                "code": code,
                "name": names.get(code, ""),
                "close": b.last(b.close),
                "pct_chg": b.last(df["pct_chg"]),
                "turnover": b.last(df["turnover"]),
                "volume_ratio": vr,
                "date": df["date"].iloc[-1],
            })
        except Exception:
            continue
    results.sort(key=lambda r: (r["pct_chg"] if r["pct_chg"] is not None else -99), reverse=True)
    total = len(results)
    return {"ok": True, "total": total, "results": results[:limit]}
