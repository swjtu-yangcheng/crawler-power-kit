#!/usr/bin/env python3
"""engines.py — 16-engine registry, zero API keys (distilled from multi-search-engine skill).

Each engine: how to build its search URL, which language/region it serves, and
whether the HTML endpoint is machine-parseable (PARSEABLE) — meaning cpk.py can
extract result links directly. Non-parseable engines still emit URLs for the
agent/user to open via WebFetch or a browser layer.

Language routing rule (from the original skill):
  Chinese query        -> CN engines first (Baidu, Bing CN, 360, Sogou, WeChat, Shenma)
  non-Chinese query    -> global engines first (Google, DDG, Brave, ...)
"""
from __future__ import annotations

import html as _html
import re
import urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

#: key -> (url_template, region, parseable, note)
ENGINES = {
    # ---- Domestic (7) ----
    "baidu":    ("https://www.baidu.com/s?wd={q}",            "CN", True,  "strong CN index; heavy anti-bot, may need cookies"),
    "bing-cn":  ("https://cn.bing.com/search?q={q}&ensearch=0", "CN", True, "Bing China, stable, parseable"),
    "bing-int": ("https://cn.bing.com/search?q={q}&ensearch=1", "CN", True, "Bing international via CN gateway"),
    "so360":    ("https://www.so.com/s?q={q}",                "CN", True,  "Qihoo 360"),
    "sogou":    ("https://sogou.com/web?query={q}",           "CN", True,  "also indexes WeChat articles"),
    "weixin":   ("https://wx.sogou.com/weixin?type=2&query={q}", "CN", True, "WeChat official-account articles"),
    "shenma":   ("https://m.sm.cn/s?q={q}",                   "CN", True,  "mobile-only index"),
    # ---- International (9) ----
    "google":   ("https://www.google.com/search?q={q}",       "GLOBAL", True, "best index; may hit consent/JS wall"),
    "google-hk":("https://www.google.com.hk/search?q={q}",    "GLOBAL", True, "Google HK, reachable from CN with VPN"),
    "ddg":      ("https://duckduckgo.com/html/?q={q}",        "GLOBAL", True, "plain-HTML endpoint, most reliable to parse, no tracking"),
    "yahoo":    ("https://search.yahoo.com/search?p={q}",     "GLOBAL", True, "Bing-powered"),
    "startpage":("https://www.startpage.com/sp/search?query={q}", "GLOBAL", False, "Google results + privacy; JS challenge"),
    "brave":    ("https://search.brave.com/search?q={q}",     "GLOBAL", True, "independent index"),
    "ecosia":   ("https://www.ecosia.org/search?q={q}",       "GLOBAL", True, "Bing-powered, eco"),
    "qwant":    ("https://www.qwant.com/?q={q}",              "GLOBAL", False, "EU GDPR; JS-heavy"),
    "wolfram":  ("https://www.wolframalpha.com/input?i={q}",  "GLOBAL", False, "knowledge computation, not web search"),
}

CN_KEYS = ["baidu", "bing-cn", "sogou", "so360", "weixin", "bing-int", "shenma"]
GLOBAL_KEYS = ["ddg", "google", "brave", "bing-int", "yahoo", "ecosia",
               "google-hk", "startpage", "qwant", "wolfram"]

#: Google/Bing-style time filters -> ddg equivalent
TIME_FILTERS = {"h": "h", "d": "d", "w": "w", "m": "m", "y": "y"}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def is_chinese(query: str) -> bool:
    """True when >=20% of the query's letters are CJK."""
    letters = [c for c in query if c.isalpha()]
    if not letters:
        return False
    cjk = [c for c in letters if _CJK_RE.match(c)]
    return len(cjk) / len(letters) >= 0.2


def route(query: str) -> list[str]:
    """Language-aware engine priority (best-first, parseable engines preferred)."""
    keys = CN_KEYS if is_chinese(query) else GLOBAL_KEYS
    return keys


def build_url(engine: str, query: str, *, site: str | None = None,
              filetype: str | None = None, time: str | None = None,
              exact: bool = False) -> str:
    """Build a search URL with the operators that work on most engines.

    site:/filetype:/exact-phrase are appended query-style (Google/Bing syntax);
    `time` maps to the engine's own freshness parameter where known.
    """
    q = f'"{query}"' if exact else query
    if site:
        q = f"site:{site} {q}"
    if filetype:
        q = f"filetype:{filetype} {q}"

    tpl, region, _parseable, _note = ENGINES[engine]
    if engine == "ddg" and time:
        # DuckDuckGo html endpoint accepts df=date range suffix
        tpl = tpl + "&df=" + TIME_FILTERS.get(time, "w")
    elif engine in ("google", "google-hk") and time:
        tpl = tpl + "&tbs=qdr:" + time
    elif engine.startswith("bing") and time:
        tpl = tpl + "&qft=interval%3d%22" + {"d": "date", "w": "week", "m": "month", "y": "year"}.get(time, "week") + "%22"
    return tpl.format(q=urllib.parse.quote_plus(q))


def bang(query: str, target: str = "gh") -> str:
    """DuckDuckGo bang shortcut: !gh GitHub, !so StackOverflow, !w Wikipedia, !yt YouTube."""
    return f"https://duckduckgo.com/html/?q=%21{target}+{urllib.parse.quote_plus(query)}"


def parse_ddg_html(html: str, limit: int = 10) -> list[dict]:
    """Parse DuckDuckGo /html/ results — stdlib regex, no bs4 needed.

    The endpoint is stable: results sit in <a class="result__a" href="URL">TITLE</a>
    with snippets in <a class="result__snippet">. Returns [{url, title, snippet}].
    """
    results, seen = [], set()
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S
    ):
        url, title = m.group(1), _html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        # DDG wraps URLs in a redirect: //duckduckgo.com/l/?uddg=<encoded>
        um = re.search(r"[?&]uddg=([^&]+)", url)
        if um:
            url = urllib.parse.unquote(um.group(1))
        if not title or url in seen:
            continue
        seen.add(url)
        results.append({"url": url, "title": title, "snippet": ""})
        if len(results) >= limit:
            break
    # attach snippets positionally
    snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    for r, s in zip(results, snips):
        r["snippet"] = _html.unescape(re.sub(r"<[^>]+>", "", s)).strip()[:300]
    return results


def parse_bing_html(html: str, limit: int = 10) -> list[dict]:
    """Parse Bing (cn.bing.com) organic results — <li class="b_algo"><h2><a href>."""
    results, seen = [], set()
    for m in re.finditer(
        r'<li class="b_algo".*?<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>(.*?)</li>',
        html, re.S,
    ):
        url = m.group(1)
        title = _html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if not title or url in seen:
            continue
        seen.add(url)
        sm = re.search(r'<p[^>]*>(.*?)</p>', m.group(3), re.S)
        snippet = _html.unescape(re.sub(r"<[^>]+>", "", sm.group(1))).strip()[:300] if sm else ""
        results.append({"url": url, "title": title, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


PARSERS = {"ddg": parse_ddg_html, "bing-cn": parse_bing_html,
           "bing-int": parse_bing_html}
