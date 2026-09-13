#!/usr/bin/env python3
"""academic.py — Crossref / OpenAlex / arXiv / DOI resolution, stdlib only.

Recipes consolidated from web-research-pro ACADEMIC-API.md and the paper-lookup
skill's arxiv.md trap list. Every function returns plain dicts and never raises
on "not found" — it returns None so callers can fall through to the next source.

arXiv traps handled here (they silently produce WRONG results otherwise):
  1. malformed param -> HTTP 200 + totalResults=1 + single entry titled "Error"
  2. feed <link> before first entry is the query URL, not a paper
  3. <id> carries a version suffix (1706.03762v7)
  4. title/summary arrive hard-wrapped mid-sentence
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "crawler-power-kit academic/1.0 (mailto:anonymous@example.com)"
TIMEOUT = 25

CROSSREF = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
ARXIV = "https://export.arxiv.org/api/query"
DOI_ORG = "https://doi.org/api/handles"


def _get(url: str, accept: str = "application/json", retries: int = 2):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == retries:
                raise
        except Exception:
            if i == retries:
                raise
        time.sleep(1.5 * (i + 1))
    return None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ------------------------------------------------------------------ crossref

def crossref(title: str = "", doi: str = "", rows: int = 3, mailto: str = "") -> list[dict]:
    """Bibliographic search or DOI lookup against Crossref."""
    out = []
    if doi:
        body = _get(f"{CROSSREF}/{urllib.parse.quote(doi, safe='/')}")
        if body is None:
            return []
        msg = json.loads(body)["message"]
        out.append(msg)
    else:
        params = {"query.bibliographic": title, "rows": str(rows),
                  "select": "DOI,title,author,container-title,issued,volume,issue,page,type"}
        if mailto:
            params["mailto"] = mailto
        body = _get(f"{CROSSREF}?{urllib.parse.urlencode(params)}")
        if body is None:
            return []
        out = json.loads(body)["message"]["items"]
    return [_crossref_item(m) for m in out]


def _crossref_item(m: dict) -> dict:
    au = m.get("author", [])
    return {
        "source": "crossref",
        "title": _clean((m.get("title") or [""])[0]),
        "doi": m.get("DOI", ""),
        "authors": "; ".join(f"{a.get('family','')}, {a.get('given','')}".strip(", ")
                             for a in au[:8]),
        "venue": (m.get("container-title") or [""])[0] if m.get("container-title") else "",
        "year": (m.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0],
        "volume": m.get("volume", ""), "issue": m.get("issue", ""),
        "pages": m.get("page", ""), "type": m.get("type", ""),
    }


# ------------------------------------------------------------------ openalex

def openalex(title: str = "", doi: str = "", rows: int = 3, mailto: str = "") -> list[dict]:
    """OpenAlex — free, no key, great coverage incl. venues/citations."""
    params = {"per-page": str(rows)}
    if mailto:
        params["mailto"] = mailto
    if doi:
        d = doi if doi.startswith("10.") else doi
        params["filter"] = f"doi:https://doi.org/{d}"
    else:
        params["search"] = title
    body = _get(f"{OPENALEX}?{urllib.parse.urlencode(params)}")
    if body is None:
        return []
    return [_openalex_item(w) for w in json.loads(body).get("results", [])]


def _openalex_item(w: dict) -> dict:
    def _name(a):
        return a.get("author", {}).get("display_name", "") if isinstance(a, dict) else ""
    primary = w.get("primary_location") or {}
    src = (primary.get("source") or {}).get("display_name", "")
    return {
        "source": "openalex",
        "title": _clean(w.get("display_name", "")),
        "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
        "authors": "; ".join(_name(a) for a in w.get("authorships", [])[:8]),
        "venue": src, "year": w.get("publication_year"),
        "cited_by": w.get("cited_by_count"),
        "type": w.get("type"), "oa": (w.get("open_access") or {}).get("is_oa"),
    }


# ------------------------------------------------------------------ arxiv

def arxiv(query: str = "", id_list: str = "", max_results: int = 5) -> list[dict] | None:
    """arXiv Atom search. Returns None on the fake 'Error' entry / rate-limit body."""
    params = {"max_results": str(max_results), "searchtype": "all"}
    if id_list:
        params["id_list"] = id_list
    else:
        params["query"] = query
    body = _get(f"{ARXIV}?{urllib.parse.urlencode(params)}", accept="application/atom+xml")
    if body is None:
        return None
    if re.match(r"\s*rate exceeded", body, re.I):     # trap 4: throttle is plain text
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    entries = root.findall("a:entry", ns)
    if not entries:
        return None
    first_title = _clean(entries[0].findtext("a:title", "", ns))
    if first_title.lower() == "error":                 # trap 1: HTTP-200 failure
        return None
    out = []
    for e in entries:
        aid = e.findtext("a:id", "", ns)
        m = re.search(r"abs/([0-9.]+)(v\d+)?$", aid)   # trap 3: strip version
        out.append({
            "source": "arxiv",
            "title": _clean(e.findtext("a:title", "", ns)),
            "arxiv_id": m.group(1) if m else aid,
            "authors": "; ".join(_clean(p.findtext("a:name", "", ns))
                                for p in e.findall("a:author", ns)[:8]),
            "published": _clean(e.findtext("a:published", "", ns))[:10],
            "abstract": _clean(e.findtext("a:summary", "", ns))[:600],  # trap 4: unwrapped
        })
    return out


# ------------------------------------------------------------------ doi

def doi_status(doi: str) -> dict | None:
    """Hard DOI existence check via the DOI handle API (authoritative registry)."""
    body = _get(f"{DOI_ORG}/{urllib.parse.quote(doi, safe='')}")
    if body is None:
        return None
    try:
        h = json.loads(body)
        return {"doi": h.get("handle"), "status": h.get("responseCode"),
                "ok": h.get("responseCode") == 1}
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------ combined

def find_paper(title: str = "", doi: str = "", rows: int = 3) -> dict:
    """Try DOI registry -> Crossref -> OpenAlex -> arXiv, first wins per field.

    Cross-source agreement is the anti-hallucination core: a reference is
    trustworthy only when two independent sources agree on title+year.
    """
    found: dict = {"query": title or doi, "hits": []}
    if doi:
        st = doi_status(doi)
        if st:
            found["doi_registry"] = st
    for fn in (crossref, openalex):
        try:
            hits = fn(title=title, doi=doi, rows=rows)
        except Exception:
            hits = []
        found["hits"].extend(hits)
        if hits:
            break
    if title and not any(h.get("doi") for h in found["hits"]):
        try:
            ax = arxiv(query=title, max_results=rows)
            if ax:
                found["hits"].extend(ax)
        except Exception:
            pass
    return found
