# EVIDENCE-PIPELINE — 证据记录、去重与分级

合并自 web-research-pro EVIDENCE-PIPELINE.md 与 crawler-supervisor EVIDENCE.md。

## 信源记录 schema（每条保留的证据）

```yaml
url:
canonical_url:
title:
publisher_or_site:
source_type:            # journal | standard | gov | news | docs | forum | dataset | preprint | report
published_at:
updated_at:
retrieved_at:
author:
language:
access_method:          # websearch | webfetch | curl | python | browser | api
layer:                  # urllib | crawl4ai | playwright（哪个层抓到的）
primary_or_secondary:
tier:                   # A | B | C | D
relevant_claims:        # 该源支撑哪些论点
evidence_summary:
structured_fields:      # 数据集场景的提取值
doi_or_identifier:
confidence:             # high | medium | low
notes:                  # 撤稿状态、付费墙、矛盾点
```

机器可读版：`assets/source-record.schema.json`。

## 去重顺序（严格按此序）

1. DOI / 稳定标识符
2. canonical URL（`rel=canonical`）
3. 归一化 URL（去 utm_*/fbclid/sid/会话参数、尾斜杠、fragment——
   `ladder.dedup_urls()` 已实现）
4. 精确标题 + 出版方
5. 标题/正文近似重复（内容哈希）
6. 转载关系（同一上游通稿）

**十篇转载同一通稿 = 一个独立信源，不是十个确认。**

## 证据分级

- **A（一手）**：官方文档/标准/政府数据/同行评审论文/原始数据集
- **B（强二手）**：可靠媒体/机构综述/公认技术分析
- **C（社区经验）**：论坛/评论/社交媒体——证明"有人这么体验"，不证明技术因果
- **D（弱聚合）**：SEO 聚合站/镜像/无源转载——仅作线索

## 主张分类与证据要求

| 主张类 | 例 | 要求 |
|---|---|---|
| 事实性 | 发布日期、价格、测量性能、法规原文 | 直接一手证据 |
| 解释性 | "这可能是主因"、"用户普遍偏好" | 多个相关观察 + 明确标注为解释 |
| 体验性 | 耐用性吐槽、社区情绪 | C级可为体验主证据，不可作因果证据 |

## 置信标签

- **high**：直接一手、当前、无歧义
- **medium**：强二手或部分三角验证
- **low**：弱/间接/歧义，或仅社区证据支撑事实主张

不要把置信度换算成伪精确百分比。

## 抓取质量检查（每页）

标记并重路由：CAPTCHA页 / 登录壳 / JS空壳 / 被重定向走（记录最终URL）/
纯导航无正文 / 字段截断 / 错误语言区域 / 字段数异常（schema漂移）。

## 矛盾处理

1. 核对两边版本与日期；2. 核对单位/分母/地域/修订；3. 找各自上游一手源；
4. 评估独立性；5. 未解决则**两个都保留**并标注分歧，绝不悄悄站队。

## 引用方式

优先转述+引用；仅当措辞本身重要时短引原文。
