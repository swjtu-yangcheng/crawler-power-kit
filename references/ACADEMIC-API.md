# Academic API Recipes

Concrete, stdlib-only recipes for scholarly discovery and verification. All work via `curl` or `urllib`. Rate limits: Crossref polite pool needs a mailto; OpenAlex recommends one too. Keep request rates modest (≤3/s).

## Crossref (metadata + DOI verification)

```bash
# Search by bibliographic string (title-ish)
curl -sL "https://api.crossref.org/works?query.bibliographic=<TITLE>&rows=3&mailto=research@example.com"

# Verify a known DOI (exact record)
curl -sL "https://api.crossref.org/works/<DOI>"

# Fuzzy title match, get top candidates with scores
curl -sL "https://api.crossref.org/works?query.title=<TITLE>&rows=5&select=DOI,title,author,container-title,issued,volume,issue,page&mailto=research@example.com"
```

Check: returned `title` ≈ claimed title; `author` order matches; `container-title` = claimed journal; `issued` year matches; volume/issue/page match. Mismatch on any element → treat the reference as suspect (mismatch-type hallucination).

## OpenAlex (discovery + citation graph, broad coverage)

```bash
# Title search
curl -sL "https://api.openalex.org/works?search=<TITLE>&per-page=5&mailto=research@example.com"

# Filter by field/venue/year
curl -sL "https://api.openalex.org/works?filter=publication_year:2020-2026,concepts.id:C121332964&per-page=25"

# Forward citations of a work
curl -sL "https://api.openalex.org/works?filter=cites:W<WORK_ID>&per-page=25"
```

Fields of interest: `doi`, `title`, `authorships[].author.display_name`, `primary_location.source.display_name`, `publication_year`, `cited_by_count`, `ids` (includes DOI, PMID, MAG).

## arXiv (preprints)

```bash
curl -sL "http://export.arxiv.org/api/query?search_query=all:<TERMS>&max_results=20"
```

Returns Atom XML: `<entry>` → `<title>`, `<author><name>`, `<published>`, `<id>` (arXiv id / DOI link). Distinguish preprint date from journal issue date.

## Semantic Scholar (citation counts, abstracts, references)

```bash
# Paper lookup by title
curl -sL "https://api.semanticscholar.org/graph/v1/paper/search?query=<TITLE>&limit=5&fields=title,authors,year,venue,citationCount,externalIds,abstract"

# Lookup by DOI
curl -sL "https://api.semanticscholar.org/graph/v1/paper/DOI:<DOI>?fields=title,authors,year,venue,citationCount"
```

Unauthenticated limits are tight; prefer Crossref/OpenAlex for bulk, S2 for citation-count and abstract enrichment.

## Chinese literature (no open CNKI API)

- No public CNKI/Wanfang/VIP API exists for full metadata. Options in order:
  1. Search the exact 篇名 via WebSearch with `site:` filters and read the CNKI/万方 detail page (public abstract pages are usually reachable).
  2. Cross-check via Baidu Xueshu (`xueshu.baidu.com`) search snippets.
  3. For engineering standards: verify on 国家标准全文公开系统 (`openstd.samr.gov.cn`), 住建部/交通部 standard libraries.
- Verification standard for Chinese references: 篇名 exact match AND 期刊名 AND 年份 AND 作者 order all confirmed from a public database page. Exact-title search returning empty → hallucination; drop or replace.

## Standards / regulations (China)

- 国家标准: `openstd.samr.gov.cn` — check 标准号 (e.g. `GB 42590-2023`) and status (现行/废止/被替代).
- 行业标准: 住建部 (JGJ/CJJ), 交通部 (JTG) official standard libraries.
- 法律法规/国务院文件: 中国政府网 `www.gov.cn` 政务公开 — verify 公文文号 and 发布日期.
- Never generate a standard/document number from memory; always verify against the official source.

## Retraction / correction check

For high-stakes citations, check status via Crossref (`update-to` relations), OpenAlex, or Retraction Watch. Note corrected/retracted status in the source record.

## Typical sequence for a literature survey

```text
query family design (EN + CN terms)
  → OpenAlex/Crossref discovery (broad, filterable)
  → arXiv for preprints, S2 for citation counts
  → deduplicate by DOI
  → for each key paper: verify metadata via Crossref DOI lookup
  → CNKI/百度学术 page check for Chinese-language items
  → produce structured evidence table with verified fields only
```

## 与本套件的绑定

上述配方已固化为 `scripts/academic.py`（stdlib only）并通过
`cpk.py paper "标题或DOI"` 一键调用：DOI 注册表（doi.org handle API）→
Crossref → OpenAlex → arXiv 依次回退。arXiv 的四个陷阱（HTTP-200 Error 条目、
feed link 误判、id 版本后缀、硬换行）已在代码内处理。
