#!/usr/bin/env python3
"""ladder.py — the escalation ladder, as executable code.

Implements the core routing doctrine of the crawler toolkit:

    Layer 1  urllib/httpx direct GET      (fastest, no JS)
    Layer 2  Crawl4AI  (optional dep)     (JS optional, LLM-ready markdown, cache)
    Layer 3  Playwright (optional dep)    (full browser: JS, clicks, screenshots)

Each layer is tried only when the previous one *demonstrably fails*:
empty body, JS-shell detection, or HTTP 403/429/5xx. Never escalate
because a stronger tool exists.

Stdlib-only fallback everywhere: if crawl4ai/playwright are not importable,
the ladder degrades to urllib with a clear status note instead of crashing.
"""
from __future__ import annotations

import gzip
import io
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict

from engines import UA

TIMEOUT = 25
MAX_HTML = 8 * 1024 * 1024  # 8 MB safety cap

_SHELL_MARKERS = (
    "enable javascript", "please enable js", "checking your browser",
    "just a moment...", "cf-browser-verification", "访问过于频繁",
)


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    status: int = 0
    layer: str = ""            # urllib | crawl4ai | playwright
    title: str = ""
    text: str = ""             # extracted main text
    html_bytes: int = 0
    elapsed_ms: int = 0
    error: str = ""
    notes: list = field(default_factory=list)

    def ok(self) -> bool:
        return self.status == 200 and len(self.text) > 120 and not self.error


# ---------------------------------------------------------------- layer 1

def http_get(url: str, timeout: int = TIMEOUT, no_proxy: bool = False) -> tuple[int, str, str]:
    """Raw GET via urllib. Returns (status, html, final_url). Raises on network error.

    no_proxy=True bypasses environment proxies — often the fix when the local
    proxy returns 502/tunnel errors for domestic sites that are faster direct.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip",
    })
    if no_proxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        resp = opener.open(req, timeout=timeout)
    else:
        resp = urllib.request.urlopen(req, timeout=timeout)
    with resp:
        raw = resp.read(MAX_HTML)
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read(MAX_HTML)
        charset = resp.headers.get_content_charset() or ""
        html = raw.decode(charset or "utf-8", "replace")
        return resp.status, html, resp.geturl()


_PROXY_ERR = re.compile(r"tunnel|proxy|502|503", re.I)


def strip_tags(html: str) -> str:
    html = re.sub(r"<(script|style|noscript|svg|header|footer|nav|aside)[^>]*>.*?</\1>",
                  " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


def looks_like_js_shell(html: str) -> bool:
    """True only for genuine JS shells: big HTML but almost no text,
    or an explicit challenge marker. Small static pages (example.com)
    must NOT trigger escalation."""
    low = html.lower()
    if any(m in low for m in _SHELL_MARKERS):
        return True
    return len(html) > 50_000 and len(strip_tags(html)) < 200


def extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if not m:
        return ""
    t = re.sub(r"\s+", " ", m.group(1)).strip()
    return re.sub(r"\s*[-|–]\s*(首页|官网|Home).*$", "", t)


# ---------------------------------------------------------------- ladder

def fetch(url: str, allow_browser: bool = True) -> FetchResult:
    """Run the full ladder for one URL and return the best result."""
    t0 = time.time()
    res = FetchResult(url=url)

    # ---- layer 1: urllib (with proxy-fallback direct retry)
    try:
        status, html, final = http_get(url)
        res.status, res.final_url, res.layer = status, final, "urllib"
        res.html_bytes, res.title = len(html), extract_title(html)
        res.text = strip_tags(html)
        if status == 200 and not looks_like_js_shell(html):
            res.elapsed_ms = int((time.time() - t0) * 1000)
            return res
        res.notes.append("layer1: JS shell or non-200 -> escalate")
    except urllib.error.HTTPError as e:
        res.status, res.error = e.code, f"HTTP {e.code}"
        if e.code not in (403, 429, 405, 503):
            res.elapsed_ms = int((time.time() - t0) * 1000)
            return res  # 404 etc: escalating will not help
        res.notes.append(f"layer1: HTTP {e.code} -> escalate")
    except Exception as e:  # noqa: BLE001
        res.error = f"layer1: {e}"
        res.notes.append("layer1: network error")
        # proxy tunnel failure -> one direct-connection retry (domestic sites
        # are usually faster and cleaner without the local proxy)
        if _PROXY_ERR.search(str(e)):
            try:
                status, html, final = http_get(url, no_proxy=True)
                res.status, res.final_url, res.layer = status, final, "urllib-direct"
                res.html_bytes, res.title = len(html), extract_title(html)
                res.text = strip_tags(html)
                res.error = ""
                if status == 200 and not looks_like_js_shell(html):
                    res.elapsed_ms = int((time.time() - t0) * 1000)
                    res.notes.append("layer1-direct: proxy bypassed, succeeded")
                    return res
                res.notes.append("layer1-direct: JS shell or non-200 -> escalate")
            except Exception as e2:  # noqa: BLE001
                res.error = f"layer1(+direct): {e2}"

    # ---- layer 2: Crawl4AI (needs deps; degrades gracefully)
    try:
        res2 = _crawl4ai_fetch(url)
        if res2 is not None:
            res2.elapsed_ms = int((time.time() - t0) * 1000)
            res2.notes = res.notes + res2.notes
            return res2
    except Exception as e:  # noqa: BLE001
        res.notes.append(f"layer2 crawl4ai unavailable: {type(e).__name__}")

    # ---- layer 3: Playwright (needs deps + browser; degrades gracefully)
    if allow_browser:
        try:
            res3 = _playwright_fetch(url)
            if res3 is not None:
                res3.elapsed_ms = int((time.time() - t0) * 1000)
                res3.notes = res.notes + res3.notes
                return res3
        except Exception as e:  # noqa: BLE001
            res.notes.append(f"layer3 playwright unavailable: {type(e).__name__}")

    res.elapsed_ms = int((time.time() - t0) * 1000)
    return res


def _crawl4ai_fetch(url: str, budget_s: int = 60) -> FetchResult | None:
    """Layer 2 — Crawl4AI in no-playwright mode first (fast, cached, markdown).

    Hard time budget (default 60s): first runs may need to fetch the builtin
    browser; beyond the budget we give up cleanly instead of hanging forever.
    """
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    except ImportError:
        return None

    import asyncio

    async def _run():
        bcfg = BrowserConfig(browser_type="builtin", headless=True)  # try without playwright first
        ccfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
        crawler = AsyncWebCrawler(config=bcfg)
        await crawler.start()
        try:
            return await crawler.arun(url=url, config=ccfg)
        finally:
            try:
                await crawler.close()
            except Exception:  # noqa: BLE001
                pass  # Windows driver-exit noise; results are intact

    try:
        r = asyncio.run(asyncio.wait_for(_run(), timeout=budget_s))
    except (asyncio.TimeoutError, TimeoutError):
        return None
    except Exception:
        # BrowserConfig("builtin") may fail if extra deps missing -> give up cleanly
        return None
    if not getattr(r, "success", False):
        return None
    res = FetchResult(url=url, final_url=getattr(r, "url", url), status=200,
                      layer="crawl4ai", html_bytes=len(getattr(r, "html", "") or ""))
    res.title = getattr(r, "metadata", {}).get("title", "") if getattr(r, "metadata", None) else ""
    res.text = re.sub(r"\n{3,}", "\n\n", getattr(r, "markdown", "") or "").strip()
    if not res.title:
        res.title = extract_title(getattr(r, "html", "") or "")
    res.notes.append("layer2: crawl4ai succeeded")
    return res


def _playwright_fetch(url: str, shot_path: str | None = None) -> FetchResult | None:
    """Layer 3 — real Chromium via Playwright. Optional screenshot for evidence."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=UA, locale="zh-CN")
            page.goto(url, timeout=45_000, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)  # let late JS settle
            html = page.content()
            res = FetchResult(url=url, final_url=page.url, status=200, layer="playwright",
                              html_bytes=len(html))
            res.title = page.title() or extract_title(html)
            res.text = strip_tags(page.inner_text("body"))
            if shot_path:
                page.screenshot(path=shot_path, full_page=False)
                res.notes.append(f"screenshot: {shot_path}")
            res.notes.append("layer3: playwright succeeded")
            return res
        finally:
            try:
                browser.close()
            except Exception:  # noqa: BLE001
                pass  # Windows driver-exit noise: "Connection closed while
                      # reading from the driver" — harmless, results are intact


# ---------------------------------------------------------------- batch

def fetch_many(urls: list[str], concurrency: int = 6, delay: float = 0.5,
               allow_browser: bool = False) -> list[FetchResult]:
    """Sequential-with-delay batch fetch (layer 1 only by default).

    Keeps it polite: browsers in bulk are slow and heavy; escalate single URLs
    individually via fetch() when the sample shows they need it.
    """
    import concurrent.futures as cf

    results: list[FetchResult] = []
    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {ex.submit(fetch, u, allow_browser): u for u in urls}
        for fut in cf.as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as e:  # noqa: BLE001
                results.append(FetchResult(url=futs[fut], error=str(e)))
            time.sleep(delay)
    # restore input order
    order = {u: i for i, u in enumerate(urls)}
    results.sort(key=lambda r: order.get(r.url, 1 << 30))
    return results


def dedup_urls(urls: list[str]) -> list[str]:
    """Normalized-URL dedup: strip utm_*/fbclid/sid, trailing slash, fragment."""
    norm, out = set(), []
    for u in urls:
        p = urllib.parse.urlsplit(u.strip())
        q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query)
             if not k.lower().startswith(("utm_", "fbclid", "sid", "spm"))]
        key = (p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"),
               urllib.parse.urlencode(sorted(q)))
        if key not in norm:
            norm.add(key)
            out.append(u)
    return out


if __name__ == "__main__":
    import sys
    r = fetch(sys.argv[1] if len(sys.argv) > 1 else "https://example.com")
    print(json.dumps(asdict(r), ensure_ascii=False, indent=2)[:4000])
