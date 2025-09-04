import streamlit as st
from algorithms.kmp import kmp_find_all
from algorithms.rabin_karp import rabin_karp_find_all
from algorithms.lcs import lcs_similarity
from utils.text_io import read_files_as_texts
from utils.highlight import highlight_matches_html
import pandas as pd
import os, requests

# NEW imports
from services.webscan import scan_text_against_web
from services.aiflag import analyze_style

st.set_page_config(page_title="Plagiarism Detector (KMP/LCS/RK)", layout="wide")
st.title("Plagiarism Detector")
st.caption("KMP / Rabin–Karp for exact matches • LCS for global similarity • Web Scan (beta) • AI-text heuristics")

API_BASE = os.getenv("PLAG_API_BASE")  # optional: point UI to your hosted API

mode = st.radio("Two-text mode input", ["Upload files", "Paste text"], horizontal=True)
algo = st.selectbox("Algorithm", ["LCS (similarity %)", "KMP (exact substrings)", "Rabin–Karp (exact substrings)"])

if mode == "Upload files":
    files = st.file_uploader("Upload 2+ text files (.txt, .md, .csv)", type=["txt","md","csv"], accept_multiple_files=True)
    texts, names = read_files_as_texts(files) if files else ([], [])
else:
    col1, col2 = st.columns(2)
    with col1:
        t1 = st.text_area("Text A", height=180)
    with col2:
        t2 = st.text_area("Text B", height=180)
    texts, names = ([t1, t2] if t1 and t2 else []), ["TextA", "TextB"]

run = st.button("Analyze (two-text mode)", type="primary", disabled=(len(texts) < 2))

def call_api(algorithm, textA, textB, pattern=None, chunk=20):
    if not API_BASE:
        return None
    try:
        resp = requests.post(f"{API_BASE}/api/analyze", json={
            "algorithm": algorithm, "textA": textA, "textB": textB,
            "pattern": pattern, "chunk": chunk
        }, timeout=30)
        if resp.ok:
            return resp.json()
    except Exception as e:
        st.info(f"API call failed; using local algorithms. ({e})")
    return None

if run:
    if algo.startswith("LCS"):
        # If API exists, use it
        if API_BASE and len(texts) == 2:
            data = call_api("lcs", texts[0], texts[1])
            if data and "similarity" in data:
                st.subheader("LCS Similarity (%)")
                st.write(round(data["similarity"] * 100, 2))
            else:
                st.info("Falling back to local computation.")
        # Local matrix computation
        n = len(texts)
        sim = [[0.0]*n for _ in range(n)]
        for i in range(n):
            for j in range(i+1, n):
                s = lcs_similarity(texts[i], texts[j])
                sim[i][j] = sim[j][i] = round(s*100, 2)
        df = pd.DataFrame(sim, index=names, columns=names)
        st.subheader("LCS Similarity (%) — Local")
        st.dataframe(df, use_container_width=True)
    else:
        st.subheader("Exact Match Spans")
        colA, colB = st.columns(2)
        with colA:
            a_idx = st.selectbox("Select A", list(range(len(names))), format_func=lambda i: names[i])
        with colB:
            b_idx = st.selectbox("Select B", list(range(len(names))), format_func=lambda i: names[i], index=1 if len(names)>1 else 0)

        textA, textB = texts[a_idx], texts[b_idx]
        pattern = st.text_input("Optional: pattern to search (leave empty to auto-chunk)")

        finder = kmp_find_all if algo.startswith("KMP") else rabin_karp_find_all

        if pattern:
            # Try API
            data = call_api("kmp" if algo.startswith("KMP") else "rk", textA, textB, pattern=pattern)
            if data and "matchesA" in data:
                matchesA = data["matchesA"]
                matchesB = data["matchesB"]
            else:
                matchesA = [(i, len(pattern)) for i in finder(textA, pattern)]
                matchesB = [(i, len(pattern)) for i in finder(textB, pattern)]
            st.markdown(f"**Occurrences in A:** {len(matchesA)}  |  **in B:** {len(matchesB)}")
            st.markdown("### Highlighted A")
            st.markdown(highlight_matches_html(textA, matchesA), unsafe_allow_html=True)
            st.markdown("### Highlighted B")
            st.markdown(highlight_matches_html(textB, matchesB), unsafe_allow_html=True)
        else:
            chunk = st.slider("Auto-chunk length", 8, 64, 20, step=2)
            # Try API
            data = call_api("kmp" if algo.startswith("KMP") else "rk", textA, textB, pattern=None, chunk=chunk)
            if data and "matchesA" in data:
                matchesA = data["matchesA"]
                matchesB = data["matchesB"]
            else:
                chunksA = set()
                for i in range(0, max(0, len(textA)-chunk+1)):
                    s = textA[i:i+chunk]
                    if s.strip():
                        chunksA.add(s)
                matchesA, matchesB = [], []
                for s in chunksA:
                    for pos in finder(textA, s):
                        matchesA.append((pos, chunk))
                    for pos in finder(textB, s):
                        matchesB.append((pos, chunk))
            st.markdown(f"**Matched chunks in A:** {len(matchesA)}  |  **in B:** {len(matchesB)}")
            st.markdown("### Highlighted A")
            st.markdown(highlight_matches_html(textA, matchesA), unsafe_allow_html=True)
            st.markdown("### Highlighted B")
            st.markdown(highlight_matches_html(textB, matchesB), unsafe_allow_html=True)

# ----- NEW: Single-Input Scanner -----
st.header("Single-Input Scanner")
mode1 = st.radio("Input", ["Paste text", "Upload file"], horizontal=True, key="single")
if mode1 == "Paste text":
    doc = st.text_area("Paste text here", height=240, key="one")
else:
    uf = st.file_uploader("Upload a text file", type=["txt","md","csv","py","java","cpp"])
    doc = uf.read().decode("utf-8", errors="ignore") if uf else ""

colx, coly = st.columns(2)
run_web = colx.button("Run Web Plagiarism Scan (beta)")
run_ai  = coly.button("Check AI-Generated Signals (heuristic)")

if run_web and doc:
    res = scan_text_against_web(doc, max_queries=8)
    st.subheader("Queries used")
    st.write(res["queries"])
    st.subheader("Possible matches (evidence)")
    for m in res["matches"]:
        st.markdown(f"- **[{m['name']}]({m['url']})** — {m['snippet']}")

if run_ai and doc:
    st.subheader("AI-text heuristic score")
    st.json(analyze_style(doc))
