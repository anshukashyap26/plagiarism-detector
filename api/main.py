from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Tuple, Optional

from algorithms.kmp import kmp_find_all
from algorithms.rabin_karp import rabin_karp_find_all
from algorithms.lcs import lcs_similarity

app = FastAPI(title="Plagiarism Detector API", version="1.0")

# CORS for demos; restrict origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    algorithm: str = Field(pattern=r"^(kmp|rk|rabin-?karp|lcs)$")
    textA: str
    textB: str
    pattern: Optional[str] = None  # for exact-match modes
    chunk: Optional[int] = 20      # auto-chunk length when pattern is None

class AnalyzeResponse(BaseModel):
    algorithm: str
    similarity: Optional[float] = None  # for LCS
    matchesA: Optional[List[Tuple[int, int]]] = None  # (start, len)
    matchesB: Optional[List[Tuple[int, int]]] = None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    algo = req.algorithm.lower()
    if algo in ("lcs",):
        sim = lcs_similarity(req.textA, req.textB)
        return AnalyzeResponse(algorithm="lcs", similarity=round(sim, 6))

    # exact substring modes
    finder = kmp_find_all if algo == "kmp" else rabin_karp_find_all

    if req.pattern:
        pa = finder(req.textA, req.pattern)
        pb = finder(req.textB, req.pattern)
        return AnalyzeResponse(
            algorithm="kmp" if algo == "kmp" else "rabin-karp",
            matchesA=[(i, len(req.pattern)) for i in pa],
            matchesB=[(i, len(req.pattern)) for i in pb],
        )

    # auto-chunk overlap detection
    chunk = max(4, int(req.chunk or 20))
    chunksA = set()
    for i in range(0, max(0, len(req.textA) - chunk + 1)):
        s = req.textA[i:i+chunk]
        if s.strip():
            chunksA.add(s)
    matchesA, matchesB = [], []
    for s in chunksA:
        for pos in finder(req.textA, s):
            matchesA.append((pos, chunk))
        for pos in finder(req.textB, s):
            matchesB.append((pos, chunk))
    return AnalyzeResponse(
        algorithm="kmp" if algo == "kmp" else "rabin-karp",
        matchesA=matchesA,
        matchesB=matchesB,
    )

# Run with: uvicorn api.main:app --host 0.0.0.0 --port 8000
