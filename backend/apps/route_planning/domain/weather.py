from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class WeatherReading:
    """Normalized forecast values for one location and one forecast hour.

    Rain and snow are mean intensities over the forecast hour (accumulation
    during that hour divided by one hour). Any value may be None when the
    provider has no data for it.
    """

    valid_time: datetime
    wind_mph: Decimal | None
    gust_mph: Decimal | None
    rain_in_per_hr: Decimal | None
    snow_in_per_hr: Decimal | None
    issued_at: datetime
