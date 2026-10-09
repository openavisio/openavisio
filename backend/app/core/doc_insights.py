"""Condense a document's extraction into what the documents list shows.

The extraction JSON is rich (summary, observations, medications, …) but only
ever read on the detail page. The list showed a cryptic file name instead, so
a caregiver had to open every document to find out what was in it.

Strictly DESCRIPTIVE: what a document contains, never what it means. We do not
compare values against reference ranges, rank them by severity, or flag them —
that is software-authored prioritisation of clinical significance, which
`docs/regulatory-positioning.md` commits to avoiding (#113). The counts say
"47 values are in here"; they must never say "this one is worrying".
"""


def build_insights(entities: dict | None) -> dict | None:
    """Summary, issuer and content counts for one document. None if nothing useful."""
    if not isinstance(entities, dict):
        return None
    observations = [o for o in (entities.get("observations") or []) if isinstance(o, dict)]
    insights = {
        "summary": (entities.get("summary") or None),
        "provider": (entities.get("provider") or None),
        "observations": len(observations),
        "medications": len(entities.get("medications") or []),
        "diagnoses": len(entities.get("diagnoses") or []),
        "recommendations": len(entities.get("recommendations") or []),
    }
    if not any(insights.values()):
        return None
    return insights


if __name__ == "__main__":
    obs = [
        {"type": "Kalium", "value": "5.8", "unit": "mmol/l", "reference_range": "3.5 - 5.1"},
        {"type": "Leukozyten", "value": "10.85", "unit": "G/l", "reference_range": "5.1 - 12.9"},
    ]
    full = build_insights({
        "summary": "Hämolyse", "provider": "MVZ", "observations": obs,
        "medications": [{"name": "VPA"}], "recommendations": ["Kontrolle"],
    })
    assert full["observations"] == 2 and full["medications"] == 1 and full["recommendations"] == 1
    assert full["provider"] == "MVZ"
    # the out-of-range potassium is counted, never judged
    assert "abnormal" not in full

    assert build_insights(None) is None
    assert build_insights({"observations": [], "summary": ""}) is None
    print("ok")
