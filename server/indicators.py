# -*- coding: utf-8 -*-
"""技术指标计算：输入单只股票的日K DataFrame（按日期升序），输出指标数组包"""
import numpy as np
import pandas as pd


def _ema(series, n):
    return series.ewm(span=n, adjust=False).mean()


def ma(series, n):
    return series.rolling(n).mean()


def macd(close, fast=12, slow=26, signal=9):
    dif = _ema(close, fast) - _ema(close, slow)
    dea = _ema(dif, signal)
    bar = (dif - dea) * 2
    return dif, dea, bar


def kdj(df, n=9, m1=3, m2=3):
    low_n = df["low"].rolling(n, min_periods=1).min()
    high_n = df["high"].rolling(n, min_periods=1).max()
    rsv = (df["close"] - low_n) / (high_n - low_n + 1e-12) * 100
    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def rsi(close, n=14):
    diff = close.diff()
    up = diff.clip(lower=0)
    down = (-diff).clip(lower=0)
    avg_up = up.ewm(alpha=1 / n, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / n, adjust=False).mean()
    return 100 * avg_up / (avg_up + avg_down + 1e-12)


def boll(close, n=20, k=2):
    mid = close.rolling(n).mean()
    std = close.rolling(n).std()
    return mid, mid + k * std, mid - k * std


class Bundle:
    """一只股票的全部指标序列（pandas Series，与 df 等长，尾部即最新）"""

    def __init__(self, df):
        self.df = df
        c = df["close"]
        v = df["volume"]
        self.close = c
        self.volume = v
        self.ma = {n: ma(c, n) for n in (5, 10, 20, 30, 60)}
        self.dif, self.dea, self.bar = macd(c)
        self.k, self.d, self.j = kdj(df)
        self.rsi = {n: rsi(c, n) for n in (6, 14, 24)}
        self.boll_mid, self.boll_up, self.boll_low = boll(c)
        self.vol_ma5 = v.rolling(5).mean()      # 含当日的5日均量
        self.pct = df["pct_chg"]

    # 便捷取尾部值
    def last(self, series, offset=0):
        """series 尾部第 offset 个值（0=最新交易日），NaN 返回 None"""
        if series is None or len(series) <= offset:
            return None
        v = series.iloc[len(series) - 1 - offset]
        return None if pd.isna(v) else float(v)

    def crossed_up(self, a, b, within=5):
        """a 在最近 within 日内上穿 b"""
        if a is None or b is None or len(a) < 2:
            return False
        n = min(within, len(a) - 1)
        for i in range(len(a) - n, len(a)):
            if pd.isna(a.iloc[i]) or pd.isna(b.iloc[i]) or pd.isna(b.iloc[i - 1]) or pd.isna(a.iloc[i - 1]):
                continue
            if a.iloc[i - 1] <= b.iloc[i - 1] and a.iloc[i] > b.iloc[i]:
                return True
        return False

    def crossed_down(self, a, b, within=5):
        if a is None or b is None or len(a) < 2:
            return False
        n = min(within, len(a) - 1)
        for i in range(len(a) - n, len(a)):
            if pd.isna(a.iloc[i]) or pd.isna(b.iloc[i]) or pd.isna(b.iloc[i - 1]) or pd.isna(a.iloc[i - 1]):
                continue
            if a.iloc[i - 1] >= b.iloc[i - 1] and a.iloc[i] < b.iloc[i]:
                return True
        return False


_bundles = {}


def bundle(df, code=""):
    """带简单缓存的 Bundle 构建（key=code，DataFrame 长度变化即失效）"""
    if code and code in _bundles and _bundles[code][0] == len(df):
        return _bundles[code][1]
    b = Bundle(df)
    if code:
        if len(_bundles) > 6000:
            _bundles.clear()
        _bundles[code] = (len(df), b)
    return b


def clear_bundles():
    _bundles.clear()
