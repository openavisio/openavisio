from main import _clean_groups


def test_every_name_lands_in_exactly_one_group():
    raw = 'sure: {"groups": [["Dup15q-Syndrom", "Dnp15q-Syndrom", "Invented"], ["Dup15q-Syndrom", "Ataxie"]]}'
    names = ["Dup15q-Syndrom", "Dnp15q-Syndrom", "Ataxie", "Epilepsie"]
    assert _clean_groups(raw, names) == [["Dup15q-Syndrom", "Dnp15q-Syndrom"], ["Ataxie"], ["Epilepsie"]]
