"""
Wetterdaten-Collector: DWD Open Data (primär) + OpenWeatherMap (optional).

DWD: Kostenlos, offiziell, Deutschland-fokussiert.
OpenWeatherMap: Globale Abdeckung, API-Key nötig.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import httpx

from config.settings import get_settings
from models.weather import WeatherData

logger = logging.getLogger(__name__)


class WeatherCollector:
    """
    Holt aktuelle und prognostizierte Wetterdaten.
    Standard: DWD Open Data (kostenlos, kein API-Key).
    Optional: OpenWeatherMap API.
    """

    # DWD API Basis-URL
    DWD_API_BASE = "https://api.brightsky.dev"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def fetch_current(self) -> Optional[WeatherData]:
        """Aktuelles Wetter für konfigurierten Standort holen."""
        if self.settings.use_openweathermap:
            return await self._fetch_owm_current()
        return await self._fetch_dwd_current()

    async def fetch_forecast(self, hours_ahead: int = 48) -> list[WeatherData]:
        """Wetterprognose für die nächsten N Stunden."""
        if self.settings.use_openweathermap:
            return await self._fetch_owm_forecast(hours_ahead)
        return await self._fetch_dwd_forecast(hours_ahead)

    async def fetch_historical(self, date: datetime) -> list[WeatherData]:
        """Historische Wetterdaten für einen Tag."""
        return await self._fetch_dwd_historical(date)

    # ----------------------------------------------------------
    # DWD via BrightSky API (kostenloser DWD-Wrapper)
    # ----------------------------------------------------------

    async def _fetch_dwd_current(self) -> Optional[WeatherData]:
        """
        Aktuelles Wetter via BrightSky (DWD Open Data Wrapper).
        Kein API-Key nötig, offiziell unterstützt.
        """
        params = {
            "lat":  self.settings.weather_lat,
            "lon":  self.settings.weather_lon,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.DWD_API_BASE}/current_weather", params=params)
            response.raise_for_status()
            data = response.json()

        weather_raw = data.get("weather", {})
        station     = data.get("sources", [{}])[0] if data.get("sources") else {}

        return self._dwd_to_model(weather_raw, station, is_forecast=False)

    async def _fetch_dwd_forecast(self, hours_ahead: int = 48) -> list[WeatherData]:
        """Stündliche Prognose via BrightSky."""
        now        = datetime.now(timezone.utc)
        date_from  = now.strftime("%Y-%m-%dT%H:%M")
        date_to    = (now + timedelta(hours=hours_ahead)).strftime("%Y-%m-%dT%H:%M")

        params = {
            "lat":       self.settings.weather_lat,
            "lon":       self.settings.weather_lon,
            "date":      date_from,
            "last_date": date_to,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.DWD_API_BASE}/weather", params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        sources = {s["id"]: s for s in data.get("sources", [])}
        for entry in data.get("weather", []):
            station = sources.get(entry.get("source_id"), {})
            model   = self._dwd_to_model(entry, station, is_forecast=True)
            if model:
                results.append(model)
        return results

    async def _fetch_dwd_historical(self, date: datetime) -> list[WeatherData]:
        """Historische Stundenwerte via BrightSky."""
        date_str = date.strftime("%Y-%m-%d")
        params   = {
            "lat":       self.settings.weather_lat,
            "lon":       self.settings.weather_lon,
            "date":      f"{date_str}T00:00",
            "last_date": f"{date_str}T23:59",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.DWD_API_BASE}/weather", params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        sources = {s["id"]: s for s in data.get("sources", [])}
        for entry in data.get("weather", []):
            station = sources.get(entry.get("source_id"), {})
            model   = self._dwd_to_model(entry, station, is_forecast=False)
            if model:
                results.append(model)
        return results

    def _dwd_to_model(self, data: dict, station: dict, is_forecast: bool) -> Optional[WeatherData]:
        """BrightSky/DWD-Antwort in WeatherData-Model konvertieren."""
        if not data:
            return None

        # Zeitstempel
        timestamp_str = data.get("timestamp")
        if not timestamp_str:
            return None
        try:
            from dateutil import parser as dp
            measured_at = dp.parse(timestamp_str)
        except Exception:
            return None

        station_id = str(station.get("dwd_station_id") or station.get("id") or "unknown")

        return WeatherData(
            station_id          = station_id,
            station_name        = station.get("station_name") or self.settings.weather_location_name,
            latitude            = Decimal(str(station.get("lat") or self.settings.weather_lat)),
            longitude           = Decimal(str(station.get("lon") or self.settings.weather_lon)),
            altitude_m          = Decimal(str(station.get("height", 0))),
            measured_at         = measured_at,
            data_source         = "dwd",
            temp_c              = _dec(data.get("temperature")),
            humidity_pct        = data.get("relative_humidity"),
            pressure_hpa        = _dec(data.get("pressure_msl")),
            wind_speed_ms       = _dec(data.get("wind_speed")),
            wind_gust_ms        = _dec(data.get("wind_gust_speed")),
            wind_direction_deg  = data.get("wind_direction"),
            precipitation_mm    = _dec(data.get("precipitation")),
            snow_depth_cm       = _dec(data.get("snow_depth")),
            cloud_cover_pct     = data.get("cloud_cover"),
            visibility_m        = data.get("visibility"),
            sunshine_min        = _dec(data.get("sunshine")),
            weather_code        = None,  # DWD liefert Strings, nicht numerische Codes
            weather_description = data.get("condition"),
            is_forecast         = is_forecast,
            raw_json            = data,
        )

    # ----------------------------------------------------------
    # OpenWeatherMap (optional)
    # ----------------------------------------------------------

    async def _fetch_owm_current(self) -> Optional[WeatherData]:
        """Aktuelles Wetter via OpenWeatherMap API."""
        params = {
            "lat":   self.settings.weather_lat,
            "lon":   self.settings.weather_lon,
            "appid": self.settings.openweathermap_api_key,
            "units": "metric",
            "lang":  "de",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params=params
            )
            response.raise_for_status()
            data = response.json()

        return self._owm_to_model(data, is_forecast=False)

    async def _fetch_owm_forecast(self, hours_ahead: int = 48) -> list[WeatherData]:
        """5-Tage-Prognose (3h-Intervalle) via OpenWeatherMap."""
        params = {
            "lat":   self.settings.weather_lat,
            "lon":   self.settings.weather_lon,
            "appid": self.settings.openweathermap_api_key,
            "units": "metric",
            "lang":  "de",
            "cnt":   min(hours_ahead // 3, 40),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params=params
            )
            response.raise_for_status()
            data = response.json()

        return [
            self._owm_to_model(entry, is_forecast=True)
            for entry in data.get("list", [])
            if self._owm_to_model(entry, is_forecast=True)
        ]

    def _owm_to_model(self, data: dict, is_forecast: bool) -> Optional[WeatherData]:
        """OpenWeatherMap-Antwort in WeatherData-Model konvertieren."""
        if not data:
            return None

        # Zeitstempel: dt ist Unix-Timestamp
        ts = data.get("dt")
        if not ts:
            return None
        measured_at = datetime.fromtimestamp(ts, tz=timezone.utc)

        main    = data.get("main", {})
        wind    = data.get("wind", {})
        weather = data.get("weather", [{}])[0]
        rain    = data.get("rain", {})
        snow    = data.get("snow", {})

        return WeatherData(
            station_id          = f"owm_{data.get('id', 'unknown')}",
            station_name        = data.get("name") or self.settings.weather_location_name,
            latitude            = Decimal(str(self.settings.weather_lat)),
            longitude           = Decimal(str(self.settings.weather_lon)),
            measured_at         = measured_at,
            data_source         = "openweathermap",
            temp_c              = _dec(main.get("temp")),
            temp_feels_like_c   = _dec(main.get("feels_like")),
            temp_min_c          = _dec(main.get("temp_min")),
            temp_max_c          = _dec(main.get("temp_max")),
            humidity_pct        = main.get("humidity"),
            pressure_hpa        = _dec(main.get("pressure")),
            pressure_sea_hpa    = _dec(main.get("sea_level")),
            wind_speed_ms       = _dec(wind.get("speed")),
            wind_gust_ms        = _dec(wind.get("gust")),
            wind_direction_deg  = wind.get("deg"),
            precipitation_mm    = _dec(rain.get("1h") or rain.get("3h") or 0),
            snow_depth_cm       = _dec(snow.get("1h") or snow.get("3h") or 0),
            cloud_cover_pct     = data.get("clouds", {}).get("all"),
            visibility_m        = data.get("visibility"),
            weather_code        = weather.get("id"),
            weather_description = weather.get("description", ""),
            weather_icon        = weather.get("icon", ""),
            is_forecast         = is_forecast,
            raw_json            = data,
        )


def _dec(value) -> Optional[Decimal]:
    """Sicherer Decimal-Konverter."""
    if value is None:
        return None
    try:
        return Decimal(str(round(float(value), 2)))
    except (ValueError, TypeError):
        return None
