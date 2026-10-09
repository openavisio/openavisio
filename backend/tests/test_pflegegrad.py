"""The statutory arithmetic behind an Einstufung (ADR 042, § 15 SGB XI).

These are the numbers a Bescheid is checked against, so a wrong one here quietly
accepts a misread table or rejects a correct one.
"""

import pytest

from app.services.pflegegrad import (
    MODULE_KEYS,
    grade_for_points,
    modules_within_limits,
    points_match_grade,
    scale_position,
)


@pytest.mark.parametrize("total,grade", [
    (12.5, 1), (26.9, 1),
    (27.0, 2), (42.5, 2), (47.4, 2),
    (47.5, 3), (69.9, 3),
    (70.0, 4), (89.9, 4),
    (90.0, 5), (100.0, 5),
])
def test_the_thresholds_are_the_ones_in_the_law(total, grade):
    assert grade_for_points(total) == grade


@pytest.mark.parametrize("total", [0.0, 12.4])
def test_below_the_first_threshold_there_is_no_pflegegrad(total):
    assert grade_for_points(total) is None


def test_a_boundary_belongs_to_the_higher_grade():
    """47.5 is Pflegegrad 3, not 2. The demo Bescheid got this wrong once."""
    assert grade_for_points(47.5) == 3
    assert grade_for_points(47.4) == 2


def test_a_total_that_contradicts_the_printed_grade_is_rejected():
    assert points_match_grade(42.5, 2) is True
    assert points_match_grade(47.5, 2) is False   # 47.5 is grade 3
    assert points_match_grade(12.0, 1) is False   # below any grade


def test_a_missing_side_is_not_a_contradiction():
    """The guard catches disagreement, it does not demand completeness."""
    assert points_match_grade(None, 2) is True
    assert points_match_grade(42.5, None) is True
    assert points_match_grade(None, None) is True


def test_weighted_module_points_stay_under_their_statutory_caps():
    ok = {"mobility": 10.0, "cognitive": 15.0, "behaviour": 15.0,
          "self_care": 40.0, "therapy_demands": 20.0, "daily_life": 15.0}
    assert modules_within_limits(ok) is True
    assert set(ok) == set(MODULE_KEYS)


def test_the_raw_points_column_breaks_the_caps():
    """The failure this guard exists for: a Bescheid prints Einzelpunkte beside the
    weighted ones, and only the weighted ones add up to the total."""
    assert modules_within_limits({"mobility": 15.0}) is False      # cap is 10
    assert modules_within_limits({"self_care": 54.0}) is False     # cap is 40
    assert modules_within_limits({"daily_life": 20.0}) is False    # cap is 15


def test_nothing_to_check_passes():
    assert modules_within_limits({}) is True
    assert modules_within_limits(None) is True
    assert modules_within_limits({"mobility": None}) is True


def test_an_unknown_module_key_is_refused():
    assert modules_within_limits({"schuhgroesse": 1.0}) is False


def test_the_scale_is_a_position_not_a_distance():
    pos = scale_position(42.5)
    assert pos["total"] == 42.5
    assert pos["grade"] == 2
    assert len(pos["thresholds"]) == 5
    # no "points to the next grade" anywhere: it reads like a target to aim for
    assert not any("to_next" in t or "remaining" in t for t in pos["thresholds"])
    assert scale_position(None) is None
