# -*- coding: utf-8 -*-
"""全局配置：默认值 + config.json 覆盖"""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
# 允许通过环境变量覆盖数据库路径（便于隔离测试与多实例部署）
DB_PATH = os.environ.get("QUANT_DB_PATH") or os.path.join(DATA_DIR, "quant.db")

DEFAULTS = {
    "password": "123456",      # 网页访问密码
    "port": 8787,              # 服务端口
    "fetch_threads": 6,        # 行情抓取线程数（过高容易被数据源限流）
    "history_days": 140,       # 日历天窗口（约120个交易日，即半年）
    "news_time": "07:40",      # 每日热榜抓取时间
    "quotes_time": "16:10",    # 每日行情增量更新时间
    "calendar_time": "06:30",  # 每日财经日历刷新时间
}


def load_config():
    cfg = dict(DEFAULTS)
    path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


CONFIG = load_config()
