import time
from algorithms.kmp import kmp_find_all
from algorithms.rabin_karp import rabin_karp_find_all
from algorithms.lcs import lcs_similarity

text = "abcd" * 50_000
pat = "bcda"

for name, fn in [("KMP", kmp_find_all), ("Rabin–Karp", rabin_karp_find_all)]:
    t0 = time.time()
    _ = fn(text, pat)
    print(name, "secs:", round(time.time()-t0, 4))

print("LCS 5k vs 5k (short demo)")
a = "abcde" * 1000
b = "abXde" * 1000
print(lcs_similarity(a, b))
