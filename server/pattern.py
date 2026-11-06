# -*- coding: utf-8 -*-
"""K线形态匹配：DTW + 相关系数（含截图识别辅助）"""
import numpy as np

from . import cache
from . import indicators as ind


def _zscore(a):
    a = np.asarray(a, dtype=float)
    s = a.std()
    if s < 1e-12:
        return a - a.mean()
    return (a - a.mean()) / s


def _pct(a):
    a = np.asarray(a, dtype=float)
    return np.diff(a) / (np.abs(a[:-1]) + 1e-12)


def _corr(a, b):
    if len(a) < 3:
        return 0.0
    za, zb = _zscore(a), _zscore(b)
    denom = (np.sqrt((za ** 2).sum()) * np.sqrt((zb ** 2).sum()))
    if denom < 1e-12:
        return 0.0
    return float((za * zb).sum() / denom)


def _dtw(a, b, window=None):
    """带约束窗口的 DTW 距离（容忍时间轴伸缩）"""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0.0
    if window is None:
        window = max(abs(n - m) + 2, max(n, m) // 3)
    INF = 1e18
    cost = np.full((n + 1, m + 1), INF)
    cost[0, 0] = 0.0
    for i in range(1, n + 1):
        j0, j1 = max(1, i - window), min(m, i + window)
        for j in range(j0, j1 + 1):
            c = abs(a[i - 1] - b[j - 1])
            cost[i, j] = c + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    return float(cost[n, m])


def _score(tpl_close, seg_close, tpl_vol=None, seg_vol=None, match_volume=False):
    """综合相似度 0~1：形状相关 + 涨跌节奏 + DTW（可选量能）"""
    tpl_close = np.asarray(tpl_close, dtype=float)
    seg_close = np.asarray(seg_close, dtype=float)
    if len(tpl_close) < 4 or len(seg_close) < 4:
        return 0.0
    shape = max(0.0, _corr(_zscore(tpl_close), _zscore(seg_close)))
    rhythm = max(0.0, _corr(_pct(tpl_close), _pct(seg_close)))
    d = _dtw(_zscore(tpl_close), _zscore(seg_close)) / max(len(tpl_close), len(seg_close))
    dtw_sim = max(0.0, 1.0 - d / 2.0)
    s = 0.45 * shape + 0.30 * rhythm + 0.25 * dtw_sim
    if match_volume and tpl_vol is not None and seg_vol is not None:
        v_sim = max(0.0, _corr(_zscore(tpl_vol), _zscore(seg_vol)))
        s = 0.85 * s + 0.15 * v_sim
    return float(min(1.0, max(0.0, s)))


def match(template_close, template_vol=None, match_volume=False, top=50,
          scan_windows=False, exclude_code="", exclude_st=True):
    """
    template_close: 模板收盘价序列（按时间升序）
    scan_windows: False=只比各股"最近一段"；True=在各股半年内滑动找最佳窗口
    """
    tpl_close = np.asarray(template_close, dtype=float)
    L = len(tpl_close)
    if L < 5:
        return {"ok": False, "msg": "模板太短（至少5根K线）"}
    if L > 60:
        return {"ok": False, "msg": "模板太长（最多60根K线）"}
    tpl_vol = np.asarray(template_vol, dtype=float) if (match_volume and template_vol is not None) else None

    frames, names = cache.load()
    hits = []
    for code, df in frames.items():
        if code == exclude_code or len(df) < max(L + 1, 30):
            continue
        if exclude_st:
            nm = names.get(code, "")
            if "ST" in nm.upper() or "退" in nm:
                continue
        closes = df["close"].values
        vols = df["volume"].values if match_volume else None

        candidates = []
        if scan_windows:
            step = 1
            for start in range(0, len(closes) - L + 1, step):
                candidates.append((start, start + L))
        else:
            candidates.append((len(closes) - L, len(closes)))

        best = None
        for s, e in candidates:
            seg = closes[s:e]
            sv = vols[s:e] if vols is not None else None
            tv = tpl_vol if vols is not None else None
            sc = _score(tpl_close, seg, tv, sv, match_volume)
            if best is None or sc > best[0]:
                best = (sc, s, e, seg)
        if best is None:
            continue
        sc, s, e, seg = best
        if sc < 0.3:
            continue
        hits.append({
            "code": code,
            "name": names.get(code, ""),
            "score": round(sc * 100, 1),
            "seg_start": df["date"].iloc[s],
            "seg_end": df["date"].iloc[e - 1],
            "is_recent": (e == len(closes)),
            "seg_close": [round(float(x), 3) for x in seg],
            "seg_dates": [str(x) for x in df["date"].iloc[s:e]],
            "last_close": float(closes[-1]),
            "last_pct": float(df["pct_chg"].iloc[-1]) if df["pct_chg"].iloc[-1] == df["pct_chg"].iloc[-1] else None,
        })
    hits.sort(key=lambda h: h["score"], reverse=True)
    out = hits[:top]
    for i, h in enumerate(out):
        h["rank"] = i + 1
    return {"ok": True, "total": len(hits), "results": out}


# ---------------- 截图识别（辅助，精度有限） ----------------
def extract_from_image(path):
    """
    从K线截图中粗略提取收盘价走势：
    按列扫描红/绿蜡烛像素 → 每根蜡烛取实体端点 → 还原相对走势序列。
    仅适用于清晰的普通K线截图（红涨绿跌）。
    """
    from PIL import Image

    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w < 50 or h < 50:
        return {"ok": False, "msg": "图片太小"}
    px = img.load()
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            arr[y, x, 0] = r; arr[y, x, 1] = g; arr[y, x, 2] = b

    r_ch, g_ch, b_ch = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    red_mask = (r_ch > 130) & (r_ch - g_ch > 40) & (r_ch - b_ch > 40)
    green_mask = (g_ch > 100) & (g_ch - r_ch > 30) & (g_ch - b_ch > 10)
    mask = red_mask | green_mask
    col_has = mask.any(axis=0)
    if col_has.sum() < 20:
        return {"ok": False, "msg": "未检测到红/绿K线（请确认是红涨绿跌配色、清晰的K线截图）"}

    # 把相邻有颜色的列聚成蜡烛
    groups = []
    in_g = False
    for x in range(w):
        if col_has[x] and not in_g:
            start = x; in_g = True
        elif not col_has[x] and in_g:
            groups.append((start, x - 1)); in_g = False
    if in_g:
        groups.append((start, w - 1))
    # 过滤太窄的噪声组（比如网格线）
    groups = [g for g in groups if g[1] - g[0] >= 1]
    if len(groups) < 5:
        return {"ok": False, "msg": f"仅识别到 {len(groups)} 根K线，数量不足"}

    # 均衡蜡烛宽度（剔除明显偏宽的组，如坐标轴区域）
    widths = [g[1] - g[0] + 1 for g in groups]
    med_w = float(np.median(widths))
    groups = [g for g, wd in zip(groups, widths) if wd <= med_w * 2.5]

    closes = []
    for (x0, x1) in groups:
        sub_red = red_mask[:, x0:x1 + 1]
        sub_green = green_mask[:, x0:x1 + 1]
        n_red, n_green = int(sub_red.sum()), int(sub_green.sum())
        if n_red + n_green < 4:
            continue
        m = sub_red if n_red >= n_green else sub_green
        ys = np.where(m.any(axis=1))[0]
        if len(ys) == 0:
            continue
        top, bottom = int(ys.min()), int(ys.max())
        # 红K：实体上端=开盘，下端=收盘；绿K相反（y 越大价格越低）
        if n_red >= n_green:
            close_y = bottom
        else:
            close_y = top
        closes.append((close_y, n_red >= n_green))

    if len(closes) < 5:
        return {"ok": False, "msg": "识别到的K线数量不足（截图可能不清晰）"}

    # y 坐标转相对价格（仅保留形态，无量纲）
    raw = np.array([c[0] for c in closes], dtype=float)
    price = (raw.max() - raw)  # 翻转：y小=价格高
    if price.std() < 1e-9:
        return {"ok": False, "msg": "未能提取有效走势"}
    norm = (price - price.min()) / (price.max() - price.min() + 1e-9) * 100 + 1
    return {
        "ok": True,
        "series": [round(float(v), 2) for v in norm],
        "count": len(norm),
        "note": "截图识别为粗略走势（无量纲），精度有限，建议到「行情」页用框选获取精确模板",
    }
