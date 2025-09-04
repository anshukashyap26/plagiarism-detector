import math, re, statistics
from collections import Counter
from typing import Dict

def analyze_style(text: str) -> Dict:
    words = re.findall(r"[A-Za-z']+", text.lower())
    n = len(words)
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if n == 0:
        return {"score": 0.0, "signals": {}, "note": "empty text"}

    # lexical variation
    ttr = len(set(words)) / n

    # sentence length/burstiness
    slens = [len(re.findall(r"[A-Za-z']+", s)) for s in sents] or [n]
    burst = statistics.pstdev(slens)

    # repetition: fraction of *extra* bigrams beyond 1 occurrence
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(n-1)]
    counts = Counter(bigrams)
    repeated_extra = sum(max(0, v-1) for v in counts.values())
    rep_ratio = repeated_extra / max(1, len(bigrams))

    # combine
    base = 0.5*(1 - ttr) + 0.3*(1/(1 + burst)) + 0.2*rep_ratio

    # very short texts are unreliable → dampen score
    length_factor = min(1.0, n / 40.0)   # ~full weight after ~40 words
    score = max(0.0, min(1.0, base * length_factor))

    return {
        "score": round(score, 3),
        "signals": {
            "type_token_ratio": round(ttr, 3),
            "avg_sentence_len": round(sum(slens)/len(slens), 2),
            "burstiness": round(burst, 2),
            "bigram_repetition": round(rep_ratio, 3),
            "word_count": n
        },
        // "disclaimer": "Heuristic only. Short texts (<40 words) are not reliable."
    }
