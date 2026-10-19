from decimal import Decimal

import pytest

from apps.route_planning.domain.enums import DataStatus, RiskLevel, WeatherMetric
from apps.route_planning.domain.exceptions import InvalidLoadWeight
from apps.route_planning.domain.risk import (
    RAIN_SCALE,
    SNOW_SCALE,
    WIND_SCALE,
    assess_checkpoint,
    assess_metric,
)
from apps.route_planning.tests.factories import reading

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        ("0", L),
        ("24.9", L),
        ("25", M),
        ("34.9", M),
        ("35", H),
        ("44.9", H),
        ("45", S),
        ("54.9", S),
        ("55", NT),
        ("80", NT),
    ],
)
def test_wind_thresholds(mph, expected):
    assert assess_metric(WIND_SCALE, Decimal(mph)).level == expected


@pytest.mark.parametrize(
    ("in_per_hr", "expected"),
    [
        ("0", L),
        ("0.099", L),
        ("0.10", M),
        ("0.249", M),
        ("0.25", H),
        ("0.499", H),
        ("0.50", S),
        ("1.00", S),
        ("1.001", NT),
        ("2.5", NT),
    ],
)
def test_rain_thresholds(in_per_hr, expected):
    assert assess_metric(RAIN_SCALE, Decimal(in_per_hr)).level == expected


@pytest.mark.parametrize(
    ("in_per_hr", "expected"),
    [
        ("0", L),
        ("0.499", L),
        ("0.5", M),
        ("0.999", M),
        ("1.0", H),
        ("1.999", H),
        ("2.0", S),
        ("3.0", S),
        ("3.001", NT),
    ],
)
def test_snow_thresholds(in_per_hr, expected):
    assert assess_metric(SNOW_SCALE, Decimal(in_per_hr)).level == expected


@pytest.mark.parametrize(
    ("wind", "load", "expected"),
    [
        ("55", 0, NT),
        ("55", 10_000, NT),
        ("45", 30_000, S),
        ("54.9", 30_000, S),
        ("45", 30_001, NT),
        ("54.9", 30_001, NT),
        ("35", 40_000, H),
        ("44.9", 40_000, H),
        ("35", 40_001, S),
        ("44.9", 40_001, S),
        ("34.9", 80_000, M),
        ("44.9", 80_000, S),
    ],
)
def test_load_adjusted_wind(wind, load, expected):
    assert assess_checkpoint(reading(wind=wind), load).level == expected


def test_load_rules_do_not_affect_precipitation():
    risk = assess_checkpoint(reading(wind="10", rain="0.30", snow="1.5"), 80_000)
    assert risk.level == H
    assert risk.load_adjustment is None


def test_highest_metric_wins_and_all_decisive_metrics_are_reported():
    risk = assess_checkpoint(reading(wind="46", rain="0.6", snow="0.2"), 10_000)
    assert risk.level == S
    assert set(risk.decisive_metrics) == {WeatherMetric.WIND, WeatherMetric.RAIN}


def test_load_adjustment_can_be_the_deciding_factor():
    risk = assess_checkpoint(reading(wind="42", rain="0.3"), 45_000)
    assert risk.level == S
    assert risk.decisive_metrics == (WeatherMetric.WIND,)
    assert risk.load_adjustment is not None
    assert risk.load_adjustment.from_level == H
    assert risk.load_adjustment.to_level == S
    assert risk.explanation.startswith("Severe: wind is 42 mph and the load is 45,000 lb")
    assert "heavy-load wind adjustment" in risk.explanation


def test_explanation_reflects_actual_measurement_and_band():
    risk = assess_checkpoint(reading(rain="0.31"), 10_000)
    assert risk.explanation == "High: rain is 0.31 in/hr (0.25 to below 0.50 in/hr)."


def test_low_explanation_lists_measurements():
    risk = assess_checkpoint(reading(wind="12", rain="0.02", snow="0"), 10_000)
    assert risk.level == L
    assert "wind 12 mph" in risk.explanation


def test_missing_reading_is_unknown_not_low():
    risk = assess_checkpoint(None, 10_000)
    assert risk.level is None
    assert risk.data_status == DataStatus.UNAVAILABLE


def test_all_metrics_missing_is_unknown():
    risk = assess_checkpoint(reading(wind=None, rain=None, snow=None), 10_000)
    assert risk.level is None
    assert risk.data_status == DataStatus.UNAVAILABLE


def test_partially_missing_metrics_give_minimum_classification():
    risk = assess_checkpoint(reading(wind="30", rain="0", snow=None), 10_000)
    assert risk.level == M
    assert risk.data_status == DataStatus.PARTIAL
    assert "minimum classification" in risk.explanation
    assert "Snow data is unavailable" in risk.explanation


@pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity"])
def test_invalid_measurements_are_treated_as_missing(bad):
    risk = assess_checkpoint(reading(wind=bad, rain="0", snow="0"), 10_000)
    wind = next(m for m in risk.metrics if m.metric == WeatherMetric.WIND)
    assert wind.invalid
    assert wind.level is None
    assert risk.data_status == DataStatus.PARTIAL


@pytest.mark.parametrize("load", [-1, -40_000])
def test_negative_load_is_rejected(load):
    with pytest.raises(InvalidLoadWeight):
        assess_checkpoint(reading(), load)


@pytest.mark.parametrize("load", [1.5, True, "1000"])
def test_non_integer_load_is_rejected(load):
    with pytest.raises(InvalidLoadWeight):
        assess_checkpoint(reading(), load)
