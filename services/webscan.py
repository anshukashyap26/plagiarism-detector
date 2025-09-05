# services/webscan.py
"""
Web scanning with strict verification.

- Short inputs -> exact quoted phrases
- Long inputs  -> quoted full sentences + quoted 8-word windows
- Provider     -> Google Custom Search JSON API (Programmable Search Engine)
- Verifier     -> Downloads each result (HTML or PDF) and keeps only links where:
                  * single unit: exact presence
                  * multiple units: >= MIN_LINE_MATCH_FRAC (default 0.5) of units present
- Env/Secrets  -> GOOGLE_API_KEY, GOOGLE_CX, MIN_LINE_MATCH_FRAC, MAX_VERIFY_PAGES
"""

from __future__ import annotations

import io
import os
import re
import time
import unicodedata
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text as pdf_extract_text


# ------------------------ normalization helpers ------------------------

PUNCT_CLEAN = re.compile(r"[^a-z0-9 ]+")

def _normalize(s: str) -> str:
    """
    Lower, de-accent, unify quotes/dashes, collapse spaces, drop punctuation.
    This makes matching robust to formatting differences (curly quotes, hyphenation).
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = (
        s.replace("—", "-").replace("–", "-")
         .replace("“", '"').replace("”", '"')
         .replace("’", "'").replace("‘", "'")
    )
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = PUNCT_CLEAN.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# ------------------------ extraction (HTML/PDF) ------------------------

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


# ------------------------ verification units ------------------------

def _units_for_match(user_text: str) -> List[str]:
    """
    Build verification units from sentences (>=8 words).
    Fallback: overlapping 12-word windows when no long sentences exist.
    """
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", user_text) if s.strip()]
    long_sents = [s for s in sents if len(re.findall(r"[A-Za-z0-9']+", s)) >= 8]
    if long_sents:
        return long_sents

    toks = re.findall(r"[A-Za-z0-9']+", user_text)
    out = []
    for i in range(0, len(toks), 12):
        chunk = " ".join(toks[i:i + 12])
        if len(chunk.split()) >= 8:
            out.append(chunk)
    return out or ([user_text.strip()] if user_text.strip() else [])

def _fraction_units_present(page_text_norm: str, units: List[str]) -> float:
    if not units:
        return 0.0
    hits = 0
    for u in units:
        if _normalize(u) in page_text_norm:
            hits += 1
    return hits / len(units)


# ------------------------ query builders ------------------------

def _quoted_windows(text: str, n: int = 8, step: int = 4, k: int = 8) -> List[str]:
    """Quoted n-gram windows from original text—great for academic prose."""
    toks = re.findall(r"[A-Za-z0-9']+", text)
    qs: List[str] = []
    for i in range(0, max(0, len(toks) - n + 1), step):
        window = " ".join(toks[i:i + n])
        if len(window) >= 20:
            qs.append(f'"{window}"')
        if len(qs) >= k:
            break
    out, seen = [], set()
    for q in qs:
        key = q.lower()
        if key not in seen:
            out.append(q); seen.add(key)
    return out or [f'"{text.strip()}"']


# ------------------------ Google CSE provider ------------------------

def _google_cse_search(query: str, count: int = 6) -> List[Dict]:
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CX")
    if not api_key or not cx:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": min(count, 10)}
    if len(query) >= 2 and query[0] == query[-1] == '"':
        params["exactTerms"] = query.strip('"')  # tighter matching for quoted phrases
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
    by downloading each page and checking sentence-level presence.
    """
    base = text.strip()
    tokens = re.findall(r"[A-Za-z0-9']+", base)

    # Short input -> strict phrases; Long input -> quoted sentences + windows
    if len(base) < 120 or len(tokens) < 12:
        queries: List[str] = []
        if base and len(base) <= 200:
            queries.append(f'"{base}"')
        if len(tokens) >= 4:
            tail = " ".join(tokens[-6:])
            queries.append(f'"{tail}"')
        # optional domain phrase (example for "iiit naya raipur")
        m = re.search(r"\b(iiit[^,.;\n]*)", base, re.I)
        if m and len(m.group(1).split()) >= 2:
            queries.append(f'"{m.group(1).strip()}"')
        seen = set()
        queries = [q for q in queries if q not in seen and not seen.add(q)]
    else:
        # take a couple of quoted full sentences + sliding windows
        sents = [s for s in re.split(r"(?<=[.!?])\s+", base) if len(s.split()) >= 8]
        q_sents = [f'"{s.strip()}"' for s in sents[:2]]
        q_windows = _quoted_windows(base, n=8, step=4, k=max(0, max_queries - len(q_sents)))
        queries, seen = [], set()
        for q in (q_sents + q_windows):
            key = q.lower()
            if key not in seen:
                queries.append(q); seen.add(key)

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
            uniq.append(e); seen.add(e["url"])

    # 2) strict, sentence-based verification
    min_fraction = float(os.getenv("MIN_LINE_MATCH_FRAC", "0.5"))  # 50% rule
    units = _units_for_match(base)
    units_norm = [_normalize(u) for u in units]

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

        page_norm = _normalize(page_text)
        if len(units_norm) == 1:
            ok = units_norm[0] in page_norm
            frac = 1.0 if ok else 0.0
        else:
            frac = _fraction_units_present(page_norm, units_norm)
            ok = frac >= min_fraction

        if ok:
            e["line_match_fraction"] = round(frac, 3)
            verified.append(e)

    return {"queries": queries, "matches": verified}
