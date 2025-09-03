def lcs_similarity(a: str, b: str) -> float:
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0.0
    dp = [0] * (m + 1)
    for i in range(1, n + 1):
        prev = 0
        for j in range(1, m + 1):
            cur = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = cur
    l = dp[m]
    return l / max(n, m)
