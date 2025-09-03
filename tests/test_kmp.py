from algorithms.kmp import kmp_find_all

def test_kmp_basic():
    assert kmp_find_all("ababcabcababd", "ababd") == [7]
    assert kmp_find_all("aaaaa", "aa") == [0,1,2,3]
    assert kmp_find_all("abc", "abcd") == []
