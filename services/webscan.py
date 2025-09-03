import os, re, time, requests
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer

BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"
BING_KEY_ENV = "BING_API_KEY"  # set this in environment or Streamlit secrets

_SPLIT = re.compile(r"(?<=[.!?])\s+")

def _split_sentences(text: str) -> List[str]:
    sents = [s.strip() for s in _SPLIT.split(text) if s.strip()]
    return sents or [text]

def _pick_queries(text: str, k: int = 8) -> List[str]:
    sents = _split_sentences(text)
    corpus = sents + [text]
    vec = TfidfVectorizer(ngram_range=(3,5), stop_words='english', min_df=1)
    X = vec.fit_transform(corpus)
    feats = vec.get_feature_names_out()
    weights = X[-1].toarray()[0]
    pairs = sorted([(weights[i], feats[i]) for i in range(len(feats))], reverse=True)
    queries = []
    for _, phr in pairs:
        q = phr.replace('  ', ' ').strip()
        if len(q) > 14:
            queries.append('"' + q + '"')
        if len(queries) >= k:
            break
    if not queries:
        queries = [text[:80]]
    return queries

def _bing_search(query: str, count: int = 5) -> List[Dict]:
    key = os.getenv(BING_KEY_ENV)
    if not key:
        return []
    headers = {"Ocp-Apim-Subscription-Key": key}
    params  = {"q": query, "count": count, "textDecorations": False, "textFormat": "Raw"}
    r = requests.get(BING_ENDPOINT, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get('webPages', {}).get('value', []):
        results.append({
            "name": item.get("name"),
            "url": item.get("url"),
            "snippet": item.get("snippet", "")
        })
    return results

def scan_text_against_web(text: str, max_queries: int = 8) -> Dict:
    queries = _pick_queries(text, k=max_queries)
    evidence = []
    for q in queries:
        try:
            hits = _bing_search(q)
        except Exception:
            hits = []
        for h in hits:
            evidence.append({"query": q, **h})
        time.sleep(0.3)
    seen, uniq = set(), []
    for e in evidence:
        u = e["url"]
        if u not in seen:
            uniq.append(e); seen.add(u)
    return {"queries": queries, "matches": uniq}
