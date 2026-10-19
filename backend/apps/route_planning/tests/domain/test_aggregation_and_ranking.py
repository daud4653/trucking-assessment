from decimal import Decimal

import pytest

from apps.route_planning.domain.aggregation import AttributedRisk, summarize_route
from apps.route_planning.domain.enums import RiskLevel
from apps.route_planning.domain.recommendation import (
    RankingCandidate,
    ScreeningTier,
    rank_routes,
)
from apps.route_planning.domain.risk import assess_checkpoint
from apps.route_planning.tests.factories import reading

LOW = {"wind": "5"}
MODERATE = {"wind": "30"}
HIGH = {"wind": "40"}
SEVERE = {"wind": "50"}
NO_TRAVEL = {"wind": "60"}
MISSING = None


def summary(*stretches: tuple[float, dict | None], load: int = 10_000):
    items = [
        AttributedRisk(miles, assess_checkpoint(reading(**w) if w else None, load))
        for miles, w in stretches
    ]
    return summarize_route(sum(m for m, _ in stretches), items)


def candidate(route_id: str, order: int, duration: int, stretches) -> RankingCandidate:
    return RankingCandidate(route_id, f"Route {route_id}", order, duration, summary(*stretches))


def order(candidates) -> list[str]:
    return [r.route_id for r in rank_routes(candidates)]


def test_miles_are_attributed_by_distance_not_checkpoint_count():
    s = summary((5, LOW), (90, HIGH), (5, LOW))
    assert s.miles_by_level[RiskLevel.HIGH] == Decimal("90.00")
    assert s.miles_by_level[RiskLevel.LOW] == Decimal("10.00")
    assert s.average_risk == Decimal("1.800")
    assert s.coverage_ratio == Decimal("1.0000")


def test_sampling_density_does_not_change_distance_weighted_result():
    coarse = summary((50, LOW), (50, SEVERE))
    fine = summary(*([(10, LOW)] * 5 + [(10, SEVERE)] * 5))
    assert coarse.miles_by_level == fine.miles_by_level
    assert coarse.average_risk == fine.average_risk


def test_missing_weather_is_unknown_not_low():
    s = summary((50, LOW), (50, MISSING))
    assert s.unknown_miles == Decimal("50.00")
    assert s.miles_by_level[RiskLevel.LOW] == Decimal("50.00")
    assert s.coverage_ratio == Decimal("0.5000")
    assert s.is_uncertain
    assert s.average_risk == Decimal("0.000")


def test_fully_missing_route_has_no_average():
    s = summary((100, MISSING))
    assert s.average_risk is None
    assert s.peak_level is None


def test_partial_metrics_count_toward_level_but_not_coverage():
    items = [AttributedRisk(100, assess_checkpoint(reading(wind="40", snow=None), 10_000))]
    s = summarize_route(100, items)
    assert s.miles_by_level[RiskLevel.HIGH] == Decimal("100.00")
    assert s.partial_miles == Decimal("100.00")
    assert s.coverage_ratio == Decimal("0")
    assert s.is_uncertain


def test_fewer_severe_miles_wins():
    a = candidate("a", 0, 3600, [(80, LOW), (20, SEVERE)])
    b = candidate("b", 1, 9000, [(90, LOW), (10, SEVERE)])
    assert order([a, b]) == ["b", "a"]


def test_severe_miles_take_precedence_over_high_miles():
    a = candidate("a", 0, 3600, [(50, HIGH), (50, LOW)])
    b = candidate("b", 1, 3600, [(5, SEVERE), (95, LOW)])
    assert order([b, a]) == ["a", "b"]


def test_high_miles_take_precedence_over_average_risk():
    a = candidate("a", 0, 3600, [(10, HIGH), (90, LOW)])
    b = candidate("b", 1, 3600, [(5, HIGH), (95, MODERATE)])
    assert order([a, b]) == ["b", "a"]


def test_average_risk_takes_precedence_over_travel_time():
    a = candidate("a", 0, 1000, [(50, MODERATE), (50, LOW)])
    b = candidate("b", 1, 9000, [(100, LOW)])
    assert order([a, b]) == ["b", "a"]


def test_travel_time_breaks_equal_risk():
    a = candidate("a", 0, 5000, [(100, LOW)])
    b = candidate("b", 1, 4000, [(100, LOW)])
    ranked = rank_routes([a, b])
    assert [r.route_id for r in ranked] == ["b", "a"]
    assert "shorter travel time" in ranked[0].explanation


def test_identical_inputs_rank_deterministically_by_provider_order():
    a = candidate("a", 0, 4000, [(100, LOW)])
    b = candidate("b", 1, 4000, [(100, LOW)])
    for permutation in ([a, b], [b, a]):
        assert order(permutation) == ["a", "b"]


def test_no_travel_route_ranks_last_and_is_flagged():
    clean_but_severe = candidate("a", 0, 9000, [(40, SEVERE), (60, LOW)])
    prohibited = candidate("b", 1, 3000, [(1, NO_TRAVEL), (99, LOW)])
    ranked = rank_routes([prohibited, clean_but_severe])
    assert [r.route_id for r in ranked] == ["a", "b"]
    assert ranked[1].tier == ScreeningTier.NO_TRAVEL
    assert "No Travel" in ranked[1].explanation


def test_uncertain_route_does_not_outrank_assessed_route():
    assessed = candidate("a", 0, 9000, [(30, HIGH), (70, LOW)])
    mostly_unknown = candidate("b", 1, 3000, [(10, LOW), (90, MISSING)])
    ranked = rank_routes([mostly_unknown, assessed])
    assert [r.route_id for r in ranked] == ["a", "b"]
    assert ranked[1].tier == ScreeningTier.UNCERTAIN
    assert "incomplete forecast coverage" in ranked[1].explanation


def test_explanation_names_the_deciding_criterion():
    a = candidate("a", 0, 3600, [(80, LOW), (20, SEVERE)])
    b = candidate("b", 1, 9000, [(100, LOW)])
    ranked = rank_routes([a, b])
    assert ranked[0].explanation == (
        "Ranked first: fewer severe-or-worse miles than Route a (0.00 vs 20.00)."
    )
    assert ranked[1].explanation.startswith("Ranked second: more severe-or-worse miles")


def test_single_route_explanation():
    ranked = rank_routes([candidate("a", 0, 3600, [(100, LOW)])])
    assert ranked[0].rank == 1
    assert "Only route" in ranked[0].explanation


@pytest.mark.parametrize("load", [30_000, 30_001])
def test_load_threshold_changes_route_tier(load):
    s = summary((10, {"wind": "50"}), (90, LOW), load=load)
    assert s.has_no_travel is (load > 30_000)
