# services/aiflag.py
import re, statistics
from collections import Counter
from typing import Dict

def analyze_style(text: str) -> Dict[str, object]:
    """
    Heuristic-only AI-text signals.
    Down-weights short texts (< ~40 words); returns {score in [0,1], signals, disclaimer}.
    """
    words = re.findall(r"[A-Za-z']+", text.lower())
    n = len(words)
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]

    if n == 0:
        return {"score": 0.0, "signals": {}, "disclaimer": "Empty text."}

    ttr = len(set(words)) / n
    slens = [len(re.findall(r"[A-Za-z']+", s)) for s in sents] or [n]
    burst = statistics.pstdev(slens)

    bigrams = [f"{words[i]} {words[i+1]}" for i in range(n - 1)]
    counts = Counter(bigrams)
    repeated_extra = sum(max(0, v - 1) for v in counts.values())
    rep_ratio = repeated_extra / max(1, len(bigrams))

    base = 0.5 * (1 - ttr) + 0.3 * (1 / (1 + burst)) + 0.2 * rep_ratio
    length_factor = min(1.0, n / 40.0)  # full weight after ~40 words
    score = max(0.0, min(1.0, base * length_factor))

    return {
        "score": round(score, 3),
        "signals": {
            "type_token_ratio": round(ttr, 3),
            "avg_sentence_len": round(sum(slens) / len(slens), 2),
            "burstiness": round(burst, 2),
            "bigram_repetition": round(rep_ratio, 3),
            "word_count": n,
        },
        "disclaimer": "Heuristic only. Short texts (<40 words) are not reliable."
    }
