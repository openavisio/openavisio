"""Canonical lab vocabulary + reference-range parsing (ADR 028, ADR 029, #73/#78).

The vocabulary is the source of truth for a lab value's identity (`code`) and its
group (`panel`) — not the free-text section heading the OCR/model emitted, which
varies per report and per model. A model only reads values; grouping is ours.
"""
import re

# Canonical panels (small fixed set). Analyte -> (panel, [alias forms, lowercased]).
# Aliases are matched against the printed name normalised (lowercased, ":" stripped,
# whitespace collapsed), with a parenthetical-stripped and a prefix fallback — so
# "Gamma-GT (GGT)" and "GFR nach EKFC-Formel" resolve without listing every variant.
_BB, _DIFF, _CHEM = "Blutbild", "Differentialblutbild", "Klinische Chemie"
_VIT, _COAG, _DRUG = "Vitamine & Spurenelemente", "Gerinnung", "Medikamentenspiegel"

_ANALYTES: dict[str, tuple[str, list[str]]] = {
    # Blutbild
    "hemoglobin": (_BB, ["hämoglobin", "haemoglobin", "hemoglobin", "hb", "hgb"]),
    "hematocrit": (_BB, ["hämatokrit", "haematokrit", "hematocrit", "hkt", "hct"]),
    "rbc": (_BB, ["erythrozyten", "erythrocytes", "rbc", "ery"]),
    "wbc": (_BB, ["leukozyten", "leukocytes", "wbc", "leuko"]),
    "platelets": (_BB, ["thrombozyten", "thrombocytes", "platelets", "plt", "thrombo"]),
    "mcv": (_BB, ["mcv"]),
    "mch": (_BB, ["mch", "hbe"]),
    "mchc": (_BB, ["mchc"]),
    "rdw": (_BB, ["rdw", "evb", "erythrozytenverteilung"]),
    "mpv": (_BB, ["mpv"]),
    # Differentialblutbild
    "neutrophils": (_DIFF, ["neutrophile", "neutrophils", "neutro", "stabkernige", "segmentkernige"]),
    "lymphocytes": (_DIFF, ["lymphozyten", "lymphocytes", "lympho"]),
    "monocytes": (_DIFF, ["monozyten", "monocytes", "mono"]),
    "eosinophils": (_DIFF, ["eosinophile", "eosinophils", "eos"]),
    "basophils": (_DIFF, ["basophile", "basophils", "baso"]),
    # Klinische Chemie
    "sodium": (_CHEM, ["natrium", "sodium", "na"]),
    "potassium": (_CHEM, ["kalium", "potassium", "kal"]),
    "calcium": (_CHEM, ["calcium", "kalzium"]),
    "magnesium": (_CHEM, ["magnesium"]),
    "chloride": (_CHEM, ["chlorid", "chloride"]),
    "phosphate": (_CHEM, ["phosphat", "phosphate"]),
    "creatinine": (_CHEM, ["kreatinin", "creatinin", "creatinine"]),
    "urea": (_CHEM, ["harnstoff", "urea", "bun"]),
    "gfr": (_CHEM, ["gfr", "egfr"]),
    "glucose": (_CHEM, ["glucose", "glukose", "blutzucker"]),
    "bilirubin": (_CHEM, ["bilirubin"]),
    "alt": (_CHEM, ["alt", "gpt", "alat"]),
    "ast": (_CHEM, ["ast", "got", "asat"]),
    "ggt": (_CHEM, ["ggt", "gamma-gt", "gamma-glutamyltransferase", "γ-gt"]),
    "ldh": (_CHEM, ["ldh"]),
    "crp": (_CHEM, ["crp", "c-reaktives protein"]),
    "uric_acid": (_CHEM, ["harnsäure", "uric acid", "urat"]),
    "total_protein": (_CHEM, ["gesamteiweiß", "gesamteiweiss", "gesamtprotein", "total protein"]),
    "albumin": (_CHEM, ["albumin"]),
    "cholesterol": (_CHEM, ["cholesterin", "cholesterol", "gesamtcholesterin"]),
    "hdl": (_CHEM, ["hdl"]),
    "ldl": (_CHEM, ["ldl"]),
    "triglycerides": (_CHEM, ["triglyceride", "triglyzeride", "triglycerides"]),
    "hba1c": (_CHEM, ["hba1c", "hbaic"]),
    "tsh": (_CHEM, ["tsh"]),
    "lipase": (_CHEM, ["lipase"]),
    "amylase": (_CHEM, ["amylase"]),
    "hemolysis_index": (_CHEM, ["serumindex hämolytisch", "hämolyse-index", "serumindex"]),
    # Vitamine & Spurenelemente
    "vitamin_b12": (_VIT, ["vitamin b 12", "vitamin b12", "cobalamin", "b12"]),
    "folate": (_VIT, ["folsäure", "folat", "folate"]),
    "vitamin_d": (_VIT, ["vitamin d", "calcidiol", "calcitriol", "25-oh", "1.25-oh"]),
    "ferritin": (_VIT, ["ferritin"]),
    "iron": (_VIT, ["eisen", "iron"]),
    "zinc": (_VIT, ["zink", "zinc"]),
    "selenium": (_VIT, ["selen", "selenium"]),
    # Gerinnung
    "inr": (_COAG, ["inr"]),
    "aptt": (_COAG, ["aptt", "ptt"]),
    "quick": (_COAG, ["quick", "thromboplastinzeit", "quickwert"]),
    "fibrinogen": (_COAG, ["fibrinogen"]),
    # Medikamentenspiegel
    "valproate": (_DRUG, ["valproinsäure", "valproat", "valproate", "valproic acid"]),
}

# Vital signs and body measurements. Same canonical-code idea as the analytes above,
# but deliberately WITHOUT a panel: a panel is what makes a value a lab result, and a
# weight is a measurement. Codes match the ones the manual entry form writes, so a
# weight typed in by hand and one read out of a doctor's letter land in the same
# series instead of two look-alike groups (#229 follow-up).
_VITALS: dict[str, list[str]] = {
    "body-weight": ["gewicht", "körpergewicht", "koerpergewicht", "weight", "body weight"],
    "body-height": ["größe", "grösse", "groesse", "körpergröße", "koerpergroesse",
                    "länge", "laenge", "height", "body height", "body length"],
    "head-circumference": ["kopfumfang", "kopfumfang (ku)", "ku", "head circumference",
                           "occipitofrontal circumference", "ofc"],
    "body-temperature": ["temperatur", "körpertemperatur", "koerpertemperatur",
                         "temperature", "body temperature", "temp"],
    "heart-rate": ["herzfrequenz", "puls", "pulsfrequenz", "heart rate", "hf", "hr"],
    "oxygen-saturation": ["sauerstoffsättigung", "sauerstoffsaettigung", "spo2", "spo₂",
                          "o2-sättigung", "oxygen saturation", "sao2"],
    "blood-pressure-systolic": ["blutdruck systolisch", "systolisch", "systolischer blutdruck",
                                "rr systolisch", "blood pressure systolic", "systolic"],
    "blood-pressure-diastolic": ["blutdruck diastolisch", "diastolisch", "diastolischer blutdruck",
                                 "rr diastolisch", "blood pressure diastolic", "diastolic"],
    "bmi": ["bmi", "body-mass-index", "body mass index", "körpermassenindex"],
}

_ALIASES: dict[str, str] = {alias: code for code, (_, al) in _ANALYTES.items() for alias in al}
_ALIASES.update({alias: code for code, al in _VITALS.items() for alias in al})
_PANEL_BY_CODE: dict[str, str] = {code: panel for code, (panel, _) in _ANALYTES.items()}
# longest aliases first so a prefix match prefers the more specific name
_ALIASES_BY_LEN: list[tuple[str, str]] = sorted(_ALIASES.items(), key=lambda kv: -len(kv[0]))

# Free-text section headings → canonical panel (substring, lowercased; first match wins,
# so "differentialblutbild" is checked before "blutbild").
_PANEL_NORMALIZE: list[tuple[str, str]] = [
    ("differentialblutbild", _DIFF),
    ("weiße reihe", _DIFF),
    ("weise reihe", _DIFF),
    ("rote reihe", _DIFF),
    ("blutbild", _BB),
    ("hämatologie", _BB),
    ("klinische chemie", _CHEM),
    ("vitamine", _VIT),
    ("spurenelemente", _VIT),
    ("hämostas", _COAG),
    ("gerinnung", _COAG),
    ("pharmako", _DRUG),
]


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().rstrip(":").split())


def canonical_code(display: str | None) -> str | None:
    """Map a printed parameter name to a stable canonical slug, or None if unknown."""
    if not display:
        return None
    for cand in (_norm(display), _norm(re.sub(r"\(.*?\)", "", display))):
        if not cand:
            continue
        if cand in _ALIASES:
            return _ALIASES[cand]
        for alias, code in _ALIASES_BY_LEN:
            if cand == alias or cand.startswith(alias + " "):
                return code
    return None


def resolve_panel(code: str | None, raw_panel: str | None) -> str | None:
    """Canonical panel: from the analyte code if known, else the free-text heading
    normalised to a canonical one, else the cleaned free text, else None."""
    if code and code in _PANEL_BY_CODE:
        return _PANEL_BY_CODE[code]
    if raw_panel:
        low = raw_panel.lower()
        for needle, canon in _PANEL_NORMALIZE:
            if needle in low:
                return canon
        return raw_panel.strip().rstrip(":") or None
    return None


_NUM = r"[-+]?\d+(?:[.,]\d+)?"


def parse_number(raw: object) -> float | None:
    """A printed measurement value as a number, or None if it is not purely one.

    German documents write 13,9 where float() wants 13.9, and a value that fails to
    parse is stored as text — which drops it out of the trend chart and off the unit,
    silently, because the number still shows in the list. parse_reference_range has
    read the comma as a decimal separator all along; this is the same rule for the
    value itself.

    Both separators present: the LAST one is the decimal point (1.234,5 and 1,234.5
    are both 1234.5). A lone comma is a decimal separator, not a thousands one — the
    corpus is German, and a four-digit weight or lab value does not occur. Anything
    that is not purely a number ('< 5', 'negativ', '13,9 kg') stays None and keeps
    its place in value_string.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    s = str(raw).strip()
    if not re.fullmatch(r"[+-]?[\d.,]*\d", s):
        return None
    if "," in s and "." in s:
        dec, thou = (",", ".") if s.rindex(",") > s.rindex(".") else (".", ",")
        s = s.replace(thou, "").replace(dec, ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_reference_range(raw: str | None) -> tuple[float | None, float | None]:
    """Parse a printed reference range into (low, high).

    Handles '4.5-11.0', '4,5 - 11', '< 5', '> 10', 'bis 5', '≥ 2'.
    Returns (None, None) when unparseable.
    ponytail: regex on printed strings; negative-valued ranges (never in labs) would misparse.
    """
    if not raw:
        return None, None
    s = raw.strip().replace("–", "-").replace("—", "-")

    def f(x: str) -> float:
        return float(x.replace(",", "."))

    m = re.search(rf"({_NUM})\s*-\s*({_NUM})", s)
    if m:
        return f(m.group(1)), f(m.group(2))
    m = re.search(rf"(?:<|≤|bis|up to)\s*({_NUM})", s, re.I)
    if m:
        return None, f(m.group(1))
    m = re.search(rf"(?:>|≥)\s*({_NUM})", s)
    if m:
        return f(m.group(1)), None
    return None, None


if __name__ == "__main__":
    # identity
    assert canonical_code("Hämoglobin") == "hemoglobin"
    assert canonical_code("HGB") == "hemoglobin"
    assert canonical_code("Leukozyten:") == "wbc"
    assert canonical_code("Kreatinin") == "creatinine"
    assert canonical_code("Gamma-GT (GGT)") == "ggt"          # parenthetical
    assert canonical_code("GFR nach EKFC-Formel") == "gfr"    # prefix
    assert canonical_code("Vitamin B 12 (Cobalamin)") == "vitamin_b12"
    assert canonical_code("Valproinsäure") == "valproate"
    assert canonical_code("Serumindex hämolytisch") == "hemolysis_index"
    assert canonical_code("Irgendwas Unbekanntes") is None

    # canonical panel wins over free text, and is assigned even when panel is missing
    assert resolve_panel("creatinine", None) == "Klinische Chemie"
    assert resolve_panel("creatinine", "Klinische Chemie, Basisanalytik") == "Klinische Chemie"
    assert resolve_panel("valproate", None) == "Medikamentenspiegel"
    # unknown analyte: normalise the free-text heading
    assert resolve_panel(None, "Differentialblutbild maschinell") == "Differentialblutbild"
    assert resolve_panel(None, "weiße Reihe:") == "Differentialblutbild"
    assert resolve_panel(None, "Something custom") == "Something custom"
    assert resolve_panel(None, None) is None

    assert parse_reference_range("4.5-11.0") == (4.5, 11.0)
    assert parse_reference_range("< 5") == (None, 5.0)
    assert parse_reference_range("> 10") == (10.0, None)
    assert parse_reference_range("negativ") == (None, None)
    print("ok")
