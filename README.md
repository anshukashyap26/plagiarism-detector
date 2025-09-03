# Plagiarism Detector (KMP / Rabin–Karp / LCS)

A fast, privacy-friendly plagiarism detector with:
- **KMP** and **Rabin–Karp** for exact substring matches
- **LCS** (Longest Common Subsequence) for global similarity score
- **Streamlit UI**: upload files or paste text, highlight matches, export results

## ✨ Features
- Upload 2+ text files (txt/csv/md) or paste text
- Choose algorithm: **LCS**, **KMP**, **Rabin–Karp**
- Pairwise LCS similarity matrix (%)
- Highlighted overlapping spans for exact matches
- Zero-storage privacy: Processing is in-memory only

## 🔧 Quickstart
```bash
python -m venv .venv
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```
Open the app at: http://localhost:8501

## 🐳 Docker
```bash
docker build -t plagiarism-detector .
docker run -p 8501:8501 plagiarism-detector
```

## 🚀 Deploy
- **Streamlit Community Cloud**: Connect repo → set `app.py` as entrypoint
- **Render / Railway**: Use the provided `render.yaml` or `Dockerfile`/`Dockerfile.api`

## 🧠 Algorithms
- **KMP**: linear-time pattern matching via prefix function (LPS)
- **Rabin–Karp**: rolling hash for fast multi-search
- **LCS**: DP-based longest common subsequence; we compute `LCS(a,b)/max(|a|,|b|)`

## 🧪 Tests
```bash
pytest -q
```

## REST API
The same algorithms are exposed via FastAPI.

**Run API:**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**POST /api/analyze**
- Body (JSON):
  - `algorithm`: `kmp` | `rk` | `rabin-karp` | `lcs`
  - `textA`, `textB`: strings
  - `pattern` (optional, exact-match modes)
  - `chunk` (optional int, auto-chunk when `pattern` absent)
- Response:
  - `similarity` (for LCS) or `matchesA` / `matchesB` as `(start, len)` tuples.

**Note:** No data is persisted. Add rate limiting / auth if you open this publicly.

## 📄 License
[MIT](LICENSE)

## 🗺️ Roadmap
- [ ] Export HTML/PDF report with highlights
- [ ] Token-level matching (word shingles, Jaccard/BM25)
- [ ] Syntax-aware code mode (strip comments/whitespace)
- [ ] Optional serverless API (FastAPI) for batch jobs
