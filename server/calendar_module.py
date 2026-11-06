# -*- coding: utf-8 -*-
"""财经日历：国内宏观 + 海外宏观规则生成（标注"预计"），支持手动添加事件"""
from datetime import date, datetime, timedelta

from . import database as db

# 美联储官方公布的 FOMC 2026 议息日程（决议日=会议第二天，北京时间次日凌晨）
FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
             "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]


def _add(events, d, time_str, region, title, importance, note="", source="auto"):
    if isinstance(d, date):
        d = d.strftime("%Y-%m-%d")
    events.append({
        "date": d, "time": time_str, "region": region, "title": title,
        "importance": importance, "note": note, "source": source,
    })


def _first_friday(y, m):
    d = date(y, m, 1)
    offset = (4 - d.weekday()) % 7  # 周五=4
    return d + timedelta(days=offset)


def _last_day(y, m):
    if m == 12:
        return date(y, 12, 31)
    return date(y, m + 1, 1) - timedelta(days=1)


def generate(start_date, end_date):
    """生成 [start_date, end_date] 区间内的规则日历事件"""
    events = []
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    cur = start.replace(day=1)
    while cur <= end:
        y, m = cur.year, cur.month

        # ---- 国内 ----
        _add(events, date(y, m, 9) if not date(y, m, 9).weekday() >= 5 else date(y, m, 11),
             "09:30", "CN", "中国 CPI / PPI 数据（预计）", 2, "统计局，具体日期以官方为准")
        _add(events, _last_day(y, m), "09:30", "CN", "中国官方 PMI（预计）", 2, "统计局，月末发布")
        _add(events, date(y, m, 20), "09:15", "CN", "LPR 报价", 3, "央行每月20日（节假日顺延）")
        _add(events, date(y, m, 15), "", "CN", "MLF 操作（预计）", 2, "央行月中")
        _add(events, date(y, m, 12), "", "CN", "社融 / 新增信贷数据（预计）", 2, "央行，中旬发布")
        # 季度 GDP
        if m in (1, 4, 7, 10):
            _add(events, date(y, m, 17), "10:00", "CN", "中国 GDP 及经济数据（预计）", 3, "统计局")
        # 定期报告披露截止
        for (mm, dd, title) in [(4, 30, "A股年报+一季报披露截止"), (8, 31, "A股中报披露截止"),
                                 (10, 31, "A股三季报披露截止"), (1, 31, "业绩预告披露截止（有条件强制）"),
                                 (7, 15, "中报业绩预告披露截止（有条件强制）")]:
            ed = date(y, mm, dd)
            if start <= ed <= end:
                _add(events, ed, "", "CN", title, 2, "交易所规则")
        for (mm, dd, title, imp) in [(3, 5, "全国两会开幕（预计）", 3), (12, 11, "中央经济工作会议（预计）", 3)]:
            ed = date(y, mm, dd)
            if start <= ed <= end:
                _add(events, ed, "", "CN", title, imp, "重要政策窗口")

        # ---- 海外（美国） ----
        fomc = f"{y}-{m:02d}" + "-%02d" % 0  # 占位不用
        for f in FOMC_2026:
            fd = datetime.strptime(f, "%Y-%m-%d").date()
            if start <= fd <= end:
                _add(events, fd, "次日02:00", "US", "美联储 FOMC 利率决议", 3,
                     "北京时间次日凌晨公布，附新闻发布会")
        nfp = _first_friday(y, m)
        _add(events, nfp, "20:30", "US", "美国非农就业报告（预计）", 3, "每月第一个周五")
        _add(events, date(y, m, 11), "20:30", "US", "美国 CPI 数据（预计）", 3, "劳工统计局，中旬")
        _add(events, date(y, m, 14), "20:30", "US", "美国 PPI 数据（预计）", 2, "")
        _add(events, _last_day(y, m), "22:30", "US", "美国核心 PCE 物价指数（预计）", 3, "月末")
        _add(events, date(y, m, 1), "22:00", "US", "美国 ISM 制造业 PMI（预计）", 2, "")
        # 美股财报季高峰（重点公司如英伟达/苹果/微软多在此时段）
        for (mm, dd, title) in [(1, 27, "美股四季报披露高峰开启（预计）"), (4, 27, "美股一季报披露高峰开启（预计）"),
                                 (7, 27, "美股二季报披露高峰开启（预计）"), (10, 27, "美股三季报披露高峰开启（预计）")]:
            ed = date(y, mm, dd)
            if start <= ed <= end:
                _add(events, ed, "", "US", title, 2, "英伟达/苹果/微软等重磅财报多在高峰周")
        cur = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)

    return [e for e in events if start <= datetime.strptime(e["date"], "%Y-%m-%d").date() <= end]


def refresh():
    """刷新未来约两个月的自动日历（手动添加的事件保留）"""
    today = date.today()
    start = today.strftime("%Y-%m-%d")
    end = (today + timedelta(days=65)).strftime("%Y-%m-%d")
    db.execute("DELETE FROM calendar_events WHERE source='auto' AND date>=?", (start,))
    events = generate(start, end)
    ts = db.now_str()
    rows = [(e["date"], e["time"], e["region"], e["title"], e["importance"],
             "", "", e["note"], e["source"], ts) for e in events]
    db.executemany(
        "INSERT INTO calendar_events(date, time, region, title, importance, prior, "
        "forecast, note, source, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def get_events(start, end, region=None, importance_min=None):
    sql = "SELECT * FROM calendar_events WHERE date>=? AND date<=?"
    params = [start, end]
    if region:
        sql += " AND region=?"
        params.append(region)
    if importance_min:
        sql += " AND importance>=?"
        params.append(int(importance_min))
    sql += " ORDER BY date, time"
    return db.query(sql, params)


def add_manual(date_str, title, region="CN", importance=2, time_str="", note=""):
    db.execute(
        "INSERT INTO calendar_events(date, time, region, title, importance, note, source, created_at) "
        "VALUES(?,?,?,?,?,?, 'manual', ?)",
        (date_str, time_str, region, title, int(importance), note, db.now_str()))


def delete_event(event_id):
    db.execute("DELETE FROM calendar_events WHERE id=? AND source='manual'", (event_id,))
