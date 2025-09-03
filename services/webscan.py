import os, re, time, requests
from typing import List, Dict
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer

# ---------- helpers ----------
def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

def _visible_page_text(url: str, timeout: int = 12) -> str:
    """Download the page and return normalized visible text."""
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (plagiarism-detector)"},
        )
        ctype = r.headers.get("Content-Type", "")
        if r.status_code != 200 or "text/html" not in ctype:
            return ""
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()
        return _normalize(soup.get_text(separator=" "))
    except Exception:
        return ""

def _split_lines_for_match(user_text: str) -> List[str]:
    # keep non-empty lines; ignore super-short lines (<12 chars)
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

# ---------- query builders (same behavior you already had) ----------
_SPLIT = re.compile(r"(?<=[.!?])\s+")

def _split_sentences(text: str) -> List[str]:
    sents = [s.strip() for s in _SPLIT.split(text) if s.strip()]
    return sents or [text]

def _pick_queries(text: str, k: int = 8) -> List[str]:
    sents = _split_sentences(text)
    corpus = sents + [text]
    vec = TfidfVectorizer(ngram_range=(3, 5), stop_words="english", min_df=1)
    X = vec.fit_transform(corpus)
    feats = vec.get_feature_names_out()
    weights = X[-1].toarray()[0]
    pairs = sorted([(weights[i], feats[i]) for i in range(len(feats))], reverse=True)
    queries = []
    for _, phr in pairs:
        q = phr.replace("  ", " ").strip()
        if len(q) > 14:
            queries.append('"' + q + '"')
        if len(queries) >= k:
            break
    if not queries:
        queries = [text[:80]]
    return queries

# ---------- Google CSE provider (you already have this) ----------
def _google_cse_search(query: str, count: int = 5) -> List[Dict]:
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CX")
    if not api_key or not cx:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": min(count, 10)}
    if len(query) >= 4 and query[0] == query[-1] == '"':
        params["exactTerms"] = query.strip('"')
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json() or {}
    results = []
    for item in data.get("items", []) or []:
        results.append({
            "name": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", "")
        })
    return results

# ---------- main scan with STRICT verification ----------
def scan_text_against_web(text: str, max_queries: int = 8) -> Dict:
    base = text.strip()
    tokens = re.findall(r"[A-Za-z]+", base)
    # Build precise queries for short inputs; TF-IDF for longer text
    if len(base) < 120 or len(tokens) < 12:
        queries = []
        if len(base) <= 100 and base:
            queries.append(f'"{base}"')
        if len(tokens) >= 4:
            tail = " ".join(tokens[-6:])
            queries.append(f'"{tail}"')
        # add a domain phrase if present (e.g., "iiit naya raipur")
        m = re.search(r"\b(iiit[^,.;\n]*)", base, re.I)
        if m and len(m.group(1).split()) >= 2:
            queries.append(f'"{m.group(1).strip()}"')
        # de-dup
        seen = set()
        queries = [q for q in queries if q not in seen and not seen.add(q)]
        if not queries:
            queries = [f'"{base}"']
    else:
        queries = _pick_queries(text, k=max_queries)

    # 1) get candidates from Google
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

    # 2) STRICT verification on page content
    min_fraction = float(os.getenv("MIN_LINE_MATCH_FRAC", "0.5"))  # you asked for 50%
    lines = _split_lines_for_match(base)
    lines_norm = [_normalize(ln) for ln in lines]

    verified = []
    max_verify = int(os.getenv("MAX_VERIFY_PAGES", "12"))  # avoid being too slow
    checked = 0
    for e in uniq:
        if checked >= max_verify:
            break
        page_text = _visible_page_text(e["url"])
        checked += 1
        if not page_text:
            continue
        # If single line: require exact presence; else require >= 50% lines present
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
