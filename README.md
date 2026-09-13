# Crawler Power Kit（爬虫能力增强套件）

把本机安装的 **Firecrawl / Crawl4AI / Crawlee / Scrapy / Playwright** 工具链、
**16 个免 API key 搜索引擎**、**学术文献 API** 与**反幻觉引文核验**整合为
一个 CLI（`cpk.py`）加一套方法论参考文档。

## 为什么需要它

单装一堆爬虫库并不等于爬虫能力强——真正的差距在**路由决策**：
什么任务用哪一层、什么时候升级、什么时候停止、怎么验证结果没有撒谎。
本套件把踩坑经验固化为可执行代码。

## 一个 CLI，八个命令

```bash
cpk doctor                # 工具链体检：依赖/浏览器/代理/学术API 逐项检查
cpk search "查询词" --fetch # 16引擎语言路由 + DDG/Bing 结果解析
cpk quick <url>           # 升级阶梯抓取：urllib→Crawl4AI→Playwright 自动升级
cpk batch urls.txt        # 并发批量 + URL归一化去重（utm/会话参数剔除）
cpk render <url>          # Playwright 真浏览器渲染 JS 页（可截图取证）
cpk md <url>              # Crawl4AI 提取干净 Markdown（喂 LLM）
cpk paper "标题或DOI"      # DOI注册表 + Crossref + OpenAlex + arXiv 查证
cpk verify refs.txt       # 批量参考文献核验，输出 VERIFIED/LIKELY/MISMATCH/NOT_FOUND
```

全部命令支持 `--json`。**核心层零依赖**（纯 stdlib），任何 Python 3.10+ 可跑；
Crawl4AI/Playwright 缺失时自动降级并说明，绝不崩溃。

## 升级阶梯（核心设计）

```
Layer 1  urllib 直抓（代理失败→直连自动重试）    ~0.5s/页
Layer 2  Crawl4AI（60s硬预算，LLM-ready MD）      ~5s/页
Layer 3  Playwright 真浏览器（JS/点击/登录态）    ~10s/页
```

**只在当前层被证明失败时升级**——每层成本差一个数量级，选错层就是浪费。

## 已内置的实战坑位修复

- Windows 下 Playwright/Crawl4AI `Browser.close()` 退出噪音异常（结果完好）
- 本机代理 502 隧道错误 → 自动直连重试
- arXiv API 四个静默陷阱（HTTP-200 Error 条目 / feed link 误判 / id 版本后缀 / 硬换行）
- 搜索结果 HTML 实体解码、DDG 跳转 URL 解包
- Crawl4AI 首次冷启动慢 → 60s 预算后优雅放弃

## 安装（作为 Claude/WorkBuddy 类智能体的 skill）

把本目录放入 skills 目录（如 `~/.workbuddy/skills/crawler-power-kit/`），
智能体即可按 SKILL.md 的触发条件自动调用。也完全可以当普通 Python 工具用：

```bash
python scripts/cpk.py doctor
python examples/run_demo.py
```

## 目录结构

```
crawler-power-kit/
├── SKILL.md                    # 智能体入口：路由原则 + 硬规则
├── scripts/
│   ├── cpk.py                  # 统一 CLI（8 命令）
│   ├── engines.py              # 16引擎注册表 + DDG/Bing 解析器
│   ├── ladder.py               # 升级阶梯实现（fetch/dedup/batch）
│   ├── academic.py             # Crossref/OpenAlex/arXiv/DOI 注册表
│   └── verify_refs.py          # 批量引文核验（Crossref）
├── references/                 # 方法论文档（8 篇）
│   ├── ROUTING.md              #   升级阶梯与目标分类
│   ├── PERFORMANCE.md          #   提速与效能清单
│   ├── TOOLCHAIN-LOCAL.md      #   本机工具地图与已知坑
│   ├── SEARCH-ENGINES.md       #   16引擎与高级语法
│   ├── EVIDENCE-PIPELINE.md    #   证据记录/去重/分级
│   ├── CITATION-INTEGRITY.md   #   反幻觉引文 SOP
│   ├── ACADEMIC-API.md         #   学术 API 配方
│   └── SECURITY.md             #   合规红线
├── assets/source-record.schema.json
├── examples/run_demo.py
├── CREDITS.md
└── LICENSE
```

## License

MIT — 见 [LICENSE](LICENSE)。各来源技能的许可见 [CREDITS.md](CREDITS.md)。
