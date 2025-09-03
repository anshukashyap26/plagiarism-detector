from algorithms.rabin_karp import rabin_karp_find_all

def test_rk_basic():
    assert rabin_karp_find_all("abracadabra", "abra") == [0, 7]
    assert rabin_karp_find_all("aaaaa", "aa") == [0,1,2,3]
    assert rabin_karp_find_all("abc", "abcd") == []
