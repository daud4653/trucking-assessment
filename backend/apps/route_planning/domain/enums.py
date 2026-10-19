from enum import IntEnum, StrEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return _RISK_LABELS[self]


_RISK_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}


class SamplingInterval(IntEnum):
    MILES_10 = 10
    MILES_25 = 25
    MILES_50 = 50


class WeatherMetric(StrEnum):
    WIND = "wind"
    RAIN = "rain"
    SNOW = "snow"


class DataStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
