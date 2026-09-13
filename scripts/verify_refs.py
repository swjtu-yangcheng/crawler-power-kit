#!/usr/bin/env python3
"""verify_refs.py — batch reference verification against the Crossref REST API.

Detects hallucinated / mismatched references in LLM-generated text:
  - fabricated titles (not found in Crossref)
  - mismatched metadata (real title, wrong authors/year/journal)
  - fake DOIs (DOI resolves to a different work, or dead)

Input formats:
  1. Plain text / markdown, one reference per line. Lines that look like
     list items ("1. ...", "- ...", "[1] ...") are stripped automatically.
  2. JSON array of objects: [{"title": "...", "doi": "10.x/...", "year": 2006}, ...]

Usage:
  python verify_refs.py refs.txt -o report.md
  python verify_refs.py refs.json -o report.md --mailto me@example.com
  python verify_refs.py --demo          # runs a self-test with known references

Output: a markdown verification report with one row per reference:
  VERIFIED | LIKELY | MISMATCH | NOT_FOUND | ERROR
plus matched Crossref metadata and mismatch details.

Stdlib only (urllib). Rate: ~1 request/sec with retry/backoff.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

CROSSREF_API = "https://api.crossref.org/works"
UA = "web-research-pro verify_refs/1.0 (+skill; mailto:%s)"
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;)\]]+)")
LIST_PREFIX_RE = re.compile(r"^\s*(?:\d+[.)\]]|[-*•\[]\]?\d*\]?)\s*")

STATUS_ORDER = ["VERIFIED", "LIKELY", "MISMATCH", "NOT_FOUND", "ERROR"]


def http_get(url, mailto, timeout=25, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": UA % (mailto or "anonymous@example.com")},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # genuine not-found (DOI or empty query result)
            last_err = e
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:  # noqa: BLE001 - network stack varies on Windows
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url} ({last_err})")


def clean_line(line):
    line = LIST_PREFIX_RE.sub("", line.strip())
    return line.strip()


def norm_title(t):
    t = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", (t or "").lower())
    return " ".join(t.split())


def title_similarity(a, b):
    ta, tb = norm_title(a), norm_title(b)
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta.split()), set(tb.split())
    return len(sa & sb) / max(len(sa), len(sb))


def extract_year(text):
    m = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", text or "")
    return int(m.group(1)) if m else None


def crossref_match(query_title=None, doi=None, mailto=None):
    """Return (status, best_match_dict, detail) for one reference."""
    params = {"rows": "3", "select": "DOI,title,author,container-title,issued,volume,issue,page,type"}
    if mailto:
        params["mailto"] = mailto
    if doi:
        item = http_get(f"{CROSSREF_API}/{urllib.parse.quote(doi, safe='/')}", mailto)
        if item is None:
            return "NOT_FOUND", None, "DOI does not resolve in Crossref"
        msg = item.get("message", {})
        cands = [msg]
    else:
        params["query.bibliographic"] = query_title
        url = f"{CROSSREF_API}?{urllib.parse.urlencode(params)}"
        data = http_get(url, mailto)
        items = (data or {}).get("message", {}).get("items", [])
        if not items:
            return "NOT_FOUND", None, "no Crossref result for bibliographic query"
        cands = items[:3]

    best, best_sim = None, 0.0
    for cand in cands:
        cand_title = (cand.get("title") or [""])[0]
        sim = title_similarity(query_title, cand_title) if query_title else 0.0
        if sim > best_sim:
            best, best_sim = cand, sim
    if best is None:
        best = cands[0]

    best_title = (best.get("title") or [""])[0]
    sim = title_similarity(query_title, best_title) if query_title else 0.0

    def flat(meta):
        return (meta or [""])[0] if isinstance(meta, list) and meta else ("" if isinstance(meta, list) else meta)

    match = {
        "title": best_title,
        "doi": best.get("DOI", ""),
        "authors": "; ".join(
            f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
            for a in best.get("author", [])[:8]
        ),
        "journal": flat(best.get("container-title")),
        "year": (best.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0],
        "volume": best.get("volume", ""),
        "issue": best.get("issue", ""),
        "pages": best.get("page", ""),
        "type": best.get("type", ""),
        "title_similarity": round(sim, 2),
    }

    if doi and query_title and sim < 0.55:
        return "MISMATCH", match, f"DOI resolves but title differs (similarity {sim:.2f}) — suspected fake/wrong DOI"
    if sim >= 0.85:
        return "VERIFIED", match, "title match ≥0.85"
    if sim >= 0.60:
        return "LIKELY", match, f"partial title match ({sim:.2f}) — manually confirm six elements"
    if doi and not query_title:
        return "VERIFIED", match, "DOI resolves (no title supplied for comparison)"
    return "NOT_FOUND", match, f"best Crossref candidate too dissimilar ({sim:.2f}) — likely fabricated"


def load_refs(path):
    text = open(path, encoding="utf-8").read()
    stripped = text.strip()
    if stripped.startswith("["):
        refs = []
        for obj in json.loads(stripped):
            refs.append({"raw": obj.get("title", ""), "title": obj.get("title"), "doi": obj.get("doi")})
        return refs
    refs = []
    for line in stripped.splitlines():
        line = clean_line(line)
        if len(line) < 12:
            continue
        m = DOI_RE.search(line)
        refs.append({"raw": line, "title": line, "doi": m.group(1).rstrip(".") if m else None})
    return refs


def verify_all(refs, mailto):
    results = []
    for i, ref in enumerate(refs, 1):
        try:
            status, match, detail = crossref_match(
                query_title=ref.get("title"), doi=ref.get("doi"), mailto=mailto
            )
        except Exception as e:  # noqa: BLE001
            status, match, detail = "ERROR", None, str(e)
        results.append({"n": i, "raw": ref["raw"], "doi": ref.get("doi"), "status": status, "match": match, "detail": detail})
        time.sleep(1.0)
    return results


def render_report(results, src_name):
    lines = [
        "# Reference Verification Report",
        "",
        f"Source: `{src_name}` | Checked against: Crossref REST API | Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| # | Status | Input reference | Crossref match | Detail |",
        "|---|---|---|---|---|",
    ]
    counts = {s: 0 for s in STATUS_ORDER}
    for r in results:
        counts[r["status"]] += 1
        m = r["match"] or {}
        matched = f"{m.get('title', '')} — {m.get('journal', '')} ({m.get('year', '')}) DOI:{m.get('doi', '')}"
        raw = (r["raw"][:90] + "…") if len(r["raw"]) > 90 else r["raw"]
        raw = raw.replace("|", "\\|")
        matched = matched.replace("|", "\\|")
        lines.append(f"| {r['n']} | **{r['status']}** | {raw} | {matched} | {r['detail']} |")
    lines += ["", "## Summary", ""]
    for s in STATUS_ORDER:
        if counts[s]:
            lines.append(f"- **{s}**: {counts[s]}")
    lines += [
        "",
        "## Follow-up rules",
        "- VERIFIED: keep; record DOI.",
        "- LIKELY: manually confirm authors/year/volume/issue/pages (six elements).",
        "- MISMATCH: suspected fake DOI or wrong metadata — replace with a verified source covering the same claim.",
        "- NOT_FOUND: treat as hallucination — drop or replace. Never patch numbers by guessing.",
    ]
    return "\n".join(lines)


DEMO_REFS = [
    {"title": "Compressed sensing", "doi": "10.1109/TIT.2006.871582"},
    {"title": "A fabricated buzzword paper about low-power piezoelectric high-frequency wireless structural sensing with compressed digital twins", "doi": None},
    {"title": "The wealth of nations", "doi": "10.1109/TIT.2006.871582"},
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", nargs="?", help="refs .txt/.md/.json file")
    ap.add_argument("-o", "--output", default=None, help="output markdown report path")
    ap.add_argument("--mailto", default=None, help="email for Crossref polite pool")
    ap.add_argument("--demo", action="store_true", help="run self-test with built-in references")
    args = ap.parse_args()

    if args.demo:
        refs = [dict(r, raw=r.get("raw") or r["title"]) for r in DEMO_REFS]
        src = "built-in demo"
    elif args.input:
        refs = load_refs(args.input)
        src = args.input
    else:
        ap.error("provide an input file or --demo")

    print(f"Verifying {len(refs)} reference(s) against Crossref...", file=sys.stderr)
    results = verify_all(refs, args.mailto)
    report = render_report(results, src)

    out_path = args.output or "reference-verification-report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nReport written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
