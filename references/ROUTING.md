# ROUTING — 升级阶梯与目标分类

整合自 crawler-supervisor（方法论）与 web-research-pro（本机执行版）。

## 核心原则

**用最便宜可靠的方法先做，只有当前层被证明不足时才升级。**
"证明"= 空正文 / JS壳 / 403/429/5xx / 代理隧道失败。绝不等同于"更强的工具存在"。

```text
搜索/发现（WebSearch、cpk search、sitemap、RSS）
  ↓
Layer 1 直抓（urllib，含代理失败→直连重试）
  ↓
Layer 2 Crawl4AI（60s预算，markdown输出，缓存）
  ↓
Layer 3 Playwright（真浏览器：JS、点击、登录态、截图）
  ↓
平台专用（Scrapy管道 / Crawlee队列 / firecrawl云 / Apify级）
```

## 目标分类 → 默认路由

| 目标类型 | 默认路由 |
|---|---|
| 静态/服务端渲染 | Layer 1 直抓 |
| 站内未知URL | sitemap / `cpk search --site` |
| 有界同构区块 | focused crawl（Crawl4AI BFS） |
| JS/交互依赖 | `render`（Playwright） |
| 大平台 | 先找官方 API |
| 学术源 | `paper`（DOI注册表+Crossref+OpenAlex+arXiv） |
| 需登录 | 仅用户授权会话内 Playwright，凭据不落盘 |

## 爬取前先找结构化出口

官方 API > RSS/Atom > sitemap > 可下载数据集 > 公开 JSON 端点 > HTML。
robots.txt 和 sitemap.xml 是第一站：
```bash
curl -sL <site>/robots.txt
curl -sL <site>/sitemap.xml
```

## 升级触发器（精确条件）

- **Layer1→2**：正文 <200 字且 HTML >50KB（JS壳）；或挑战页标记。
- **Layer2→3**：需要点击/滚动/表单才出内容；UI-only 翻页；登录态；
  视觉布局本身是证据（截图）。
- **→平台专用**：数千页以上同构数据；需要队列/断点续爬/自动重试。

## 403/429/挑战页处理（不硬怼）

1. 核对 URL 与请求头；
2. 降速降并发；
3. 换官方 API/feed/导出；
4. 换合法替代信源；
5. 仍不行→报告用户，绝不循环重试。

## 范围边界（每次爬取前设定）

域名/路径/包含/排除。默认排除：登录页、购物车、无界日历、facet 排列组合、
跟踪参数、多语言/打印/移动端重复、无关二进制。

## 与兄弟技能的交接

| 目标 | 交给 |
|---|---|
| 大纲驱动多轮调研 | deep-research 家族 |
| AI 搜索综述 | deepseek-websearch |
| arXiv 监控摘要 | arxiv-watcher |
| 11 学术 API 深检索 | paper-lookup |
| 视频素材 | youtube-video-downloader |
| 命题式深研（综述/评审/事实核查） | ars-deep-research |
