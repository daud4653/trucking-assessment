"""Distance-weighted route risk aggregation.

Each checkpoint's classification is attributed to the miles it represents
(see checkpointing). Rules:

* Miles whose checkpoint has no usable forecast are "unknown" and are never
  counted in any risk level.
* A checkpoint with some metrics missing is classified from the metrics that
  are present. That level is a lower bound, so its miles count toward that
  level, but they do not count as covered.
* Average risk is the mean severity score (Low=0 ... No Travel=4) weighted by
  miles, over miles with a known level only. It is None when nothing is known.
* Coverage is the share of route miles backed by complete forecasts. Below
  MIN_COVERAGE_RATIO the route is uncertain.

Miles are rounded to 0.01 mi (half-even) and the average to 0.001 after
summation, so ranking compares the same values the API reports.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from .enums import DataStatus, RiskLevel
from .risk import CheckpointRisk

MIN_COVERAGE_RATIO = Decimal("0.95")
MILES_QUANTUM = Decimal("0.01")
SCORE_QUANTUM = Decimal("0.001")
RATIO_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True)
class AttributedRisk:
    represented_miles: float
    risk: CheckpointRisk


@dataclass(frozen=True)
class RouteRiskSummary:
    total_miles: Decimal
    miles_by_level: dict[RiskLevel, Decimal]
    unknown_miles: Decimal
    partial_miles: Decimal
    coverage_ratio: Decimal
    average_risk: Decimal | None
    peak_level: RiskLevel | None
    no_travel_checkpoints: int

    @property
    def severe_or_worse_miles(self) -> Decimal:
        return self.miles_by_level[RiskLevel.SEVERE] + self.miles_by_level[RiskLevel.NO_TRAVEL]

    @property
    def high_miles(self) -> Decimal:
        return self.miles_by_level[RiskLevel.HIGH]

    @property
    def has_no_travel(self) -> bool:
        return self.no_travel_checkpoints > 0

    @property
    def is_uncertain(self) -> bool:
        return self.coverage_ratio < MIN_COVERAGE_RATIO


def summarize_route(total_miles: float, attributed: Iterable[AttributedRisk]) -> RouteRiskSummary:
    if total_miles <= 0:
        raise ValueError("Route distance must be positive.")
    by_level = {level: 0.0 for level in RiskLevel}
    unknown = partial = complete = weighted_score = known = 0.0
    peak: RiskLevel | None = None
    no_travel_checkpoints = 0

    for item in attributed:
        miles = item.represented_miles
        level = item.risk.level
        if level is None:
            unknown += miles
            continue
        by_level[level] += miles
        known += miles
        weighted_score += miles * int(level)
        peak = level if peak is None else max(peak, level)
        no_travel_checkpoints += level == RiskLevel.NO_TRAVEL
        if item.risk.data_status == DataStatus.COMPLETE:
            complete += miles
        else:
            partial += miles

    return RouteRiskSummary(
        total_miles=_miles(total_miles),
        miles_by_level={level: _miles(value) for level, value in by_level.items()},
        unknown_miles=_miles(unknown),
        partial_miles=_miles(partial),
        coverage_ratio=_quantize(Decimal(complete / total_miles), RATIO_QUANTUM).min(Decimal(1)),
        average_risk=_quantize(Decimal(weighted_score / known), SCORE_QUANTUM) if known else None,
        peak_level=peak,
        no_travel_checkpoints=no_travel_checkpoints,
    )


def _miles(value: float) -> Decimal:
    return _quantize(Decimal(value), MILES_QUANTUM)


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)
