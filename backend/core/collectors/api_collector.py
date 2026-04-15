"""Generischer REST-API Collector mit Auth, Pagination, Schema-Mapping."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from core.collectors.base_collector import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class APICollector(BaseCollector):
    """
    Generischer HTTP/REST API Collector.
    Unterstützt: API-Key, Bearer Token, Basic Auth, Pagination.
    """

    async def _fetch(self, url: str, **kwargs) -> CollectorResult:
        """Einzelnen API-Endpunkt abrufen."""
        method      = kwargs.get("method", "GET").upper()
        headers     = kwargs.get("headers", {})
        params      = kwargs.get("params", {})
        body        = kwargs.get("body")
        auth_config = kwargs.get("auth_config", {})

        # Auth-Header hinzufügen
        headers = {**headers, **self._build_auth_headers(auth_config)}

        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=body if method in ("POST", "PUT", "PATCH") else None,
            )
            response.raise_for_status()

            # JSON oder Text?
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data    = response.json()
                content = str(data)
            else:
                data    = response.text
                content = data

            return CollectorResult(
                url=url,
                content=content,
                success=True,
                http_status=response.status_code,
                meta_data={"raw_data": data, "content_type": content_type},
                source_type="api",
            )

        except httpx.HTTPStatusError as e:
            return CollectorResult(
                url=url, success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
                http_status=e.response.status_code,
            )

    async def fetch_paginated(
        self,
        url: str,
        page_param: str = "page",
        max_pages: int = 10,
        **kwargs,
    ) -> list[Any]:
        """
        Paginierte API-Daten komplett abrufen.
        Erkennt automatisch Ende wenn Seite leer ist.
        """
        all_data = []
        for page in range(1, max_pages + 1):
            params = {**kwargs.get("params", {}), page_param: page}
            result = await self._fetch(url, params=params, **kwargs)

            if not result.success:
                break

            page_data = result.meta_data.get("raw_data", [])
            if not page_data:
                break

            if isinstance(page_data, list):
                all_data.extend(page_data)
                if len(page_data) == 0:
                    break
            else:
                all_data.append(page_data)
                break  # Kein Array → kein Paging

        return all_data

    def _build_auth_headers(self, auth_config: dict) -> dict:
        """Auth-Header basierend auf Konfiguration erstellen."""
        if not auth_config:
            return {}

        auth_type = auth_config.get("type", "").lower()

        if auth_type == "apikey":
            header_name = auth_config.get("header", "X-API-Key")
            return {header_name: auth_config.get("key", "")}

        elif auth_type == "bearer":
            return {"Authorization": f"Bearer {auth_config.get('token', '')}"}

        elif auth_type == "basic":
            import base64
            creds = base64.b64encode(
                f"{auth_config.get('user', '')}:{auth_config.get('password', '')}".encode()
            ).decode()
            return {"Authorization": f"Basic {creds}"}

        return {}
