"""Checkpoint weather-risk classification.

Every threshold is expressed as a band with explicit inclusive/exclusive
bounds so the boundary semantics in the specification are encoded literally.
"""

from dataclasses import dataclass
from decimal import Decimal

from .enums import DataStatus, RiskLevel, WeatherMetric
from .exceptions import InvalidLoadWeight
from .weather import WeatherReading


@dataclass(frozen=True)
class Band:
    level: RiskLevel
    lower: Decimal
    upper: Decimal | None
    lower_inclusive: bool = True
    upper_inclusive: bool = False

    def contains(self, value: Decimal) -> bool:
        below_lower = value < self.lower if self.lower_inclusive else value <= self.lower
        if below_lower:
            return False
        if self.upper is None:
            return True
        return value <= self.upper if self.upper_inclusive else value < self.upper


@dataclass(frozen=True)
class MetricScale:
    metric: WeatherMetric
    unit: str
    bands: tuple[Band, ...]

    def classify(self, value: Decimal) -> Band:
        for band in self.bands:
            if band.contains(value):
                return band
        raise ValueError(f"{self.metric.value} value {value} is outside every band")


def _bands(*spec: tuple[RiskLevel, str, bool, str | None, bool]) -> tuple[Band, ...]:
    return tuple(
        Band(level, Decimal(lower), Decimal(upper) if upper else None, lower_inc, upper_inc)
        for level, lower, lower_inc, upper, upper_inc in spec
    )


WIND_SCALE = MetricScale(
    WeatherMetric.WIND,
    "mph",
    _bands(
        (RiskLevel.LOW, "0", True, "25", False),
        (RiskLevel.MODERATE, "25", True, "35", False),
        (RiskLevel.HIGH, "35", True, "45", False),
        (RiskLevel.SEVERE, "45", True, "55", False),
        (RiskLevel.NO_TRAVEL, "55", True, None, False),
    ),
)

RAIN_SCALE = MetricScale(
    WeatherMetric.RAIN,
    "in/hr",
    _bands(
        (RiskLevel.LOW, "0", True, "0.10", False),
        (RiskLevel.MODERATE, "0.10", True, "0.25", False),
        (RiskLevel.HIGH, "0.25", True, "0.50", False),
        (RiskLevel.SEVERE, "0.50", True, "1.00", True),
        (RiskLevel.NO_TRAVEL, "1.00", False, None, False),
    ),
)

SNOW_SCALE = MetricScale(
    WeatherMetric.SNOW,
    "in/hr",
    _bands(
        (RiskLevel.LOW, "0", True, "0.5", False),
        (RiskLevel.MODERATE, "0.5", True, "1.0", False),
        (RiskLevel.HIGH, "1.0", True, "2.0", False),
        (RiskLevel.SEVERE, "2.0", True, "3.0", True),
        (RiskLevel.NO_TRAVEL, "3.0", False, None, False),
    ),
)


@dataclass(frozen=True)
class LoadRule:
    rule_id: str
    name: str
    wind_band: Band
    load_over_lb: int
    result: RiskLevel

    def applies(self, wind_mph: Decimal, load_lb: int) -> bool:
        return self.wind_band.contains(wind_mph) and load_lb > self.load_over_lb


LOAD_RULES = (
    LoadRule(
        "heavy_load_severe_wind",
        "heavy-load severe-wind rule",
        Band(RiskLevel.SEVERE, Decimal("45"), Decimal("55")),
        30_000,
        RiskLevel.NO_TRAVEL,
    ),
    LoadRule(
        "heavy_load_high_wind",
        "heavy-load wind adjustment",
        Band(RiskLevel.HIGH, Decimal("35"), Decimal("45")),
        40_000,
        RiskLevel.SEVERE,
    ),
)
# Wind of 55 mph or more is No Travel for every load; WIND_SCALE already
# encodes that, so it needs no separate load rule.


@dataclass(frozen=True)
class MetricAssessment:
    metric: WeatherMetric
    value: Decimal | None
    unit: str
    level: RiskLevel | None
    band: str | None
    invalid: bool = False


@dataclass(frozen=True)
class LoadAdjustment:
    rule_id: str
    description: str
    from_level: RiskLevel
    to_level: RiskLevel


@dataclass(frozen=True)
class CheckpointRisk:
    level: RiskLevel | None
    data_status: DataStatus
    metrics: tuple[MetricAssessment, ...]
    load_adjustment: LoadAdjustment | None
    decisive_metrics: tuple[WeatherMetric, ...]
    explanation: str


def validate_load_weight(load_lb: int) -> None:
    if isinstance(load_lb, bool) or not isinstance(load_lb, int):
        raise InvalidLoadWeight("Load weight must be a whole number of pounds.")
    if load_lb < 0:
        raise InvalidLoadWeight("Load weight cannot be negative.")


def describe_band(band: Band, unit: str) -> str:
    lower = _format_number(band.lower)
    if band.upper is None:
        return f"{lower} {unit} or above" if band.lower_inclusive else f"above {lower} {unit}"
    upper = _format_number(band.upper)
    if band.lower == 0:
        return f"below {upper} {unit}"
    if band.upper_inclusive:
        return f"{lower} to {upper} {unit} inclusive"
    return f"{lower} to below {upper} {unit}"


def assess_metric(scale: MetricScale, value: Decimal | None) -> MetricAssessment:
    if value is None:
        return MetricAssessment(scale.metric, None, scale.unit, None, None)
    if not _is_valid_measurement(value):
        return MetricAssessment(scale.metric, None, scale.unit, None, None, invalid=True)
    band = scale.classify(value)
    return MetricAssessment(
        scale.metric, value, scale.unit, band.level, describe_band(band, scale.unit)
    )


def find_load_adjustment(wind: MetricAssessment, load_lb: int) -> LoadAdjustment | None:
    if wind.value is None or wind.level is None:
        return None
    for rule in LOAD_RULES:
        if rule.applies(wind.value, load_lb) and rule.result > wind.level:
            description = (
                f"{rule.name} ({describe_band(rule.wind_band, 'mph')} wind "
                f"with load over {rule.load_over_lb:,} lb)"
            )
            return LoadAdjustment(rule.rule_id, description, wind.level, rule.result)
    return None


def assess_checkpoint(reading: WeatherReading | None, load_lb: int) -> CheckpointRisk:
    validate_load_weight(load_lb)
    if reading is None:
        return _unavailable_risk()

    wind = assess_metric(WIND_SCALE, reading.wind_mph)
    rain = assess_metric(RAIN_SCALE, reading.rain_in_per_hr)
    snow = assess_metric(SNOW_SCALE, reading.snow_in_per_hr)
    metrics = (wind, rain, snow)
    known = [m for m in metrics if m.level is not None]
    if not known:
        return _unavailable_risk(metrics)

    adjustment = find_load_adjustment(wind, load_lb)
    adjusted_wind_level = adjustment.to_level if adjustment else wind.level
    candidates = {m.metric: m.level for m in known}
    if adjusted_wind_level is not None:
        candidates[WeatherMetric.WIND] = adjusted_wind_level

    level = max(candidates.values())
    decisive = tuple(metric for metric, lvl in candidates.items() if lvl == level)
    status = DataStatus.COMPLETE if len(known) == len(metrics) else DataStatus.PARTIAL
    explanation = _explain(level, metrics, adjustment, decisive, load_lb, status)
    return CheckpointRisk(level, status, metrics, adjustment, decisive, explanation)


def _unavailable_risk(metrics: tuple[MetricAssessment, ...] = ()) -> CheckpointRisk:
    if not metrics:
        metrics = tuple(
            MetricAssessment(scale.metric, None, scale.unit, None, None)
            for scale in (WIND_SCALE, RAIN_SCALE, SNOW_SCALE)
        )
    return CheckpointRisk(
        level=None,
        data_status=DataStatus.UNAVAILABLE,
        metrics=metrics,
        load_adjustment=None,
        decisive_metrics=(),
        explanation=(
            "Unknown: no usable forecast is available for the estimated arrival "
            "time, so this checkpoint is not assessed."
        ),
    )


def _explain(
    level: RiskLevel,
    metrics: tuple[MetricAssessment, ...],
    adjustment: LoadAdjustment | None,
    decisive: tuple[WeatherMetric, ...],
    load_lb: int,
    status: DataStatus,
) -> str:
    by_metric = {m.metric: m for m in metrics}
    if level == RiskLevel.LOW:
        values = ", ".join(
            f"{m.metric.value} {_format_measurement(m)}" for m in metrics if m.level is not None
        )
        sentence = f"Low: {values} are below every Moderate threshold."
    else:
        reasons = [_decisive_reason(by_metric[metric], adjustment, load_lb) for metric in decisive]
        sentence = f"{level.label}: " + "; ".join(reasons) + "."

    missing = [m.metric.value for m in metrics if m.level is None]
    if status == DataStatus.PARTIAL:
        sentence += (
            f" {_join_words(missing).capitalize()} data is unavailable, so this is a "
            "minimum classification."
        )
    return sentence


def _decisive_reason(
    assessment: MetricAssessment, adjustment: LoadAdjustment | None, load_lb: int
) -> str:
    measurement = _format_measurement(assessment)
    if assessment.metric == WeatherMetric.WIND and adjustment is not None:
        return (
            f"wind is {measurement} and the load is {load_lb:,} lb, triggering the "
            f"{adjustment.description}"
        )
    return f"{assessment.metric.value} is {measurement} ({assessment.band})"


def _format_measurement(assessment: MetricAssessment) -> str:
    if assessment.value is None:
        return "unavailable"
    return f"{_format_number(assessment.value)} {assessment.unit}"


def _format_number(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{value:.0f}"
    text = f"{value.quantize(Decimal('0.001')):f}".rstrip("0")
    integer, _, fraction = text.partition(".")
    return f"{integer}.{fraction.ljust(2, '0')}"


def _join_words(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + f" and {words[-1]}"


def _is_valid_measurement(value: Decimal) -> bool:
    return value.is_finite() and value >= 0
