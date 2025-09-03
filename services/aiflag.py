import math, re
from collections import Counter
from typing import Dict

# Heuristic-only (NOT a definitive AI detector)
def analyze_style(text: str) -> Dict:
    words = re.findall(r"[A-Za-z']+", text.lower())
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    if not words:
        return {"score": 0.0, "signals": {}}
    ttr = len(set(words)) / max(1, len(words))
    slens = [len(re.findall(r"[A-Za-z']+", s)) for s in sents if s.strip()]
    avg_len = sum(slens) / max(1, len(slens))
    var = sum((l-avg_len)**2 for l in slens) / max(1, len(slens))
    burst = math.sqrt(var)
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    rep = Counter(bigrams)
    rep_ratio = sum(v for _, v in rep.most_common(10)) / max(1, len(bigrams))
    score = max(0.0, min(1.0), )
    score = max(0.0, min(1.0, (0.5*(1-ttr) + 0.3*(1/(1+burst)) + 0.2*rep_ratio)))
    return {
        "score": round(score, 3),
        "signals": {
            "type_token_ratio": round(ttr, 3),
            "avg_sentence_len": round(avg_len, 2),
            "burstiness": round(burst, 2),
            "bigram_repetition": round(rep_ratio, 3),
        },
        "disclaimer": "Heuristic only. Use evidence + judgment; AI-text detectors can be wrong."
    }
