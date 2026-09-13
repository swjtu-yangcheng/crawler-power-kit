# CREDITS — 来源与致谢

本套件整合并重构了以下本机技能与实践经验：

| 来源 | 贡献 | 许可 |
|---|---|---|
| crawler-supervisor（自研） | 路由方法论、证据分级、去重顺序、SECURITY/EVIDENCE/ACADEMIC 参考、《增强智能体网页爬虫能力》1251行调研（TOOLCHAIN） | 自有 |
| web-research-pro（自研） | 环境绑定工具地图、verify_refs.py、CITATION-INTEGRITY（源自《杜绝与纠正"幻觉参考文献"的经验总结》）、AUTHOR-SURVEY 方法 | 自有 |
| multi-search-engine（第三方，v2.1.3） | 16 引擎清单、语言路由、cookie 策略（已固化为 engines.py） | MIT |
| paper-lookup（第三方） | arXiv Atom 四陷阱、Crossref/OpenAlex 配方（浓缩进 academic.py 与 ACADEMIC-API.md） | 见原仓库 |
| Kail的AI工具箱《10个GitHub仓库，免费爬取整个互联网》 | Firecrawl/Crawl4AI/Playwright/Crawlee/Scrapy 三层选型法 | 公众号文章，观点引用 |
| 本机实战（2026-08~09） | 代理502直连回退、Windows Browser.close 噪音、Crawl4AI 冷启动预算、申报书文献核验实战 | — |

第三方工具链（运行时依赖，非本包分发）：
Firecrawl (firecrawl/firecrawl)、Crawl4AI (unclecode/crawl4ai)、
Crawlee (apify/crawlee)、Scrapy (scrapy/scrapy)、Playwright (microsoft/playwright)。

若作为独立仓库发布，请保留本文件中的来源说明。
