from dikwp_vita.runproof import deterministic_probe

def test_runproof_is_valid_and_stable():
    a = deterministic_probe(128)
    b = deterministic_probe(128)
    assert a["proof_valid"] is True
    assert a["digest"] == b["digest"]
