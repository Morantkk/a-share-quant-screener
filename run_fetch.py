# -*- coding: utf-8 -*-
"""独立全市场抓取脚本：不启动 Web 服务，直接拉取日 K 到本地库。

用法:
    python run_fetch.py              # 用 config.json 的线程数/天窗，东财优先
    python run_fetch.py --sina       # 强制只走新浪源（东财被限流时用）
    python run_fetch.py --days 250   # 覆盖天窗
"""
import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import database as db, fetcher
from server.config import CONFIG


def main():
    ap = argparse.ArgumentParser(description="全市场日 K 独立抓取")
    ap.add_argument("--days", type=int, default=None, help="抓取天窗（自然日），默认取 config.json")
    ap.add_argument("--threads", type=int, default=None, help="并发线程数，默认取 config.json")
    ap.add_argument("--sina", action="store_true", help="强制只使用新浪数据源")
    args = ap.parse_args()

    days = args.days or int(CONFIG.get("history_days", 140))
    threads = args.threads or int(CONFIG.get("fetch_threads", 6))
    use_em = not args.sina and bool(CONFIG.get("use_eastmoney", True))

    db.init_db()

    # 股票列表为空时先拉一次全市场列表
    codes = [r["code"] for r in db.query("SELECT code FROM stocks")]
    if not codes:
        print("股票列表为空，先刷新股票列表...", flush=True)
        fetcher.refresh_stock_list()
        codes = [r["code"] for r in db.query("SELECT code FROM stocks")]
    if not codes:
        print("仍无法获取股票列表，请检查网络或稍后重试。", flush=True)
        return 1

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    src = "东财优先(新浪兜底)" if use_em else "仅新浪"
    print(f"开始抓取 {len(codes)} 只 | 时间窗 {start}~{end} | 源={src} | 线程={threads}", flush=True)

    ak = fetcher._ak()
    done, ok, fail = [0], [0], [0]
    lock = threading.Lock()
    t0 = time.time()

    def work(code):
        try:
            df = fetcher._fetch_one(ak, code, start, end, use_eastmoney=use_em)
            n = fetcher._save_daily(code, df)
            with lock:
                if n and n > 0:
                    ok[0] += 1
                else:
                    fail[0] += 1
        except Exception:
            with lock:
                fail[0] += 1
        with lock:
            done[0] += 1
            if done[0] % 50 == 0:
                print(f"  进度 {done[0]}/{len(codes)} 成功{ok[0]} 失败{fail[0]} "
                      f"用时{time.time() - t0:.0f}s", flush=True)

    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = [pool.submit(work, c) for c in codes]
        for _ in as_completed(futures):
            pass

    print(f"抓取完成 成功{ok[0]} 失败{fail[0]} 总用时{time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
