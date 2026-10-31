from backend import p_yes


def test_nein_split_into_ne_and_in_counts_as_no():
    # measured on Qwen3.8-27B: "nein" arrives as "ne" + "in"; whole-word matching scored every question yes
    assert p_yes([("ne", -0.02), ("Ne", -4.64), ("ja", -5.14), ("Ja", -7.58)]) < 0.03
    assert p_yes([("ja", -0.01), ("ne", -5.0)]) > 0.9
    assert p_yes([("The", -0.0)]) is None
