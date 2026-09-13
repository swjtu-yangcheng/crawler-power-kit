# SEARCH-ENGINES — 16 引擎注册表（免 API key）

来自 multi-search-engine skill 的引擎清单，已固化为 `engines.py` 注册表，
可被 `cpk.py search` 直接调用。

## 语言路由（自动）

- **中文查询**（CJK 字符 ≥20%）→ 国内引擎优先：
  `baidu → bing-cn → sogou → so360 → weixin → bing-int → shenma`
- **非中文查询** → 国际引擎优先：
  `ddg → google → brave → bing-int → yahoo → ecosia → google-hk → …`

## 引擎清单

| key | URL 模板 | 区域 | 可机读解析 |
|---|---|---|---|
| baidu | `baidu.com/s?wd={q}` | CN | ✅（易反爬） |
| bing-cn | `cn.bing.com/search?q={q}&ensearch=0` | CN | ✅ 最稳 |
| bing-int | `cn.bing.com/search?q={q}&ensearch=1` | CN网关 | ✅ |
| so360 | `so.com/s?q={q}` | CN | ✅ |
| sogou | `sogou.com/web?query={q}` | CN | ✅（索引微信文章） |
| weixin | `wx.sogou.com/weixin?type=2&query={q}` | CN | ✅ 公众号 |
| shenma | `m.sm.cn/s?q={q}` | CN(移动) | ✅ |
| google | `google.com/search?q={q}` | 全球 | ✅（可能撞墙） |
| google-hk | `google.com.hk/search?q={q}` | 全球 | ✅ |
| ddg | `duckduckgo.com/html/?q={q}` | 全球 | ✅ **最稳可解析** |
| yahoo | `search.yahoo.com/search?p={q}` | 全球 | ✅ |
| startpage | `startpage.com/sp/search?query={q}` | 全球 | ❌ JS挑战 |
| brave | `search.brave.com/search?q={q}` | 全球 | ✅ 独立索引 |
| ecosia | `ecosia.org/search?q={q}` | 全球 | ✅ |
| qwant | `qwant.com/?q={q}` | 欧盟 | ❌ JS重 |
| wolfram | `wolframalpha.com/input?i={q}` | 全球 | ❌ 知识计算非搜索 |

## 用法

```bash
cpk.py search "辅导员培训"                      # 只生成路由URL清单
cpk.py search "辅导员培训" --fetch --limit 5    # 实抓DDG/Bing并解析
cpk.py search "site:gov.cn 政策" --site gov.cn
cpk.py search "机器学习" --filetype pdf --time m
cpk.py search "deep learning" --engines ddg,brave --fetch
```

## 高级语法（多数引擎通用）

| 操作符 | 例 | 说明 |
|---|---|---|
| `site:` | `site:github.com python` | 站内搜 |
| `filetype:` | `filetype:pdf 报告` | 文件类型 |
| `"…"` | `"machine learning"` | 精确短语 |
| `-` | `python -snake` | 排除 |
| `OR` | `cat OR dog` | 或 |

时间过滤：`--time h|d|w|m|y`（Google 用 `tbs=qdr:`，DDG 用 `df=`，
Bing 用 `qft=interval`，套件自动映射）。

## DDG Bangs（直达站内）

`!gh` GitHub · `!so` StackOverflow · `!w` Wikipedia · `!yt` YouTube
（`engines.bang(query, "gh")` 生成）。

## 礼貌规则

- 引擎间 ≥1s 延迟（套件已内置）；3–4 个引擎为一批顺序执行；
- 403/429 时先访问引擎首页拿新 cookie 再重试一次，仍失败即放弃该引擎；
- cookie 仅内存中持有，会话结束即清，绝不落盘。
