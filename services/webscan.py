# services/webscan.py
"""
Web scanning with strict verification.

- Builds precise queries:
  * Short inputs -> exact quoted phrases
  * Long inputs  -> quoted 8-word sliding windows
- Searches via Google CSE (needs GOOGLE_API_KEY + GOOGLE_CX)
- Downloads each result (HTML or PDF), extracts text, and
  keeps only links where:
    - single-line input: exact line is present
    - multi-line input : >= MIN_LINE_MATCH_FRAC (default 0.5) of lines present
Returns: {"queries": [...], "matches": [{"name","url","snippet","line_match_fraction"}]}
"""

from __future__ import annotations
import io
import os
import re
import time
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text as pdf_extract_text
from sklearn.feature_extraction.text import TfidfVectorizer


# ------------------------ text helpers ------------------------

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def _visible_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()
    return _normalize(soup.get_text(separator=" "))

def _visible_page_text(url: str, timeout: int = 15) -> str:
    """Return normalized text from HTML or PDF."""
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (plagiarism-detector)"},
        )
        if r.status_code != 200:
            return ""
        ctype = (r.headers.get("Content-Type") or "").lower()
        # PDF
        if "application/pdf" in ctype or url.lower().endswith(".pdf"):
            try:
                return _normalize(pdf_extract_text(io.BytesIO(r.content)) or "")
            except Exception:
                return ""
        # HTML
        if "text/html" in ctype:
            return _visible_html_text(r.text)
        return ""
    except Exception:
        return ""

def _split_lines_for_match(user_text: str) -> List[str]:
    # keep non-empty lines & ignore super-short lines (<12 chars)
    lines = [ln.strip() for ln in user_text.splitlines() if ln.strip()]
    long_lines = [ln for ln in lines if len(ln) >= 12]
    return long_lines or ([user_text.strip()] if user_text.strip() else [])

def _fraction_lines_present(page_text_norm: str, lines: List[str]) -> float:
    if not lines:
        return 0.0
    hits = 0
    for ln in lines:
        if _normalize(ln) in page_text_norm:
            hits += 1
    return hits / len(lines)


# ------------------------ query builders ------------------------

_SPLIT = re.compile(r"(?<=[.!?])\s+")

def _split_sentences(text: str) -> List[str]:
    sents = [s.strip() for s in _SPLIT.split(text) if s.strip()]
    return sents or [text]

def _pick_queries_tfidf(text: str, k: int = 8) -> List[str]:
    """Legacy TF-IDF n-grams (kept for completeness)."""
    sents = _split_sentences(text)
    corpus = sents + [text]
    vec = TfidfVectorizer(ngram_range=(3, 5), stop_words="english", min_df=1)
    X = vec.fit_transform(corpus)
    feats = vec.get_feature_names_out()
    weights = X[-1].toarray()[0]
    pairs = sorted(((weights[i], feats[i]) for i in range(len(feats))), reverse=True)
    queries = []
    for _, phr in pairs:
        q = " ".join(phr.split())
        if len(q) > 14:
            queries.append(f'"{q}"')
        if len(queries) >= k:
            break
    return queries or [text[:80]]

def _quoted_windows(text: str, n: int = 8, step: int = 4, k: int = 8) -> List[str]:
    """Quoted n-gram windows from original text—great for academic prose."""
    toks = re.findall(r"[A-Za-z0-9']+", text)
    qs = []
    for i in range(0, max(0, len(toks) - n + 1), step):
        window = " ".join(toks[i:i + n])
        if len(window) >= 20:
            qs.append(f'"{window}"')
        if len(qs) >= k:
            break
    # de-dup case-insensitively
    out, seen = [], set()
    for q in qs:
        key = q.lower()
        if key not in seen:
            out.append(q)
            seen.add(key)
    return out or [f'"{text.strip()}"']


# ------------------------ Google CSE provider ------------------------

def _google_cse_search(query: str, count: int = 6) -> List[Dict]:
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CX")
    if not api_key or not cx:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": min(count, 10)}
    # if the query is quoted, also force exactTerms
    if len(query) >= 2 and query[0] == query[-1] == '"':
        params["exactTerms"] = query.strip('"')
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json() or {}
    out = []
    for item in data.get("items", []) or []:
        out.append({
            "name": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return out


# ------------------------ main API ------------------------

def scan_text_against_web(text: str, max_queries: int = 8) -> Dict:
    """
    Build queries, fetch candidates from Google CSE, then STRICT-verify
    by downloading the page and checking for exact line presence.
    """
    base = text.strip()
    tokens = re.findall(r"[A-Za-z0-9']+", base)

    # Short input -> strict phrases; Long input -> quoted windows
    if len(base) < 120 or len(tokens) < 12:
        queries: List[str] = []
        if base and len(base) <= 200:
            queries.append(f'"{base}"')
        if len(tokens) >= 4:
            tail = " ".join(tokens[-6:])
            queries.append(f'"{tail}"')
        m = re.search(r"\b(iiit[^,.;\n]*)", base, re.I)  # domain phrase example
        if m and len(m.group(1).split()) >= 2:
            queries.append(f'"{m.group(1).strip()}"')
        # de-dup
        seen = set()
        queries = [q for q in queries if q not in seen and not seen.add(q)]
    else:
        queries = _quoted_windows(base, n=8, step=4, k=max_queries)

    # 1) get candidates
    candidates = []
    for q in queries:
        try:
            hits = _google_cse_search(q, count=6)
        except Exception:
            hits = []
        for h in hits:
            if h.get("url"):
                candidates.append({"query": q, **h})
        time.sleep(0.2)

    # de-dup by URL
    uniq, seen = [], set()
    for e in candidates:
        if e["url"] not in seen:
            uniq.append(e)
            seen.add(e["url"])

    # 2) strict verify
    min_fraction = float(os.getenv("MIN_LINE_MATCH_FRAC", "0.5"))  # your 50% rule
    lines = _split_lines_for_match(base)
    lines_norm = [_normalize(ln) for ln in lines]

    verified = []
    max_verify = int(os.getenv("MAX_VERIFY_PAGES", "12"))
    checked = 0
    for e in uniq:
        if checked >= max_verify:
            break
        page_text = _visible_page_text(e["url"])
        checked += 1
        if not page_text:
            continue

        if len(lines_norm) == 1:
            ok = lines_norm[0] in page_text
            frac = 1.0 if ok else 0.0
        else:
            frac = _fraction_lines_present(page_text, lines_norm)
            ok = frac >= min_fraction

        if ok:
            e["line_match_fraction"] = round(frac, 3)
            verified.append(e)

    return {"queries": queries, "matches": verified}
