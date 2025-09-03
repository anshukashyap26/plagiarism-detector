from algorithms.lcs import lcs_similarity

def test_lcs_similarity():
    assert abs(lcs_similarity("abcde", "ace") - 3/5) < 1e-6
    assert lcs_similarity("", "abc") == 0.0
