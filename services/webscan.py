import os, re, time, requests
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer

# -------- TF-IDF query extractor (same as before) --------
_SPLIT = re.compile(r"(?<=[.!?])\s+")

def _split_sentences(text: str) -> List[str]:
    sents = [s.strip() for s in _SPLIT.split(text) if s.strip()]
    return sents or [text]

def _pick_queries(text: str, k: int = 8) -> List[str]:
    sents = _split_sentences(text)
    corpus = sents + [text]
    vec = TfidfVectorizer(ngram_range=(3,5), stop_words="english", min_df=1)
    X = vec.fit_transform(corpus)
    feats = vec.get_feature_names_out()
    weights = X[-1].toarray()[0]
    pairs = sorted([(weights[i], feats[i]) for i in range(len(feats))], reverse=True)
    queries = []
    for _, phr in pairs:
        q = phr.replace("  ", " ").strip()
        if len(q) > 14:
            queries.append('"' + q + '"')  # quoted exact search
        if len(queries) >= k:
            break
    if not queries:
        queries = [text[:80]]
    return queries

# -------- Providers --------
def _google_cse_search(query: str, count: int = 5) -> List[Dict]:
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CX")
    if not api_key or not cx:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": min(count, 10)}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("items", []) or []:
        results.append({
            "name": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet", "")
        })
    return results

def _semantic_scholar_search(query: str, count: int = 5) -> List[Dict]:
    # Great for academic/abstract-like text. No key required for light use.
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": query.strip('"'), "limit": count, "fields": "title,url,abstract"}
    r = requests.get(url, params=params, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json() or {}
    results = []
    for item in data.get("data", []):
        results.append({
            "name": item.get("title"),
            "url": item.get("url"),
            "snippet": (item.get("abstract") or "")[:200]
        })
    return results

# Optional: keep Bing as fallback if you later add BING_API_KEY
def _bing_search(query: str, count: int = 5) -> List[Dict]:
    key = os.getenv("BING_API_KEY")
    if not key:
        return []
    headers = {"Ocp-Apim-Subscription-Key": key}
    params  = {"q": query, "count": count, "textDecorations": False, "textFormat": "Raw"}
    r = requests.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("webPages", {}).get("value", []) or []:
        results.append({"name": item.get("name"), "url": item.get("url"), "snippet": item.get("snippet", "")})
    return results

# -------- Unified scan --------
def scan_text_against_web(text: str, max_queries: int = 8) -> Dict:
    queries = _pick_queries(text, k=max_queries)
    evidence = []

    def _provider_chain(q: str) -> List[Dict]:
        # Try Google first (if configured), else Semantic Scholar, else Bing if present
        res = _google_cse_search(q)
        if not res:
            res = _semantic_scholar_search(q)
        if not res:
            res = _bing_search(q)
        return res

    for q in queries:
        try:
            hits = _provider_chain(q)
        except Exception:
            hits = []
        for h in hits:
            if h.get("url"):
                evidence.append({"query": q, **h})
        time.sleep(0.25)

    # de-dupe by URL
    seen, uniq = set(), []
    for e in evidence:
        u = e["url"]
        if u not in seen:
            uniq.append(e); seen.add(u)
    return {"queries": queries, "matches": uniq}
