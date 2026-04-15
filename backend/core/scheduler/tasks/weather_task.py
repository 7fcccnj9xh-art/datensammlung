"""Wetterdaten-Task: Holt aktuelle Daten und speichert in DB."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select

from config.database import get_db_session
from core.collectors.weather_collector import WeatherCollector
from models.weather import WeatherData

logger = logging.getLogger(__name__)


class WeatherTask:
    """Holt Wetterdaten (DWD + optional OWM) und speichert in DB."""

    async def run(self, job_id: Optional[int] = None) -> dict:
        metrics = {"records_saved": 0, "records_skipped": 0, "source": "dwd"}
        collector = WeatherCollector()

        # Aktuelles Wetter
        current = await collector.fetch_current()
        if current:
            saved = await self._save_if_new(current)
            if saved:
                metrics["records_saved"] += 1
            else:
                metrics["records_skipped"] += 1

        # Prognose (nächste 48h)
        forecast = await collector.fetch_forecast(hours_ahead=48)
        for record in forecast:
            saved = await self._save_if_new(record)
            if saved:
                metrics["records_saved"] += 1
            else:
                metrics["records_skipped"] += 1

        logger.info(
            f"Wetter-Task: {metrics['records_saved']} gespeichert, "
            f"{metrics['records_skipped']} übersprungen"
        )
        return metrics

    async def _save_if_new(self, record: WeatherData) -> bool:
        """Datensatz nur speichern wenn noch nicht vorhanden."""
        async with get_db_session() as db:
            existing = await db.execute(
                select(WeatherData.id).where(
                    WeatherData.station_id  == record.station_id,
                    WeatherData.measured_at == record.measured_at,
                    WeatherData.data_source == record.data_source,
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                return False  # Bereits vorhanden

            db.add(record)
        return True
