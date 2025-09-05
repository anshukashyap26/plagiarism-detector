# app.py
import os
import json
from typing import List

import streamlit as st

# ---- Algorithms (already in your repo) ----
try:
    from algorithms.lcs import lcs_similarity
except Exception:
    def lcs_similarity(a: str, b: str) -> float:
        m, n = len(a), len(b)
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(m):
            for j in range(n):
                dp[i+1][j+1] = dp[i][j]+1 if a[i]==b[j] else max(dp[i][j+1], dp[i+1][j])
        l = dp[m][n]
        return 0.0 if max(m, n)==0 else l / max(m, n)

try:
    from algorithms.kmp import kmp_find_all
except Exception:
    def kmp_find_all(text: str, pat: str) -> List[int]:
        if not pat: return []
        lps = [0]*len(pat); i = 1; L = 0
        while i < len(pat):
            if pat[i]==pat[L]:
                L += 1; lps[i]=L; i+=1
            elif L: L = lps[L-1]
            else: lps[i]=0
