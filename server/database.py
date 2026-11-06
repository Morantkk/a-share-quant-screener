# -*- coding: utf-8 -*-
"""SQLite 数据库层：建表、通用读写、抓取状态"""
import json
import os
import sqlite3
import threading
import time

from .config import DB_PATH

_local = threading.local()
_write_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    code TEXT PRIMARY KEY,
    name TEXT,
    market TEXT DEFAULT '',
    is_st INTEGER DEFAULT 0,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS daily (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL, turnover REAL, pct_chg REAL, amplitude REAL,
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_daily_code ON daily(code);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily(date);
CREATE TABLE IF NOT EXISTS watchlist (
    code TEXT PRIMARY KEY,
    name TEXT,
    added_at TEXT
);
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    logic TEXT,
    conditions TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    time TEXT DEFAULT '',
    region TEXT,
    title TEXT,
    importance INTEGER DEFAULT 2,
    prior TEXT DEFAULT '',
    forecast TEXT DEFAULT '',
    note TEXT DEFAULT '',
    source TEXT DEFAULT 'auto',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    published_at TEXT,
    title TEXT,
    content TEXT,
    source TEXT,
    url TEXT DEFAULT '',
    category TEXT DEFAULT '快讯',
    score REAL DEFAULT 0,
    related_code TEXT DEFAULT '',
    fetched_date TEXT,
    UNIQUE(published_at, title)
);
CREATE TABLE IF NOT EXISTS fetch_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return conn


def init_db():
    with _write_lock:
        conn = get_conn()
        conn.executescript(SCHEMA)
        conn.commit()


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def execute(sql, params=()):
    with _write_lock:
        conn = get_conn()
        conn.execute(sql, params)
        conn.commit()


def executemany(sql, rows):
    if not rows:
        return
    with _write_lock:
        conn = get_conn()
        conn.executemany(sql, rows)
        conn.commit()


def query(sql, params=()):
    conn = get_conn()
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


# ---------- 抓取状态 ----------
def get_state(key, default=None):
    row = query_one("SELECT value FROM fetch_state WHERE key=?", (key,))
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except Exception:
        return default


def set_state(key, value):
    execute(
        "INSERT INTO fetch_state(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )
