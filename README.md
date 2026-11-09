# 量化选股系统

> 本地部署的 A 股量化选股 Web 应用 —— 多线程行情抓取 + 固定指标组合选股 + K 线形态匹配 + 财经日历 + 盘前信息热榜

![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-orange)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

> [!IMPORTANT]
> **本项目仅供学习与研究使用，禁止任何商业用途。**
> 采用 [PolyForm Noncommercial 1.0.0](LICENSE) 许可：可以自由阅读、学习、修改、分发，但**不得用于商业目的**（包括但不限于：出售、付费服务、企业内部生产使用、嵌入商业产品、SaaS 对外提供）。
> 如需商业授权，请联系作者。

单机运行、浏览器交互，数据存本地 SQLite。**全部选股条件都是固定指标积木块**，不经过任何大模型自然语言解析，口径确定、结果可复现。

---

## 界面预览

> 截图托管在 jsDelivr CDN（国内网络可直接显示），原图同时保存在仓库 [`docs/screenshots/`](docs/screenshots/) 目录。
> 若图片仍不显示，通常是网络问题——可直接打开仓库里的原图文件查看。

### 条件选股 —— 点击积木块组合条件，全市场筛选

![条件选股](https://cdn.jsdelivr.net/gh/Morantkk/a-share-quant-screener@main/docs/screenshots/02-screener.png)

### K 线形态匹配 —— 用一段 K 线去找"正在走出相同形态"的股票

![形态匹配](https://cdn.jsdelivr.net/gh/Morantkk/a-share-quant-screener@main/docs/screenshots/04-pattern.png)

### 盘前信息热榜 —— 多源快讯去重、分类、按权重打分排序

![盘前热榜](https://cdn.jsdelivr.net/gh/Morantkk/a-share-quant-screener@main/docs/screenshots/01-hotlist.png)

### 个股行情 —— K 线 / 成交量 / 均线，可在图上框选一段作为形态模板

![个股行情](https://cdn.jsdelivr.net/gh/Morantkk/a-share-quant-screener@main/docs/screenshots/03-quote.png)

### 财经日历 —— 未来 1~2 个月国内外重要事件

![财经日历](https://cdn.jsdelivr.net/gh/Morantkk/a-share-quant-screener@main/docs/screenshots/05-calendar.png)

### 自选池

![自选池](https://cdn.jsdelivr.net/gh/Morantkk/a-share-quant-screener@main/docs/screenshots/06-watchlist.png)

### 数据管理 —— 手动触发抓取 / 热榜 / 日历，也可查看数据状态

![数据管理](https://cdn.jsdelivr.net/gh/Morantkk/a-share-quant-screener@main/docs/screenshots/07-data.png)

---

## 功能

### 1. 日 K 数据抓取

多线程抓取全 A 股（沪深京，约 5900 只）日 K 线，半年滚动窗口（默认 140 个自然日）。每天收盘后按设定时间自动增量更新，也可在「数据管理」手动触发。

### 2. 条件选股（17 类固定指标积木块）

点击添加条件 → 填参数 → 且/或组合。**全程无自然语言解析**，每个条件的计算口径固定，同一份数据必然得到同一结果。

| 分类 | 指标块 |
|---|---|
| 均线 | 均线交叉（金叉/死叉）、股价与均线位置、均线排列（多头/空头） |
| MACD | 金叉死叉、状态（红柱/绿柱、DIF 与 0 轴关系） |
| KDJ | 金叉死叉、状态（超买/超卖） |
| 其他指标 | RSI 区间、布林带（突破/位置） |
| 量能 | 量比（今量/前 5 日均量）、换手率、连续放量/缩量 |
| 价格形态 | 突破平台、回踩均线、涨跌幅、股价区间、创 N 日新高/新低 |

选出的结果可直接加入自选池；条件组合可存为策略随时载入。

### 3. K 线形态匹配

两种提供模板的方式：

- **行情页框选**（推荐）：在 K 线图上按住鼠标拖选一段，点「用此段匹配」即可，取到的是精确的收盘价序列。
- **上传截图**（辅助）：从红涨绿跌的清晰 K 线截图中粗略提取走势，无量纲、精度有限。

匹配算法为 **DTW（动态时间规整）+ 相关系数**，可选「同时匹配成交量节奏」，可选「近半年任意时段扫描」做历史复盘。输出带相似度评分和每只股票对应的 K 线片段缩略图。

### 4. 财经日历

自动生成未来 1~2 个月的重要事件：中国 CPI / PPI / PMI / LPR / MLF / 社融 / GDP、财报披露截止、美国 FOMC / 非农 / CPI / PCE、美股财报季等。每天自动刷新，支持手动添加自定义事件（如某公司财报）。

### 5. 盘前信息热榜

整合东方财富 / 新浪 / 同花顺 / 财联社等多源快讯，去重后按「关键词权重 + 来源权重 + 时效性」打分排序，并分类为宏观 / 海外 / 行业 / 个股 / 快讯。交易日早间自动抓取，个股消息可一键跳转 K 线。

---

## 快速开始

### 环境要求

- Python 3.9+（推荐 3.10 及以上）
- 可访问公开行情接口的网络环境

### 安装

```bash
git clone https://github.com/Morantkk/a-share-quant-screener.git
cd a-share-quant-screener

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 配置

仓库不含 `config.json`（含访问密码，因人而异）。从示例复制一份即可：

```bash
# Windows
copy config.example.json config.json
# macOS / Linux
cp config.example.json config.json
```

不创建也能跑，此时使用 `server/config.py` 里的默认值。

### 启动

```bash
# Windows：双击 run.bat，或
run.bat

# 跨平台通用
python -m uvicorn server.main:app --host 0.0.0.0 --port 8787
```

浏览器访问 <http://127.0.0.1:8787>，默认密码 `123456`（请自行修改 `config.json`）。
局域网其他设备可通过 `http://<本机IP>:8787` 访问。

### 首次使用

1. 登录后进入「数据管理」，点 **增量更新**。首次全量抓取约 5~15 分钟（取决于网络与线程数，进度条实时显示）。
2. 抓取完成后即可使用选股、形态匹配等功能。
3. 「数据管理」中也可手动触发热榜抓取和日历刷新；这三项任务每天也会按配置时间自动执行。

> 仓库不附带任何行情数据库，`data/quant.db` 在首次抓取后自动生成。

---

## 配置项

`config.json`（全部字段可选，缺省用默认值）：

| 配置项 | 默认 | 说明 |
|---|---|---|
| `password` | `123456` | 网页访问密码 |
| `port` | `8787` | 服务端口 |
| `fetch_threads` | `6` | 行情抓取线程数，过高容易被数据源限流 |
| `history_days` | `140` | 保留的日 K 天数（约 120 个交易日，即半年） |
| `news_time` | `07:40` | 每日热榜抓取时间 |
| `quotes_time` | `16:10` | 每日行情增量更新时间 |
| `calendar_time` | `06:30` | 每日财经日历刷新时间 |

此外支持通过环境变量 `QUANT_DB_PATH` 覆盖数据库路径，便于隔离测试或多实例部署。

---

## 技术架构

| 层 | 选型 |
|---|---|
| 后端 | Python + FastAPI + SQLite（WAL 模式） |
| 计算 | pandas / numpy（指标与 DTW 用 numpy 向量化实现） |
| 数据源 | akshare（东方财富 / 新浪等公开接口，免费，需联网） |
| 前端 | 原生 JavaScript + ECharts（本地化引入，运行时不依赖外网 CDN） |
| 部署 | 单机单进程，浏览器交互，无需额外数据库服务 |

## 目录结构

```
.
├── run.bat                    # Windows 一键启动（自动检测解释器并补依赖）
├── run_fetch.py               # 独立抓取脚本（不开服务也能抓数据）
├── config.example.json        # 配置示例，复制为 config.json 后生效
├── requirements.txt
├── server/                    # 后端
│   ├── main.py                # FastAPI 入口与全部 API
│   ├── config.py              # 默认配置 + config.json 覆盖
│   ├── database.py            # SQLite 封装与表初始化
│   ├── fetcher.py             # 多线程日 K 抓取（东财主源 + 新浪兜底）
│   ├── akshare_compat.py      # akshare 请求兼容层（UA / 短连接 / 镜像回退）
│   ├── indicators.py          # 技术指标计算
│   ├── screener.py            # 条件选股引擎（指标块定义与执行）
│   ├── pattern.py             # 形态匹配（DTW + 相关系数 + 截图识别）
│   ├── calendar_module.py     # 财经日历生成
│   ├── news.py                # 新闻抓取、去重、分类与打分
│   ├── cache.py               # 行情内存缓存
│   ├── auth.py                # 简单 token 鉴权
│   └── scheduler.py           # 每日定时任务
├── web/                       # 前端
│   ├── index.html
│   ├── css/app.css
│   ├── js/{api,app,screen,pattern,quote,calendar}.js
│   └── vendor/echarts.min.js
├── tests/
│   ├── test_synthetic.py      # 离线引擎测试（合成数据，不联网）
│   └── test_pipeline.py       # 小批量全链路实测（需联网）
├── docs/screenshots/          # 界面截图
└── data/                      # 运行时生成，不入库
```

## 测试

```bash
# 离线：用合成数据验证筛选/匹配/指标引擎，不联网、不碰真实库
python tests/test_synthetic.py

# 联网：小批量抓取 20 只 → 筛选 → 形态匹配，验证全链路
python tests/test_pipeline.py
```

`test_synthetic.py` 会生成 80 只股票 × 140 天的随机游走数据，并植入 3 只"先跌后涨 + 末端放量"的确定性形态，用于校验筛选能精确命中、形态匹配能把植入样本排到前列。

---

## 数据源与容错

- 主数据源为**东方财富**（经 akshare）。抓取器启动时会探测：若东方财富返回反爬拦截页（临时限流），自动整批切换到**新浪**兜底源，并在抓取进度中提示当前数据源。
- 每个请求都带浏览器 UA、关闭长连接复用（`Connection: close`），并针对东财 `push2` / `push2his` 不稳定子域做了**镜像主机回退**，避免长时间卡死。
- 单只股票抓取失败会自动重试 3 次并指数退避；整批失败率过高时不会无限重试，失败代码会被记录供后续增量补齐。
- 新闻源接口偶尔变动，**单个源失败自动跳过**，不影响其他源。
- 部分 akshare 接口内部使用 V8 引擎（py_mini_racer）且非线程安全，代码中对这类调用加了全局串行锁；行情抓取的新浪通道仍保持多线程并发。
- 若需强制指定数据源，可在 `config.json` 加 `"use_eastmoney": false` 只走新浪（适合东财被限流期间）。

## 常见问题

**Q：首次抓取很慢或大量失败？**
A：多为数据源限流。可把 `fetch_threads` 调到 4~6，稍等一段时间再增量更新（已入库的不会重抓）。

**Q：页面能打开但数据全空？**
A：尚未抓取。去「数据管理」点一次 **增量更新**。

**Q：抓取进度一直停在"抓取中"？**
A：进程被强杀会让状态残留。新版本已修复——服务启动时会自动复位未完成的抓取状态。

**Q：能抓港股 / 美股吗？**
A：当前只覆盖 A 股（沪深京）。数据层按代码前缀区分市场，扩展其他市场需另接数据源。

---

## 免责声明

- 本项目为**技术学习与研究用途**，**未经授权禁止商业使用**（详见[许可证](#许可证)）。所有数据来自互联网公开免费接口，仅供个人参考，**不构成任何投资建议**。
- 数据源由第三方提供，可能存在延迟、缺失或错误；据此做出的任何决策及其后果由使用者自行承担。
- 请合理控制抓取频率，遵守数据源的 robots 与使用条款，勿用于商业用途的大规模采集。
- 海外事件日程（如美股个别公司财报）以规则生成 + 手动补充为主，标注"预计"的请以官方公布为准。

## 许可证

本项目采用 **[PolyForm Noncommercial 1.0.0](LICENSE)** 许可。

### 你可以

- 阅读、克隆、下载代码
- 个人学习、研究、实验、做课程作业或业余项目
- 修改代码、二次开发供自己学习使用
- 在**保留本许可与版权声明**的前提下分发副本

### 你不可以

- **任何商业用途**：出售本项目或其衍生品、提供付费服务、嵌入商业产品或收费工具
- **企业内部生产使用**：在公司业务系统、生产环境、对外服务中部署
- **SaaS / 云服务**：把本项目或其修改版作为线上服务对外提供
- 移除或隐藏版权声明与许可声明

> 商业授权请联系作者。未获授权而商用，即构成侵权。

### 关于"开源"的说明

严格意义上，本项目属于**源码公开（source-available）**而非 OSI 定义的开源软件——因为 OSI 开源定义要求「不得限制任何领域的使用」，而本项目禁止商用。这样做的目的是防止有人直接拿去卖钱或包装成付费产品，同时保留学习交流的自由。
