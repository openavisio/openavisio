"""The statutory numbers behind an Einstufung, and the guards that use them (ADR 042).

Everything here is § 15 SGB XI. It lives in one file so it can be read against the
law instead of hunted through the code, and so a reform is one edit.
"""

# Total weighted points -> Pflegegrad. Lower bound inclusive, upper bound exclusive;
# below 12.5 there is no Pflegegrad at all.
GRADE_THRESHOLDS: list[tuple[float, float, int]] = [
    (12.5, 27.0, 1),
    (27.0, 47.5, 2),
    (47.5, 70.0, 3),
    (70.0, 90.0, 4),
    (90.0, 100.01, 5),  # 100 is attainable, so the top bound has to include it
]

# The six modules, in the order the law numbers them, with the maximum weighted
# points each can contribute. Modules 2 and 3 share one weighting: only the higher
# of the two enters the result, which is why they carry the same maximum and why
# the totals are NOT re-added here (ADR 042).
MODULES: list[tuple[str, str, float]] = [
    ("mobility", "Mobilität", 10.0),
    ("cognitive", "Kognitive und kommunikative Fähigkeiten", 15.0),
    ("behaviour", "Verhaltensweisen und psychische Problemlagen", 15.0),
    ("self_care", "Selbstversorgung", 40.0),
    ("therapy_demands", "Bewältigung von Krankheits- und Therapieanforderungen", 20.0),
    ("daily_life", "Gestaltung des Alltagslebens und sozialer Kontakte", 15.0),
]

MODULE_KEYS: list[str] = [key for key, _, _ in MODULES]
_MODULE_MAX: dict[str, float] = {key: cap for key, _, cap in MODULES}


def grade_for_points(total: float | None) -> int | None:
    """The Pflegegrad a total of weighted points yields, or None if it yields none."""
    if total is None:
        return None
    for low, high, grade in GRADE_THRESHOLDS:
        if low <= total < high:
            return grade
    return None


def points_match_grade(total: float | None, grade: int | None) -> bool:
    """Does the printed total agree with the printed Pflegegrad?

    A model that read the wrong column, or misplaced a decimal separator, almost
    always breaks this. Unknowable (either side missing) counts as agreement: the
    guard exists to catch contradictions, not to demand completeness.
    """
    if total is None or grade is None:
        return True
    return grade_for_points(total) == grade


def modules_within_limits(scores: dict[str, float | None] | None) -> bool:
    """Is every module score inside the points that module can contribute?

    This is the guard that catches the common misread: a Bescheid prints both
    Einzelpunkte and gewichtete Punkte, and only the weighted ones sum to the total.
    Raw points run far higher than the weighted caps, so picking the wrong column
    fails here immediately.
    """
    if not scores:
        return True
    for key, value in scores.items():
        if value is None:
            continue
        cap = _MODULE_MAX.get(key)
        if cap is None or value < 0 or value > cap:
            return False
    return True


def scale_position(total: float | None) -> dict | None:
    """Where a total sits between the thresholds, for the scale in the UI.

    Deliberately not "5 points to Pflegegrad 3": points come out of an assessment of
    actual need, and a difference reads like a target to aim for (ADR 042).
    """
    if total is None:
        return None
    return {
        "total": total,
        "grade": grade_for_points(total),
        "thresholds": [{"from": low, "to": high, "grade": grade}
                       for low, high, grade in GRADE_THRESHOLDS],
    }
