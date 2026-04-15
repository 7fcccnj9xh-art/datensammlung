"""ORM-Model: WeatherData"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, Index, Integer,
    Numeric, SmallInteger, String, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class WeatherData(Base):
    """Wetterdaten-Zeitreihe – optimiert für häufige Abfragen."""

    __tablename__ = "weather_data"

    id:                   Mapped[int]              = mapped_column(BigInteger,    primary_key=True, autoincrement=True)
    station_id:           Mapped[str]              = mapped_column(String(100),   nullable=False)
    station_name:         Mapped[Optional[str]]    = mapped_column(String(200))
    latitude:             Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 5))
    longitude:            Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 5))
    altitude_m:           Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    measured_at:          Mapped[datetime]         = mapped_column(DateTime,      nullable=False)
    data_source:          Mapped[str]              = mapped_column(String(50),    nullable=False, default="dwd")

    # Temperaturen
    temp_c:               Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temp_feels_like_c:    Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temp_min_c:           Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temp_max_c:           Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Luftfeuchte & Druck
    humidity_pct:         Mapped[Optional[int]]    = mapped_column(SmallInteger)
    pressure_hpa:         Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    pressure_sea_hpa:     Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))

    # Wind
    wind_speed_ms:        Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    wind_gust_ms:         Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    wind_direction_deg:   Mapped[Optional[int]]    = mapped_column(SmallInteger)

    # Niederschlag & Schnee
    precipitation_mm:     Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    snow_depth_cm:        Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))

    # Sonstige
    cloud_cover_pct:      Mapped[Optional[int]]    = mapped_column(SmallInteger)
    visibility_m:         Mapped[Optional[int]]    = mapped_column(Integer)
    uv_index:             Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2))
    sunshine_min:         Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Wetter-Beschreibung
    weather_code:         Mapped[Optional[int]]    = mapped_column(SmallInteger)
    weather_description:  Mapped[Optional[str]]    = mapped_column(String(200))
    weather_icon:         Mapped[Optional[str]]    = mapped_column(String(50))

    # Metadaten
    is_forecast:          Mapped[bool]             = mapped_column(Boolean,  nullable=False, default=False)
    raw_json:             Mapped[Optional[dict]]   = mapped_column(JSON)
    created_at:           Mapped[datetime]         = mapped_column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        # UNIQUE: Station + Zeit + Quelle → kein Duplikat
        {"mysql_engine": "InnoDB"},
    )

    def __repr__(self) -> str:
        return f"<WeatherData station={self.station_id!r} at={self.measured_at} temp={self.temp_c}°C>"

    @property
    def wind_speed_kmh(self) -> Optional[float]:
        """Windgeschwindigkeit in km/h."""
        if self.wind_speed_ms is not None:
            return float(self.wind_speed_ms) * 3.6
        return None
