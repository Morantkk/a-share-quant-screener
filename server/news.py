# -*- coding: utf-8 -*-
"""盘前信息热榜：多源财经快讯聚合 → 去重 → 分类 → 规则打分排序"""
import re
import threading
import time
from datetime import datetime, timedelta

from . import akshare_compat  # noqa: F401
from . import database as db

_news_lock = threading.Lock()
_running = False

# 数据源：名称 → (akshare 接口名, 来源权重)
SOURCES = [
    ("em", "stock_info_global_em", 1.00),      # 东方财富全球财经快讯
    ("sina", "stock_info_global_sina", 0.95),  # 新浪全球财经快讯
    ("ths", "stock_info_global_ths", 0.90),    # 同花顺全球财经直播
    ("cls", "stock_info_global_cls", 1.05),    # 财联社电报（可能需要token，失败自动跳过）
    ("cjzc", "stock_info_cjzc_em", 0.75),      # 东方财富财经早餐
]

# 关键词 → 权重（标题命中满分，内容命中减半）
KEYWORDS = {
    "降息": 6, "加息": 6, "美联储": 5, "FOMC": 5, "非农": 5, "CPI": 5, "通胀": 4,
    "关税": 5, "制裁": 5, "禁令": 4, "突发": 4, "紧急": 4, "停牌": 4, "复牌": 3,
    "降准": 5, "印花税": 5, "货币政策": 4, "利率": 3, "国债": 3, "财政": 3,
    "重组": 4, "并购": 4, "收购": 3, "借壳": 4, "退市": 4, "IPO": 2, "增发": 2,
    "业绩": 3, "净利": 3, "预增": 3, "预亏": 3, "扭亏": 3, "财报": 3, "季报": 3,
    "涨停": 2, "跌停": 3, "炸板": 2, "龙头": 2, "新高": 2, "新低": 2,
    "涨价": 3, "提价": 3, "停产": 4, "减产": 3, "扩产": 2, "投产": 2,
    "订单": 3, "中标": 3, "签约": 2, "合作": 2, "获批": 3, "批准": 3,
    "爆雷": 5, "立案": 4, "调查": 3, "处罚": 3, "减持": 3, "增持": 3, "回购": 3,
    "分红": 2, "解禁": 3, "北向": 3, "外资": 3, "央行": 4, "证监会": 4,
    "英伟达": 4, "OpenAI": 3, "苹果": 3, "特斯拉": 3, "台积电": 3, "谷歌": 2, "微软": 2,
    "战争": 4, "地缘": 3, "原油": 3, "黄金": 2, "汇率": 3, "人民币": 3,
    "芯片": 3, "半导体": 3, "AI": 2, "人工智能": 3, "算力": 3, "光模块": 3,
    "新能源": 2, "光伏": 2, "锂电": 2, "机器人": 2, "创新药": 2, " vaccine": 2,
}

CATEGORY_RULES = [
    ("宏观", ["央行", "美联储", "降息", "加息", "CPI", "PPI", "GDP", "PMI", "社融", "信贷",
              "利率", "财政", "税", "通胀", "非农", "就业", "LPR", "MLF", "降准", "货币政策",
              "国债", "人民币", "汇率", "统计局", "国常会", "政治局"]),
    ("海外", ["美股", "纳指", "道指", "标普", "美元", "日元", "欧元", "欧洲", "日本", "英国",
              "特朗普", "美国", "地缘", "FOMC", "美联储", "中东", "俄乌", "原油", "OPEC"]),
    ("行业", ["板块", "产业", "芯片", "半导", "新能源", "光伏", "锂电", "汽车", "医药", "白酒",
              "地产", "银行", "券商", "保险", "军工", "煤炭", "钢铁", "化工", "电力", "算力",
              "AI", "人工智能", "消费", "电子", "机器人", "创新药", "储能", "风电", "游戏"]),
]


def _ak():
    import akshare as ak
    return ak


def _norm_title(t):
    return re.sub(r"[\s，。：:；;！!？?（）()【】\[\]\"'‘’“”]", "", str(t or ""))


def _classify(title, content, related_code):
    text = str(title) + " " + str(content or "")
    if related_code:
        return "个股"
    for cat, words in CATEGORY_RULES:
        for w in words:
            if w in text:
                return cat
    return "快讯"


def _related_code(title, names):
    """标题中出现股票名称 → 关联代码（名称长度≥3优先，避免误命中）"""
    t = str(title)
    best = ""
    for name in names:
        if len(name) >= 2 and name in t:
            if len(name) > len(best):
                best = name
    if not best:
        return "", ""
    for code, nm in names.items():
        if nm == best:
            return code, best
    return "", ""


def _score(title, content, source_weight, published_at):
    s = 0.0
    t, c = str(title), str(content or "")
    for kw, w in KEYWORDS.items():
        k = kw.strip()
        if not k:
            continue
        if k.lower() in t.lower():
            s += w
        elif k.lower() in c.lower():
            s += w * 0.5
    s *= source_weight
    try:
        pt = datetime.strptime(str(published_at)[:19], "%Y-%m-%d %H:%M:%S")
        age_h = (datetime.now() - pt).total_seconds() / 3600
        if age_h < 3:
            s += 3
        elif age_h < 12:
            s += 1.5
        elif age_h > 48:
            s -= 2
    except Exception:
        pass
    return round(min(s, 100.0), 2)


def refresh():
    """抓取各来源快讯，去重打分入库"""
    global _running
    with _news_lock:
        if _running:
            return {"ok": False, "msg": "正在抓取中"}
        _running = True
    try:
        return _refresh_impl()
    finally:
        _running = False


def _refresh_impl():
    ak = _ak()
    names = {r["code"]: r["name"] for r in db.query("SELECT code, name FROM stocks")}
    today = datetime.now().strftime("%Y-%m-%d")
    items = []
    for key, func_name, weight in SOURCES:
        try:
            func = getattr(ak, func_name, None)
            if func is None:
                continue
            from .akshare_compat import AKSHARE_LOCK
            with AKSHARE_LOCK:
                df = func()
            if df is None or df.empty:
                continue
            for _, r in df.head(120).iterrows():
                d = r.to_dict()
                title, content, pub = "", "", ""
                if key in ("em", "cjzc"):          # 东方财富系：标题/摘要/发布时间
                    title = str(d.get("标题", "")).strip()
                    content = str(d.get("摘要", "")).strip()
                    pub = str(d.get("发布时间", ""))
                elif key == "sina":                # 新浪：时间/内容
                    content = str(d.get("内容", "")).strip()
                    pub = str(d.get("时间", ""))
                    title = content[:60]
                elif key == "ths":                 # 同花顺：标题/内容/发布时间
                    title = str(d.get("标题", "")).strip()
                    content = str(d.get("内容", "")).strip()
                    pub = str(d.get("发布时间", ""))
                elif key == "cls":                 # 财联社：发布日期+发布时间
                    title = str(d.get("标题", "")).strip()
                    content = str(d.get("内容", "")).strip()
                    pub = f"{d.get('发布日期', '')} {d.get('发布时间', '')}".strip()
                if not title or title == "nan":
                    continue
                items.append({
                    "title": title[:200],
                    "content": content[:500],
                    "published_at": pub[:19].strip(),
                    "source": key,
                    "source_weight": weight,
                })
        except Exception:
            continue  # 该源失败跳过

    if not items:
        return {"ok": False, "msg": "所有新闻源抓取失败，请稍后重试"}

    # 去重（规范化标题）
    seen = {}
    for it in items:
        k = _norm_title(it["title"])
        if k not in seen or it["source_weight"] > seen[k]["source_weight"]:
            seen[k] = it
    items = list(seen.values())

    rows = []
    for it in items:
        code, name = _related_code(it["title"], names)
        cat = _classify(it["title"], it["content"], code)
        sc = _score(it["title"], it["content"], it["source_weight"], it["published_at"])
        rows.append((it["published_at"], it["title"], it["content"], it["source"], "",
                     cat, sc, code, today))
    db.executemany(
        "INSERT OR IGNORE INTO news_items(published_at, title, content, source, url, "
        "category, score, related_code, fetched_date) VALUES(?,?,?,?,?,?,?,?,?)", rows)
    # 清理30天前的旧新闻
    db.execute("DELETE FROM news_items WHERE fetched_date < ?",
               ((datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),))
    db.set_state("news", {"last_refresh": db.now_str(), "count": len(rows)})
    return {"ok": True, "msg": f"抓取 {len(rows)} 条（来自 {len(SOURCES)} 个源）"}


def hotlist(day=None, category=None, limit=60):
    day = day or datetime.now().strftime("%Y-%m-%d")
    sql = "SELECT * FROM news_items WHERE fetched_date=?"
    params = [day]
    if category and category != "全部":
        sql += " AND category=?"
        params.append(category)
    sql += " ORDER BY score DESC, published_at DESC LIMIT ?"
    params.append(int(limit))
    rows = db.query(sql, params)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        nm = db.query_one("SELECT name FROM stocks WHERE code=?", (r.get("related_code") or "",))
        r["related_name"] = nm["name"] if nm else ""
    return rows


def status():
    return db.get_state("news") or {}
