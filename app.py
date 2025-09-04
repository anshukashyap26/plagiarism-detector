# app.py
import os
import json
from typing import List, Tuple

import streamlit as st

# ---- Algorithms (already in your repo) ----
try:
    from algorithms.lcs import lcs_similarity
except Exception:
    # Fallback simple LCS similarity if import ever fails
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
    # very small KMP fallback
    def kmp_find_all(text: str, pat: str) -> List[int]:
        if not pat: return []
        lps = [0]*len(pat)
        i = 1; L = 0
        while i < len(pat):
            if pat[i]==pat[L]:
                L += 1; lps[i]=L; i+=1
            elif L: L = lps[L-1]
            else: lps[i]=0; i+=1
        out=[]; i=j=0
        while i < len(text):
            if text[i]==pat[j]:
                i+=1; j+=1
                if j==len(pat):
                    out.append(i-j); j=lps[j-1]
            elif j: j=lps[j-1]
            else: i+=1
        return out

try:
    from algorithms.rabin_karp import rabin_karp_find_all
except Exception:
    # simple RK fallback
    def rabin_karp_find_all(text: str, pat: str) -> List[int]:
        if not pat: return []
        base, mod = 256, 10**9+7
        m, n = len(pat), len(text)
        if m>n: return []
        hp = 0; ht = 0; h = 1
        for _ in range(m-1): h = (h*base) % mod
        for i in range(m):
            hp = (hp*base + ord(pat[i])) % mod
            ht = (ht*base + ord(text[i])) % mod
        out=[]
        for i in range(n-m+1):
            if hp==ht and text[i:i+m]==pat:
                out.append(i)
            if i < n-m:
                ht = ( (ht - ord(text[i])*h) * base + ord(text[i+m]) ) % mod
                if ht<0: ht += mod
        return out

# ---- Optional modules (won't crash if missing) ----
try:
    from services.webscan import scan_text_against_web
except Exception as e:
    scan_text_against_web = None
    WEBSCAN_IMPORT_ERR = str(e)
else:
    WEBSCAN_IMPORT_ERR = None

try:
    from services.aiflag import analyze_style
except Exception as e:
    analyze_style = None
    AIFLAG_IMPORT_ERR = str(e)
else:
    AIFLAG_IMPORT_ERR = None


st.set_page_config(page_title="Plagiarism Detector • Streamlit", layout="wide")
st.title("🧭 Plagiarism & Style Analyzer")

st.caption(
    "Compare two texts (LCS/KMP/RK), scan a single input against the public web "
    "with strict evidence, and inspect simple AI-text heuristics."
)

tabs = st.tabs(["🔁 Compare two texts", "🛰️ Single-Input Scanner"])

# =====================================================================================
# TAB 1 — Compare two texts
# =====================================================================================
with tabs[0]:
    st.subheader("Compare two texts")

    colA, colB = st.columns(2)
    with colA:
        textA = st.text_area(
            "Text A",
            height=220,
            value="The quick brown fox jumps over the lazy dog.",
            key="txtA",
        )
        fileA = st.file_uploader("Or upload .txt for A", type=["txt"], key="fA")
        if fileA is not None:
            try:
                textA = fileA.read().decode("utf-8", errors="ignore")
                st.success("Loaded Text A from file.")
            except Exception:
                st.error("Could not read file A as UTF-8 text.")

    with colB:
        textB = st.text_area(
            "Text B",
            height=220,
            value="A quick brown dog outpaces a fast fox.",
            key="txtB",
        )
        fileB = st.file_uploader("Or upload .txt for B", type=["txt"], key="fB")
        if fileB is not None:
            try:
                textB = fileB.read().decode("utf-8", errors="ignore")
                st.success("Loaded Text B from file.")
            except Exception:
                st.error("Could not read file B as UTF-8 text.")

    algo = st.selectbox(
        "Algorithm",
        ["LCS (global similarity %)", "Exact matches • KMP", "Exact matches • Rabin-Karp"],
    )

    pattern = ""
    if "KMP" in algo or "Rabin" in algo:
        pattern = st.text_input("Pattern to search (required for exact-match modes)", "")

    if st.button("Analyze", type="primary"):
        if not textA or not textB:
            st.error("Please provide both Text A and Text B.")
        else:
            if algo.startswith("LCS"):
                sim = lcs_similarity(textA, textB)
                st.metric("LCS similarity", f"{round(sim*100, 2)} %")
            else:
                if not pattern.strip():
                    st.warning("Enter a pattern for exact-match modes.")
                else:
                    finder = kmp_find_all if "KMP" in algo else rabin_karp_find_all
                    posA = finder(textA, pattern)
                    posB = finder(textB, pattern)
                    st.write("**Positions in A**:", posA or "no matches")
                    st.write("**Positions in B**:", posB or "no matches")


# =====================================================================================
# TAB 2 — Single-Input Scanner
# =====================================================================================
with tabs[1]:
    st.subheader("Single-Input Scanner")

    doc = st.text_area("Paste text here", height=180, key="singleInput")

    c1, c2 = st.columns(2)
    run_web = c1.button("Run Web Plagiarism Scan (beta)")
    run_ai  = c2.button("Check AI-Generated Signals (heuristic)")

    # --- Web scan ---
    if run_web:
        if scan_text_against_web is None:
            st.error("Web scan module failed to load.")
            if WEBSCAN_IMPORT_ERR:
                st.caption(WEBSCAN_IMPORT_ERR)
        elif not doc.strip():
            st.warning("Please paste some text first.")
        else:
            res = scan_text_against_web(doc, max_queries=8)
            st.subheader("Queries used  ↩︎")
            st.write(res.get("queries", []))

            st.subheader("Possible matches (evidence)")
            matches = res.get("matches", [])
            if not matches:
                st.info(
                    "No strict matches found. Try a longer excerpt, or adjust strictness "
                    "(env var MIN_LINE_MATCH_FRAC, default 0.5)."
                )
            for m in matches:
                frac = m.get("line_match_fraction")
                extra = f" — match:{frac:.2f}" if isinstance(frac, (int, float)) else ""
                st.markdown(f"- **[{m.get('name','(no title)')}]({m.get('url','#')})** — {m.get('snippet','')}{extra}")

    # --- AI heuristics ---
    if run_ai:
        if analyze_style is None:
            st.error("AI-heuristics module not available.")
            if AIFLAG_IMPORT_ERR:
                st.caption(AIFLAG_IMPORT_ERR)
        elif not doc.strip():
            st.warning("Please paste some text first.")
        else:
            out = analyze_style(doc)
            wc = out.get("signals", {}).get("word_count", 0)
            if wc < 30:
                st.caption("Note: very short text; score is not reliable.")
            st.subheader("AI-text heuristic score  ↩︎")
            st.json(out)


# Footer
st.markdown("---")
st.caption(
    "This tool provides evidence links and simple style signals. Always review sources manually; "
    "web detectors and heuristics can be noisy."
)
