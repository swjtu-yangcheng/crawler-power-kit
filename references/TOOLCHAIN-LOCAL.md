# TOOLCHAIN-LOCAL — 本机爬虫工具地图（2026-09 核对）

本机（Windows，用户 yangc）实际安装的工具链。`cpk.py doctor` 可随时复核。

## Python 侧（managed venv，首选解释器）

```
C:\Users\yangc\.workbuddy\binaries\python\envs\default\Scripts\python.exe
```

| 库 | 版本 | 选用时机 |
|---|---|---|
| Crawl4AI | 0.9.3 | LLM-ready Markdown、批量爬取、自带缓存；builtin 浏览器模式无需 Playwright |
| Crawlee | 1.10.0 | 需要队列/去重/自动重试的工程化爬虫（Python API） |
| Scrapy | 2.19.0 | 百万页级工业管道、中间件、Item Pipeline |
| playwright | 1.62.0 | JS 渲染、点击/表单/翻页、登录态（用户授权）、截图取证 |
| playwright-stealth | 2.0.3 | 常规 UA 被识别时的隐身增强（合规站点） |
| firecrawl-py | 4.42.0 | 云端 search/scrape/map（需 FIRECRAWL_API_KEY） |
| httpx / aiohttp | 0.28 / 3.14 | 异步批量请求 |
| bs4 / lxml | 4.15 / 6.1 | HTML 解析 |

## Node 侧

```
node:    C:\Users\yangc\.workbuddy\binaries\node\versions\22.22.2-2\node.exe
firecrawl-cli:  C:\Users\yangc\.workbuddy\binaries\node\workspace\node_modules\firecrawl-cli\dist\index.js  (v1.22.0)
playwright:     node workspace 内（chromium-1234 已装于 %LOCALAPPDATA%\ms-playwright）
```

firecrawl CLI 运行方式（未设全局 PATH 时）：

```bash
NODE_PATH=C:/Users/yangc/.workbuddy/binaries/node/workspace/node_modules \
  node .../firecrawl-cli/dist/index.js scrape <url>      # 需 FIRECRAWL_API_KEY
```

## 三层选型法（来自 Kail 的AI工具箱调研 + 实测）

| 需求层次 | 选 |
|---|---|
| 只要干净数据，不想写解析（RAG/喂LLM） | Crawl4AI（本机免key）或 Firecrawl（云，需key） |
| 要控制浏览器行为、模拟真实用户 | Playwright（新）；Crawlee 介于中间 |
| 大规模爬虫管道（百万页） | Scrapy + Playwright 组合 |

## 已知本机坑（实测记录）

1. **本机代理 `127.0.0.1:51603` 对部分境外站返回 502 隧道错误**（如
   news.ycombinator.com）。ladder.py 已内置代理失败→直连重试；若直连
   也不通，说明站点被墙，需用户开 VPN 后重试。
2. **Playwright/Crawl4AI 在 Windows 上 `Browser.close()` 常报
   "Connection closed while reading from the driver"**——退出噪音，
   结果完好。套件已捕获；自写脚本时务必 `try/except` 包住 close。
3. **Crawl4AI builtin 浏览器首次冷启动慢**（可能下载数据）——已加 60s
   预算，超时优雅放弃并落到 Playwright 层。
4. **百度直接抓搜索页易触发反爬**；`search --fetch` 里 DDG/Bing 解析
   最稳，百度结果建议走 WebSearch 工具或浏览器层。
