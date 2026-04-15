"""Wetterdaten-Endpunkte."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from models.weather import WeatherData

router = APIRouter()


@router.get("/current")
async def get_current_weather(db: AsyncSession = Depends(get_db)):
    """Aktuellster Wetterdatensatz."""
    result = await db.execute(
        select(WeatherData)
        .where(WeatherData.is_forecast == False)
        .order_by(desc(WeatherData.measured_at))
        .limit(1)
    )
    data = result.scalar_one_or_none()
    return _weather_to_dict(data) if data else {"error": "Keine Wetterdaten"}


@router.get("/forecast")
async def get_forecast(hours: int = Query(48, ge=1, le=168), db: AsyncSession = Depends(get_db)):
    """Wetterprognose für N Stunden."""
    until  = datetime.utcnow() + timedelta(hours=hours)
    result = await db.execute(
        select(WeatherData)
        .where(WeatherData.is_forecast == True, WeatherData.measured_at <= until)
        .order_by(WeatherData.measured_at)
        .limit(hours)
    )
    return [_weather_to_dict(d) for d in result.scalars()]


@router.get("/history")
async def get_history(
    days:  int = Query(7, ge=1, le=365),
    db:    AsyncSession = Depends(get_db),
):
    """Historische Wetterdaten für N Tage."""
    since  = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(WeatherData)
        .where(WeatherData.is_forecast == False, WeatherData.measured_at >= since)
        .order_by(WeatherData.measured_at)
    )
    return [_weather_to_dict(d) for d in result.scalars()]


@router.post("/fetch")
async def trigger_weather_fetch():
    """Wetterdaten sofort aktualisieren."""
    from core.scheduler.scheduler import get_scheduler
    job_id = await get_scheduler().job_manager.run_weather_job()
    return {"job_id": job_id, "message": "Wetterdaten-Abfrage gestartet"}


def _weather_to_dict(d: WeatherData) -> dict:
    return {
        "station_id":         d.station_id,
        "station_name":       d.station_name,
        "measured_at":        d.measured_at.isoformat(),
        "data_source":        d.data_source,
        "temp_c":             float(d.temp_c) if d.temp_c else None,
        "temp_feels_like_c":  float(d.temp_feels_like_c) if d.temp_feels_like_c else None,
        "humidity_pct":       d.humidity_pct,
        "pressure_hpa":       float(d.pressure_hpa) if d.pressure_hpa else None,
        "wind_speed_ms":      float(d.wind_speed_ms) if d.wind_speed_ms else None,
        "wind_direction_deg": d.wind_direction_deg,
        "precipitation_mm":   float(d.precipitation_mm) if d.precipitation_mm else None,
        "cloud_cover_pct":    d.cloud_cover_pct,
        "weather_description":d.weather_description,
        "weather_icon":       d.weather_icon,
        "is_forecast":        d.is_forecast,
    }
