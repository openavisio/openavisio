"""Deterministic lab-table parser (ADR 028, #73).

GLM-OCR's Table Recognition emits an HTML <table> with value and reference in
separate cells. Parsing that directly into observations is exact and instant —
no LLM guessing, no timeout. Used for lab pages; prose falls back to the LLM.
stdlib only (html.parser).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

# Header keywords that identify each column (German + English lab reports).
_VALUE_HDR = ("ergebnis", "result", "wert", "value", "messwert", "befund")
_REF_HDR = ("referenz", "reference", "zielbereich", "normbereich", "bereich", "range", "norm")
_UNIT_HDR = ("einheit", "maßeinheit", "masseinheit", "unit", "dimension")

# A cumulative report (Kumulativbefund) has several dated result columns — skip it
# entirely; the current values live on the primary report pages. A date in a value
# cell is likewise history, never a result.
_DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{2,4}\b")

# Sub-qualifier rows under a parameter (e.g. atypical-lymphocyte breakdown), not analytes.
_SKIP_NAMES = {
    "datum", "vermutlich reaktiv", "vermutlich neoplastisch", "diverse/unklare",
    "diverse / unklare", "weiße reihe", "weise reihe", "rote reihe",
}


class _TableCollector(HTMLParser):
    """Collect every <table> as a list of rows; each cell keeps its text, th flag, colspan."""

    def __init__(self):
        super().__init__()
        self.tables: list[list[list[dict]]] = []
        self._table = None
        self._row = None
        self._cell = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            colspan = 1
            for k, v in attrs:
                if k == "colspan":
                    try:
                        colspan = int(v)
                    except ValueError:
                        pass
            self._cell = {"th": tag == "th", "colspan": colspan}
            self._buf = []

    def handle_data(self, data):
        if self._cell is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._cell["text"] = " ".join("".join(self._buf).split())
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


# A value cell starts with a number/comparator, or is a qualitative + / negativ / positiv.
_VALUE_LIKE = re.compile(r"^\s*(?:[<>≤≥]\s*)?[-+]?\d|^\s*[+-]\s*$|^\s*(?:neg|pos)", re.I)
# A reference cell: a range, a comparator bound, or a bare number.
_RANGE_LIKE = re.compile(r"[<>≤≥]|\d\s*[-–]\s*\d|^\s*[-+]?\d")


def _looks_like_lab_rows(table: list[list[dict]]) -> bool:
    """A headerless table is a lab continuation if it has >=2 rows shaped like a lab
    result (a value in col 1 AND a reference in col 2). Counted, not majority — so a
    table dominated by footnotes but carrying a few real rows still qualifies."""
    good = sum(
        1 for r in table
        if len(r) >= 3 and _VALUE_LIKE.match(r[1]["text"]) and _RANGE_LIKE.search(r[2]["text"])
    )
    return good >= 2


def _column_roles(header: list[dict]) -> dict | None:
    """Map a header row to column indices. Returns None if there's no value column."""
    texts = [c["text"].lower() for c in header]
    if sum(1 for h in texts if _DATE_RE.search(h)) >= 2:
        return None  # cumulative report: dated columns, not a single result column
    val = ref = unit = None
    for i, h in enumerate(texts):
        if val is None and any(k in h for k in _VALUE_HDR):
            val = i
        elif ref is None and any(k in h for k in _REF_HDR):
            ref = i
        elif unit is None and any(k in h for k in _UNIT_HDR):
            unit = i
    if val is None:
        return None
    return {"name": 0, "value": val, "ref": ref, "unit": unit}


def parse_lab_tables(text: str) -> list[dict]:
    """Parse lab-result HTML tables in `text` into observation dicts.

    Only tables with a recognizable result column are parsed (so a stray table in
    a letter is ignored). Rows without a result value are omitted — never the
    reference range as the value. Returns [] when nothing lab-like is found.
    """
    if not text or "<table" not in text.lower():
        return []
    collector = _TableCollector()
    collector.feed(text)

    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for table in collector.tables:
        # A cumulative summary (Kumulativbefund) repeats current values with dated,
        # often transposed columns — skip the whole table.
        if "kumulativbefund" in " ".join(c["text"].lower() for r in table for c in r):
            continue
        header = next((r for r in table if any(c["th"] for c in r)), None)
        roles = _column_roles(header) if header else None
        positional = False
        if not roles and header is None and _looks_like_lab_rows(table):
            # headerless page-continuation table: standard German lab column order
            roles = {"name": 0, "value": 1, "ref": 2, "unit": 3}
            positional = True
        if not roles:
            continue
        name_i, val_i, ref_i, unit_i = roles["name"], roles["value"], roles["ref"], roles["unit"]
        panel = None
        for row in table:
            if row is header:
                continue
            # a single wide cell is either a section heading ("Blutbild") or a
            # footnote sentence — treat only short, non-sentence text as a panel so
            # comments don't hijack the grouping; keep the last real heading otherwise.
            if len(row) == 1 and row[0]["colspan"] > 1:
                t = row[0]["text"]
                if t and len(t) <= 40 and not t.endswith("."):
                    panel = t
                continue
            cells = [c["text"] for c in row]
            if val_i >= len(cells):
                continue
            name = cells[name_i].strip() if name_i < len(cells) else ""
            value = cells[val_i].strip()
            if not name or not value:  # omit rows with no legible result
                continue
            if name.lower() in _SKIP_NAMES:  # sub-qualifier row, not a parameter
                continue
            if _DATE_RE.search(value):  # a date cell (cumulative history), not a result
                continue
            if positional and not _VALUE_LIKE.match(value):  # headerless: skip footnote rows
                continue
            # citation/footnote text mis-read as a parameter name (e.g. "(…, PMID …)")
            if name.startswith("(") or "pmid" in name.lower() or len(name) > 48:
                continue
            key = (name.lower(), value)
            if key in seen:  # same parameter+value already captured (repeated section)
                continue
            seen.add(key)
            out.append({
                "type": name,
                "value": value,
                "unit": (cells[unit_i].strip() if unit_i is not None and unit_i < len(cells) else "") or None,
                "reference_range": (cells[ref_i].strip() if ref_i is not None and ref_i < len(cells) else "") or None,
                "panel": panel,
                "category": "lab",
            })
    return out


if __name__ == "__main__":
    sample = (
        '<table><thead><tr><th>Untersuchung</th><th>Ergebnis</th>'
        '<th>Referenz/Zielbereich</th><th>Maßeinheit</th><th>Mat/Meth</th><th>Anm</th></tr></thead>'
        '<tbody>'
        '<tr><td colspan="6">Hämatologie, Basisanalytik</td></tr>'
        '<tr><td colspan="6">Blutbild</td></tr>'
        '<tr><td>Leukozyten</td><td>9.50</td><td>5.1 - 12.9</td><td>G/l</td><td>E</td><td></td></tr>'
        '<tr><td>Hämoglobin</td><td>14.1</td><td>10.7 - 13.9</td><td>g/dl</td><td>E</td><td></td></tr>'
        '<tr><td colspan="6">Die Bestimmung erfolgte nach der enzymatischen Methode.</td></tr>'  # footnote, not a panel
        '<tr><td>Creatinin</td><td>0.4</td><td>0.23-0.46</td><td>mg/dl</td><td>E</td><td></td></tr>'
        '<tr><td>Lymphozyten, atypisch</td><td></td><td></td><td></td><td></td><td></td></tr>'  # no result → skip
        '</tbody></table>'
    )
    obs = parse_lab_tables(sample)
    assert len(obs) == 3, obs
    leuko = obs[0]
    assert leuko["type"] == "Leukozyten" and leuko["value"] == "9.50"
    assert leuko["reference_range"] == "5.1 - 12.9" and leuko["unit"] == "G/l"
    assert leuko["panel"] == "Blutbild" and leuko["category"] == "lab"
    assert obs[1]["type"] == "Hämoglobin" and obs[1]["value"] == "14.1"
    # the footnote must not become a panel — Creatinin stays under Blutbild
    assert obs[2]["type"] == "Creatinin" and obs[2]["panel"] == "Blutbild", obs[2]
    # a non-lab table (no result column) yields nothing
    assert parse_lab_tables("<table><tr><th>Name</th><th>Role</th></tr><tr><td>A</td><td>B</td></tr></table>") == []
    assert parse_lab_tables("plain text, no table") == []

    # cumulative report (dated columns) is skipped entirely
    cumulative = (
        '<table><thead><tr><th>Untersuchung</th><th>18.06.26</th><th>13.01.26</th>'
        '<th>31.03.23</th></tr></thead><tbody>'
        '<tr><td>Leukozyten</td><td>9.50</td><td>8.1</td><td>7.7</td></tr></tbody></table>'
    )
    assert parse_lab_tables(cumulative) == [], parse_lab_tables(cumulative)

    # sub-qualifier rows and date-valued cells are dropped, real params kept
    noisy = (
        '<table><thead><tr><th>Untersuchung</th><th>Ergebnis</th><th>Ref</th>'
        '<th>Einheit</th></tr></thead><tbody>'
        '<tr><td>Lymphozyten, unauffällig</td><td>45</td><td>25 - 50</td><td>%</td></tr>'
        '<tr><td>vermutlich reaktiv</td><td>7</td><td>0</td><td>%</td></tr>'
        '<tr><td>diverse/unklare</td><td>0</td><td>0</td><td>%</td></tr>'
        '<tr><td>Datum</td><td>13.01.26</td><td></td><td></td></tr>'
        '</tbody></table>'
    )
    got = parse_lab_tables(noisy)
    assert [o["type"] for o in got] == ["Lymphozyten, unauffällig"], got

    # headerless continuation table (GLM splits pages), mixed with footnotes:
    # only the real lab rows are parsed; the section header and footnote are dropped.
    headerless = (
        "<table><tbody>"
        "<tr><td>Pharmakologie</td><td></td><td></td><td></td></tr>"
        "<tr><td>Valproinsäure</td><td>41</td><td>50 - 100</td><td>mg/l</td></tr>"
        "<tr><td>Zink</td><td>19.6</td><td>7.7 - 15</td><td>umol/l</td></tr>"
        "<tr><td colspan='4'>Die Analysenmethode wurde von HPLC auf Photometrie umgestellt.</td></tr>"
        "</tbody></table>"
    )
    hl = parse_lab_tables(headerless)
    assert [o["type"] for o in hl] == ["Valproinsäure", "Zink"], hl
    assert hl[0]["value"] == "41" and hl[0]["reference_range"] == "50 - 100"

    # a headerless non-lab table (no numeric values) is left alone
    assert parse_lab_tables("<table><tbody><tr><td>Foo</td><td>bar</td><td>baz</td></tr></tbody></table>") == []

    # a whole Kumulativbefund table is skipped
    kumu = (
        "<table><tbody><tr><td colspan='3'>Kumulativbefund:</td></tr>"
        "<tr><td>Leukozyten</td><td>(5.1 - 12.9)</td><td>10.85</td></tr></tbody></table>"
    )
    assert parse_lab_tables(kumu) == [], parse_lab_tables(kumu)

    # duplicate rows deduped; citation/footnote names dropped
    dupcite = (
        "<table><thead><tr><th>Test</th><th>Ergebnis</th><th>Referenz</th></tr></thead><tbody>"
        "<tr><td>Eisen</td><td>73</td><td>22 - 135</td></tr>"
        "<tr><td>Eisen</td><td>73</td><td>22 - 135</td></tr>"
        "<tr><td>(K.Khan, PMID 30570998 (2023))</td><td>1176</td><td>197 - 771</td></tr>"
        "</tbody></table>"
    )
    assert [o["type"] for o in parse_lab_tables(dupcite)] == ["Eisen"], parse_lab_tables(dupcite)
    print("ok")
