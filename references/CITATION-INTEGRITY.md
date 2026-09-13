# Citation Integrity — Anti-Hallucination SOP

Distilled from 《杜绝与纠正"幻觉参考文献"的经验总结》(grant-application practice) and merged with the API recipes in [ACADEMIC-API.md](ACADEMIC-API.md).

## Hallucination types to detect

1. **纯虚构型** — plausible title assembled from domain buzzwords; exists in no database.
2. **错配型（拼盘）** — real title, wrong authors/year/volume/issue/pages.
3. **DOI 伪造型** — DOI present but resolves to an unrelated paper or dead link.
4. **标准/法规文号捏造型** — standard name right, number invented or wrong.

Root cause: an LLM completes "author + title + journal + year + DOI" by probability, not retrieval. Any reference produced from memory is unverified until checked.

## Verification SOP (per reference)

| Step | Action | Standard | Branch |
|---|---|---|---|
| 1 | Extract reference list + in-text anchor positions | — | — |
| 2 | Database exact search | EN: Crossref/OpenAlex (API) or Google Scholar/IEEE Xplore; CN: CNKI/万方/维普/百度学术 篇名精确检索 | empty → hallucination → step 4 |
| 3 | Metadata cross-check | Title, author order, journal, year, volume, issue, pages — all six elements must match. DOI resolves (`https://doi.org/<DOI>`) to the same work | pass → keep + record DOI; fail → step 4 |
| 4 | Replace with true source | Locate the specific claim the citation supports; find a real, highly-cited, authoritative paper or current standard covering the same point; verify IT through steps 2–3 | never patch volume/page numbers by guessing |
| 5 | Emit verification report | Per-reference status table: verified / replaced / dropped, with database checked and match details | done |

## Rules

- **Never invent or "correct" identifiers from memory.** A wrong-but-plausible DOI is worse than no DOI.
- **Replacement beats repair.** When a citation is hallucinated, substitute a verified classic (e.g., a field-defining review) that genuinely supports the claim — do not fabricate metadata to make the fake one fit.
- **Batch tooling**: run `scripts/verify_refs.py` on the final reference list before delivery. It queries Crossref per reference and reports exact-match / fuzzy-match / not-found with per-element mismatch details.
- **Chinese references**: exact 篇名 search in CNKI/万方/维普 via public pages; empty result ⇒ hallucination. Pre-2017 Chinese journals often have no DOI — record "该刊该年未注册 DOI" plus a CNKI/journal-site link instead of forcing a DOI.
- **Cross-validation channel priority**: DOI resolution → publisher official page > Google Scholar (EN) > CNKI (CN) > journal site / napstic.cn. On page-number conflicts, CNKI/publisher wins; faculty homepages and repost sites never override.
- **Author-dimension tasks**: run the disambiguation gate in [AUTHOR-SURVEY.md](AUTHOR-SURVEY.md) before verification — verifying metadata of the wrong author's paper is still a hallucinated entry.
- **Standards/regulations**: verify number and status on openstd.samr.gov.cn (国标), ministry standard libraries (行标), or gov.cn (法规/国务院令) — never from memory.
- **Unverifiable but plausibly real**: mark explicitly as unverified in the output, or omit. The user decides; the agent never silently includes it.
- **Retraction check** for high-stakes citations; note corrections.

## Output artifact

Every research deliverable that contains references must end with a verification table:

```markdown
| # | Reference | Database checked | Result | Action |
|---|---|---|---|---|
| 1 | Lynch JP, ... (2006) | Crossref DOI | all six elements match | kept, DOI recorded |
| 2 | (fabricated title) | Crossref + CNKI | not found | replaced with [verified ref] |
```
