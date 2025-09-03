def kmp_build_lps(p: str):
    lps, j = [0]*len(p), 0
    for i in range(1, len(p)):
        while j and p[i] != p[j]:
            j = lps[j-1]
        if p[i] == p[j]:
            j += 1
            lps[i] = j
    return lps

def kmp_find_all(t: str, p: str):
    if not p or not t or len(p) > len(t):
        return []
    lps, res, j = kmp_build_lps(p), [], 0
    for i, ch in enumerate(t):
        while j and ch != p[j]:
            j = lps[j-1]
        if ch == p[j]:
            j += 1
            if j == len(p):
                res.append(i-j+1)
                j = lps[j-1]
    return res
