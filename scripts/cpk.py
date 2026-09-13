#!/usr/bin/env python3
"""cpk.py — Crawler Power Kit: one CLI for the whole local crawling stack.

Subcommands
  doctor                 one-shot health check of the local toolchain
  search  <query>        16-engine search: print routed URLs; --fetch parses DDG/Bing
  quick   <url>          ladder-fetch one URL (urllib -> Crawl4AI -> Playwright)
  batch   <file>         concurrent layer-1 fetch of a URL list, with dedup
  render  <url>          force Playwright rendering (JS pages), optional screenshot
  md      <url>          Crawl4AI markdown extraction (LLM-ready output)
  paper   <title|doi>    Crossref/OpenAlex/arXiv/DOI-registry lookup
  verify  <refs file>    batch reference verification -> markdown report

Design rules (from the accumulated experience notes):
  - stdlib core, optional layers degrade gracefully instead of crashing;
  - every command prints machine-readable JSON with --json;
  - small-sample gate: batch caps by default; escalation is opt-in;
  - politeness: 0.5s delay, browser never used in bulk by default.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import re
import sys
import time

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engines                       # noqa: E402
import ladder                        # noqa: E402
import academic as acad              # noqa: E402

PY_VENV = r"C:\Users\yangc\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
NODE_EXE = r"C:\Users\yangc\.workbuddy\binaries\node\versions\22.22.2-2\node.exe"
FC_CLI = r"C:\Users\yangc\.workbuddy\binaries\node\workspace\node_modules\firecrawl-cli\dist\index.js"
PW_BROWSERS = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")


# ------------------------------------------------------------------ doctor

def _try(fn):
    try:
        return True, fn()
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def cmd_doctor(args) -> int:
    report: dict = {"python": sys.version.split()[0], "checks": [], "ok": 0, "warn": 0}

    def add(name, ok, detail, warn_only=False):
        report["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)})
        report["warn" if (not ok and warn_only) or (ok and warn_only is None) else
               ("ok" if ok else "warn")] = report.get("warn", 0)

    # 1. stdlib net
    ok, det = _try(lambda: ladder.http_get("https://example.com")[0])
    add("network/https", ok, det)

    # 2. optional python layers
    def _ver(m):
        mod = __import__(m)
        v = getattr(mod, "__version__", None)
        if not v:
            v = getattr(getattr(mod, "__version__", None), "__version__", None)
        return v or "imported"
    for mod in ("crawl4ai", "crawlee", "scrapy", "playwright", "firecrawl",
                "bs4", "lxml", "httpx", "aiohttp"):
        ok, det = _try(lambda m=mod: _ver(m))
        add(f"pip/{mod}", ok, det, warn_only=True)

    # 3. playwright browsers installed
    pw_ok = os.path.isdir(PW_BROWSERS) and any("chromium" in d for d in os.listdir(PW_BROWSERS)) \
        if os.path.isdir(PW_BROWSERS) else False
    add("playwright/chromium", pw_ok,
        PW_BROWSERS if pw_ok else "not found — run: playwright install chromium",
        warn_only=True)

    # 4. firecrawl CLI + key
    fc_ok = os.path.isfile(FC_CLI)
    fc_key = bool(os.environ.get("FIRECRAWL_API_KEY"))
    add("firecrawl/cli", fc_ok, f"v1.22.0 at workspace" if fc_ok else FC_CLI, warn_only=True)
    add("firecrawl/api-key", fc_key,
        "set" if fc_key else "unset — cloud features need FIRECRAWL_API_KEY; "
        "Crawl4AI covers the no-key path", warn_only=True)

    # 5. academic APIs
    for name, fn in (("api/crossref", lambda: acad._get("https://api.crossref.org/works?rows=1")),
                     ("api/openalex", lambda: acad._get("https://api.openalex.org/works?per-page=1")),
                     ("api/arxiv", lambda: acad._get("https://export.arxiv.org/api/query?id_list=1706.03762"))):
        ok, det = _try(fn)
        add(name, ok, "reachable" if ok else det, warn_only=True)

    report["ok"] = sum(1 for c in report["checks"] if c["ok"])
    report["warn"] = len(report["checks"]) - report["ok"]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for c in report["checks"]:
            mark = "OK " if c["ok"] else "MISS"
            print(f"[{mark}] {c['name']:<22} {c['detail'][:80]}")
        print(f"\n{report['ok']}/{len(report['checks'])} checks passed. "
              f"Interpreter: {sys.executable}")
    return 0


# ------------------------------------------------------------------ search

def cmd_search(args) -> int:
    keys = (args.engines.split(",") if args.engines
            else engines.route(args.query))
    urls = {}
    for k in keys:
        k = k.strip()
        if k not in engines.ENGINES:
            print(f"unknown engine: {k}", file=sys.stderr)
            continue
        urls[k] = engines.build_url(k, args.query, site=args.site,
                                    filetype=args.filetype, time=args.time,
                                    exact=args.exact)
    if not args.fetch:
        if args.json:
            print(json.dumps({"query": args.query, "urls": urls}, ensure_ascii=False, indent=2))
        else:
            print(f"query: {args.query}\n")
            for k, u in urls.items():
                print(f"  [{k}] {u}")
        return 0

    # --fetch: parse the parseable engines
    hits = []
    for k, u in urls.items():
        if k not in engines.PARSERS:
            continue
        try:
            status, html, _ = ladder.http_get(u)
            got = engines.PARSERS[k](html, limit=args.limit)
            for h in got:
                h["engine"] = k
            hits.extend(got)
        except Exception as e:  # noqa: BLE001
            print(f"[{k}] fetch failed: {e}", file=sys.stderr)
        time.sleep(1.0)
    # cross-engine dedup by url
    seen, uniq = set(), []
    for h in hits:
        if h["url"] not in seen:
            seen.add(h["url"])
            uniq.append(h)
    uniq = uniq[: args.limit]
    if args.json:
        print(json.dumps(uniq, ensure_ascii=False, indent=2))
    else:
        for i, h in enumerate(uniq, 1):
            print(f"{i}. [{h['engine']}] {h['title']}\n   {h['url']}")
            if h["snippet"]:
                print(f"   {h['snippet'][:150]}")
    return 0 if uniq else 1


# ------------------------------------------------------------------ quick / batch

def _print_fetch(res, json_mode=False):
    if json_mode:
        print(json.dumps(dataclasses.asdict(res), ensure_ascii=False, indent=2))
        return
    print(f"layer={res.layer}  status={res.status}  {res.elapsed_ms}ms  "
          f"text={len(res.text)}ch  bytes={res.html_bytes}")
    if res.final_url and res.final_url != res.url:
        print(f"redirected -> {res.final_url}")
    if res.notes:
        print("notes: " + "; ".join(res.notes))
    if res.title:
        print(f"title: {res.title}")
    if res.text:
        print("\n" + res.text[:1500] + ("\n…[truncated]" if len(res.text) > 1500 else ""))
    if not res.ok():
        print(f"ERROR: {res.error}")


def cmd_quick(args) -> int:
    res = ladder.fetch(args.url, allow_browser=not args.no_browser)
    _print_fetch(res, args.json)
    return 0 if res.ok() else 1


def cmd_batch(args) -> int:
    raw = [ln.strip() for ln in open(args.file, encoding="utf-8")
           if ln.strip() and not ln.startswith("#")]
    urls = ladder.dedup_urls(raw)
    print(f"{len(raw)} urls -> {len(urls)} after dedup", file=sys.stderr)
    results = ladder.fetch_many(urls, concurrency=args.concurrency,
                                delay=args.delay, allow_browser=False)
    ok_n = sum(1 for r in results if r.ok())
    rows = [{"url": r.url, "ok": r.ok(), "layer": r.layer, "status": r.status,
             "title": r.title, "chars": len(r.text), "ms": r.elapsed_ms,
             "error": r.error} for r in results]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            mark = "OK " if r["ok"] else "FAIL"
            print(f"[{mark}] {r['status'] or '---'} {r['layer']:<9} "
                  f"{r['chars']:>7}ch {r['ms']:>6}ms  {r['url']}")
    print(f"\n{ok_n}/{len(urls)} fetched OK. Failed URLs -> retry singly with `cpk quick <url>` "
          f"(browser escalation happens there).", file=sys.stderr)
    return 0 if ok_n == len(urls) else 1


# ------------------------------------------------------------------ render / md

def cmd_render(args) -> int:
    t0 = time.time()
    res = ladder._playwright_fetch(args.url, shot_path=args.screenshot)
    if res is None:
        print(json.dumps({"error": "playwright layer unavailable"}, ensure_ascii=False))
        return 2
    res.elapsed_ms = int((time.time() - t0) * 1000)
    _print_fetch(res, args.json)
    return 0 if res.ok() else 1


def cmd_md(args) -> int:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        async def _run():
            bcfg = BrowserConfig(browser_type="builtin", headless=True)
            ccfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
            crawler = AsyncWebCrawler(config=bcfg)
            await crawler.start()
            try:
                return await crawler.arun(url=args.url, config=ccfg)
            finally:
                try:
                    await crawler.close()
                except Exception:  # noqa: BLE001
                    pass  # Windows driver-exit noise

        r = asyncio.run(_run())
        md = re.sub(r"\n{3,}", "\n\n", getattr(r, "markdown", "") or "").strip()
        if args.json:
            print(json.dumps({"url": args.url, "markdown": md,
                              "title": (getattr(r, "metadata", None) or {}).get("title", "")},
                             ensure_ascii=False, indent=2))
        else:
            print(md)
        return 0 if md else 1
    except ImportError:
        print("crawl4ai not installed in this interpreter — run under the managed venv:\n"
              f"  {PY_VENV} cpk.py md <url>", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"crawl4ai failed: {e}", file=sys.stderr)
        return 1


# ------------------------------------------------------------------ paper / verify

def cmd_paper(args) -> int:
    is_doi = re.match(r"^10\.\d{4,9}/", args.query or "")
    found = acad.find_paper(title="" if is_doi else args.query,
                            doi=args.query if is_doi else "")
    if args.json:
        print(json.dumps(found, ensure_ascii=False, indent=2))
    else:
        if "doi_registry" in found:
            st = found["doi_registry"]
            print(f"DOI registry: {'EXISTS' if st['ok'] else 'NOT FOUND'} ({st['doi']})")
        if not found["hits"]:
            print("no hits in crossref/openalex/arxiv")
            return 1
        for h in found["hits"]:
            src = h.pop("source", "?")
            au = h.pop("authors", "")
            print(f"[{src}] {h.get('title', '')}")
            line2 = []
            for k in ("year", "venue", "doi", "arxiv_id", "volume", "issue", "pages", "cited_by"):
                if h.get(k):
                    line2.append(f"{k}={h[k]}")
            print("    " + "  ".join(line2))
            if au:
                print(f"    authors: {au[:100]}")
    return 0


def cmd_verify(args) -> int:
    from verify_refs import DEMO_REFS, load_refs, verify_all, render_report
    if args.demo:
        refs = [dict(r, raw=r["title"]) for r in DEMO_REFS]
        src = "built-in demo"
    else:
        refs = load_refs(args.input)
        src = args.input
    results = verify_all(refs, args.mailto)
    report = render_report(results, src)
    out = args.output or "reference-verification-report.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nreport -> {out}", file=sys.stderr)
    bad = sum(1 for r in results if r["status"] in ("MISMATCH", "NOT_FOUND"))
    return 1 if bad else 0


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(prog="cpk", description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor")

    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--engines", help="comma list, e.g. ddg,bing-cn,baidu")
    s.add_argument("--site"), s.add_argument("--filetype"), s.add_argument("--time", help="h|d|w|m|y")
    s.add_argument("--exact", action="store_true")
    s.add_argument("--fetch", action="store_true", help="actually fetch & parse DDG/Bing HTML")
    s.add_argument("--limit", type=int, default=10)

    q = sub.add_parser("quick")
    q.add_argument("url")
    q.add_argument("--no-browser", action="store_true", help="stop at layer 2")

    b = sub.add_parser("batch")
    b.add_argument("file", help="UTF-8 text file, one URL per line")
    b.add_argument("--concurrency", type=int, default=6)
    b.add_argument("--delay", type=float, default=0.5)

    r = sub.add_parser("render")
    r.add_argument("url")
    r.add_argument("--screenshot", help="save PNG evidence")

    m = sub.add_parser("md")
    m.add_argument("url")

    p = sub.add_parser("paper")
    p.add_argument("query", help="paper title or 10.x/xxx DOI")

    v = sub.add_parser("verify")
    v.add_argument("input", nargs="?", default=None, help="refs .txt/.md/.json")
    v.add_argument("-o", "--output")
    v.add_argument("--mailto")
    v.add_argument("--demo", action="store_true", help="self-test with built-in references")

    args = ap.parse_args()
    if not args.json:
        args.json = getattr(args, "json", False)
    fn = {"doctor": cmd_doctor, "search": cmd_search, "quick": cmd_quick,
          "batch": cmd_batch, "render": cmd_render, "md": cmd_md,
          "paper": cmd_paper, "verify": cmd_verify}[args.cmd]
    sys.exit(fn(args))


if __name__ == "__main__":
    main()
