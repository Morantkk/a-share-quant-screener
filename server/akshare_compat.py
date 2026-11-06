# -*- coding: utf-8 -*-
"""
akshare 兼容补丁（导入即生效）：
1. 东方财富等数据源拒绝不带 User-Agent 的请求 → 统一注入浏览器 UA
2. 东财 keep-alive 复用陈旧连接 → 注入 Connection: close，每请求新建连接，避免 RemoteDisconnected
3. 东财 push2 / push2his 行情子域在部分网络/时段不稳定 → 重写为已验证稳定的镜像主机并带故障回退

实测可用主机（2026-08）：
  push2.eastmoney.com         → 30.push2.eastmoney.com / push2delay.eastmoney.com
  push2his.eastmoney.com      → push2hisdelay.eastmoney.com
"""
import re
import threading

import requests

# 全局串行锁：akshare 部分接口（东方财富历史K线、新闻/日历快讯等）内部使用
# py_mini_racer（V8 JS 引擎），该引擎非线程安全，多线程并发调用会直接让进程崩溃。
# 所有会触发 py_mini_racer 的 akshare 调用都必须在此锁内执行（新浪日K抓取不走该路径，可并发）。
AKSHARE_LOCK = threading.Lock()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# push2 行情（实时列表/个股）替代主机，按稳定性排序
_PUSH2_FALLBACK = [
    "30.push2.eastmoney.com",
    "push2delay.eastmoney.com",
    "push2.eastmoney.com",
]
# push2his 历史 K 线替代主机
_PUSH2HIS_FALLBACK = [
    "push2hisdelay.eastmoney.com",
    "push2his.eastmoney.com",
]

_patched = False


def _host_of(url):
    m = re.match(r"^https?://([^/]+)", url)
    return m.group(1) if m else ""


def _rewrite(url, host):
    return re.sub(r"^https?://[^/]+", f"https://{host}", url, count=1)


def patch():
    global _patched
    if _patched:
        return
    _patched = True
    orig = requests.Session.request

    def patched_request(self, method, url, **kw):
        # 1) 注入 UA + 关闭 keep-alive
        headers = dict(kw.get("headers") or {})
        if not any(k.lower() == "user-agent" for k in headers):
            headers["User-Agent"] = UA
        headers["Connection"] = "close"
        kw["headers"] = headers

        # 2) 选择回退主机列表
        host = _host_of(url)
        if re.search(r"(?:^|\.)push2his\.eastmoney\.com$", host):
            hosts = _PUSH2HIS_FALLBACK
        elif re.search(r"(?:^|\.)push2\.eastmoney\.com$", host):
            hosts = _PUSH2_FALLBACK
        else:
            hosts = [host]  # 非东财域名，原样请求

        for fb in hosts:
            try:
                return orig(self, method, _rewrite(url, fb), **kw)
            except requests.RequestException:
                continue
        # 全部失败，抛出最后一个（让上层重试）
        return orig(self, method, url, **kw)

    requests.Session.request = patched_request


patch()
