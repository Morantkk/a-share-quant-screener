# -*- coding: utf-8 -*-
"""内存数据缓存：全市场日K一次性载入，供筛选/匹配共用"""
import threading

import pandas as pd

from . import database as db

_lock = threading.Lock()
_cache = {"key": None, "frames": None, "names": None}


def _key():
    row = db.query_one("SELECT MAX(date) AS d, COUNT(*) AS c FROM daily")
    return (row["d"], row["c"]) if row else None


def load(force=False):
    """返回 (frames: {code: DataFrame}, names: {code: name})"""
    with _lock:
        k = _key()
        if not force and _cache["frames"] is not None and _cache["key"] == k:
            return _cache["frames"], _cache["names"]
        rows = db.query(
            "SELECT code, date, open, high, low, close, volume, amount, "
            "turnover, pct_chg, amplitude FROM daily ORDER BY code, date")
        frames = {}
        if rows:
            df = pd.DataFrame(rows)
            num_cols = ["open", "high", "low", "close", "volume", "amount", "turnover", "pct_chg", "amplitude"]
            for c in num_cols:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            for code, g in df.groupby("code"):
                g = g.reset_index(drop=True)
                frames[code] = g
        names = {r["code"]: r["name"] for r in db.query("SELECT code, name FROM stocks")}
        _cache["key"] = k
        _cache["frames"] = frames
        _cache["names"] = names
        return frames, names


def invalidate():
    with _lock:
        _cache["frames"] = None
        _cache["names"] = None
