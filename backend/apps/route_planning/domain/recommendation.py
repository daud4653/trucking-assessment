"""Deterministic route ranking.

Routes are first split into screening tiers so that a route which violates
the thresholds, or whose weather could not be assessed, never silently
outranks a fully assessed route:

    1. ASSESSED      - forecast coverage sufficient, no No Travel segment
    2. UNCERTAIN     - coverage below the minimum, no known No Travel segment
    3. NO_TRAVEL     - at least one checkpoint classified No Travel

Within a tier the specified lexicographic policy applies:

    severe-or-worse miles, high miles, average risk, travel time

with the provider's route order as the final, stable tie-breaker. A route
with no known miles at all sorts last within its tier on average risk.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum

from .aggregation import RouteRiskSummary


class ScreeningTier(IntEnum):
    ASSESSED = 0
    UNCERTAIN = 1
    NO_TRAVEL = 2


@dataclass(frozen=True)
class RankingCandidate:
    route_id: str
    label: str
    provider_order: int
    duration_seconds: int
    summary: RouteRiskSummary


@dataclass(frozen=True)
class RankedRoute:
    route_id: str
    rank: int
    tier: ScreeningTier
    explanation: str


_UNKNOWN_AVERAGE = Decimal("Infinity")


def screening_tier(summary: RouteRiskSummary) -> ScreeningTier:
    if summary.has_no_travel:
        return ScreeningTier.NO_TRAVEL
    if summary.is_uncertain:
        return ScreeningTier.UNCERTAIN
    return ScreeningTier.ASSESSED


def ranking_key(candidate: RankingCandidate) -> tuple[int, Decimal, Decimal, Decimal, int, int]:
    summary = candidate.summary
    average = summary.average_risk if summary.average_risk is not None else _UNKNOWN_AVERAGE
    return (
        int(screening_tier(summary)),
        summary.severe_or_worse_miles,
        summary.high_miles,
        average,
        candidate.duration_seconds,
        candidate.provider_order,
    )


def rank_routes(candidates: list[RankingCandidate]) -> list[RankedRoute]:
    ordered = sorted(candidates, key=ranking_key)
    ranked = []
    for position, candidate in enumerate(ordered):
        reference = ordered[position - 1] if position else ordered[min(1, len(ordered) - 1)]
        explanation = _explain_position(candidate, reference, position, len(ordered))
        tier = screening_tier(candidate.summary)
        ranked.append(RankedRoute(candidate.route_id, position + 1, tier, explanation))
    return ranked


_TIER_PREDICATES = {
    ScreeningTier.ASSESSED: "is fully assessed with no No Travel segment",
    ScreeningTier.UNCERTAIN: "has incomplete forecast coverage",
    ScreeningTier.NO_TRAVEL: "contains a No Travel segment",
}


def _explain_position(
    candidate: RankingCandidate, reference: RankingCandidate, position: int, total: int
) -> str:
    if total == 1:
        return "Only route returned by the routing provider; there is nothing to compare."
    prefix = f"Ranked {_ordinal(position + 1)}"
    return f"{prefix}: {_deciding_reason(candidate, reference, better=position == 0)}."


def _deciding_reason(candidate: RankingCandidate, reference: RankingCandidate, better: bool) -> str:
    a, b = candidate.summary, reference.summary
    tier_a, tier_b = screening_tier(a), screening_tier(b)
    other = reference.label
    if tier_a != tier_b:
        return f"this route {_TIER_PREDICATES[tier_a]}, whereas {other} {_TIER_PREDICATES[tier_b]}"
    if a.severe_or_worse_miles != b.severe_or_worse_miles:
        word = "fewer" if better else "more"
        return (
            f"{word} severe-or-worse miles than {other} "
            f"({a.severe_or_worse_miles} vs {b.severe_or_worse_miles})"
        )
    if a.high_miles != b.high_miles:
        word = "fewer" if better else "more"
        return f"{word} high-risk miles than {other} ({a.high_miles} vs {b.high_miles})"
    if a.average_risk != b.average_risk:
        word = "lower" if better else "higher"
        return (
            f"same severe and high mileage as {other}, {word} average risk "
            f"({_score(a.average_risk)} vs {_score(b.average_risk)})"
        )
    if candidate.duration_seconds != reference.duration_seconds:
        word = "shorter" if better else "longer"
        return (
            f"same weather risk as {other}, {word} travel time "
            f"({_hours(candidate.duration_seconds)} vs {_hours(reference.duration_seconds)})"
        )
    return (
        f"identical risk and travel time to {other}; ordered by the routing provider's preference"
    )


def _score(value: Decimal | None) -> str:
    return "unknown" if value is None else f"{value:.2f}"


def _hours(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    return f"{hours}h {remainder // 60:02d}m"


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third"}.get(n, f"#{n}")
