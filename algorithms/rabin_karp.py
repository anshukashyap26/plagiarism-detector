def rabin_karp_find_all(t: str, p: str, base: int = 256, mod: int = 10**9 + 7):
    n, m = len(t), len(p)
    if m == 0 or m > n:
        return []
    h = hp = 0
    power = 1
    for _ in range(m-1):
        power = (power * base) % mod
    for i in range(m):
        h = (h * base + ord(t[i])) % mod
        hp = (hp * base + ord(p[i])) % mod
    res = []
    for i in range(n-m+1):
        if h == hp and t[i:i+m] == p:
            res.append(i)
        if i < n-m:
            h = ((h - ord(t[i]) * power) * base + ord(t[i+m])) % mod
            if h < 0:
                h += mod
    return res
