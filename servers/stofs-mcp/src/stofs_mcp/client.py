"""Async HTTP client for STOFS data on AWS S3 and CO-OPS API."""

from __future__ import annotations

import asyncio
import random
import tempfile
from pathlib import Path
from typing import Any

import httpx

from .models import ESTOFS_CUTOVER_DATE

S3_BASE_2D = "https://noaa-gestofs-pds.s3.amazonaws.com"
S3_BASE_3D = "https://noaa-nos-stofs3d-pds.s3.amazonaws.com"
NOMADS_BASE = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/stofs/prod"
OPENDAP_BASE_2D = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo"
OPENDAP_BASE_3D = "https://nomads.ncep.noaa.gov/dods/stofs_3d_atl"
COOPS_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


# Transient responses worth retrying: rate-limit + the upstream/gateway 5xx
# family that NOAA endpoints intermittently emit under load.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryTransport(httpx.AsyncHTTPTransport):
    """AsyncHTTPTransport that retries idempotent GETs on transient failures.

    httpx's built-in ``retries=`` covers only connection errors; this also
    retries transient HTTP 5xx/429 and timeouts (read included) with
    exponential backoff plus jitter. These servers are read-only and issue
    only GETs, which are safe to replay; non-GET requests and non-transient
    responses pass straight through. Set ``backoff_factor=0`` to retry with
    no delay (used by the test suite).
    """

    def __init__(
        self,
        *args: Any,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return await super().handle_async_request(request)

        last_exc: httpx.TransportError | None = None
        for attempt in range(self._max_retries + 1):
            if attempt:
                delay = self._backoff_factor * (2 ** (attempt - 1))
                await asyncio.sleep(delay + random.uniform(0, delay / 2))
            try:
                response = await super().handle_async_request(request)
            except httpx.TransportError as exc:
                last_exc = exc
                continue
            if response.status_code in _RETRY_STATUS and attempt < self._max_retries:
                await response.aclose()
                continue
            return response
        assert last_exc is not None  # loop ran at least once
        raise last_exc


class STOFSAPIError(Exception):
    """Custom exception for STOFS API errors."""

    pass


class STOFSClient:
    """Async client for downloading STOFS data and fetching CO-OPS observations."""

    def __init__(
        self,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        cycle_cache_ttl: float = 600.0,
    ) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        # Cache the resolved latest cycle per model for a short TTL (read/written
        # by utils.resolve_latest_cycle). Resolving sweeps several S3 HEADs and
        # every forecast tool resolves on each call; a cycle publishes every
        # ~6 h, so a 10-min cache is safe. cycle_cache_ttl=0 disables it (tests).
        self._cycle_cache: dict[str, tuple[float, tuple[str, str]]] = {}
        self._cycle_cache_ttl = cycle_cache_ttl

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,  # NetCDF downloads can be slow
                follow_redirects=True,
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
            )
        return self._client

    async def check_file_exists(self, url: str) -> bool:
        """Check if a file exists on S3/NOMADS using HTTP HEAD."""
        client = await self._get_client()
        try:
            response = await client.head(url)
            return response.status_code == 200
        except Exception:
            return False

    async def download_netcdf(self, url: str) -> Path:
        """Download a NetCDF file to a temporary location.

        Args:
            url: Full HTTPS URL to the NetCDF file.

        Returns:
            Path to the temporary file. Caller must delete it.

        Raises:
            httpx.HTTPStatusError: If the file is not found or request fails.
        """
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        tmp.write(response.content)
        tmp.close()
        return Path(tmp.name)

    async def fetch_coops_observations(
        self,
        station_id: str,
        begin_date: str,
        end_date: str,
        datum: str = "MSL",
    ) -> dict[str, Any]:
        """Fetch CO-OPS observed water levels for comparison.

        Args:
            station_id: CO-OPS station ID (e.g., '8518750').
            begin_date: Start date in YYYYMMDD or 'YYYYMMDD HH:MM' format.
            end_date: End date in YYYYMMDD or 'YYYYMMDD HH:MM' format.
            datum: Vertical datum — 'MSL' for 2D-Global, 'NAVD' for 3D-Atlantic.

        Returns:
            CO-OPS API JSON response with 'data' list.

        Raises:
            ValueError: If the CO-OPS API returns an error.
        """
        client = await self._get_client()
        params = {
            "station": station_id,
            "product": "water_level",
            "datum": datum,
            "units": "metric",
            "time_zone": "gmt",
            "format": "json",
            "begin_date": begin_date,
            "end_date": end_date,
            "application": "stofs_mcp",
        }
        response = await client.get(COOPS_API_BASE, params=params)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(
                f"CO-OPS API error: {data['error'].get('message', 'Unknown error')}"
            )
        return data

    def build_station_url(
        self,
        model: str,
        date: str,
        cycle: str,
        product: str = "cwl",
    ) -> str:
        """Build the AWS S3 URL for a STOFS station NetCDF file.

        Args:
            model: 'two_global' or '3d_atlantic'.
            date: Date in YYYYMMDD format.
            cycle: Cycle hour '00', '06', '12', '18'.
            product: 'cwl', 'htp', or 'swl' (3D only supports 'cwl').

        Returns:
            Full HTTPS URL to the station NetCDF file.
        """
        if model == "2d_global":
            # Pre-cutover cycles are archived under the ESTOFS name.
            prefix = "estofs" if date < ESTOFS_CUTOVER_DATE else "stofs_2d_glo"
            return (
                f"{S3_BASE_2D}/{prefix}.{date}/{prefix}.t{cycle}z.points.{product}.nc"
            )
        elif model == "3d_atlantic":
            return (
                f"{S3_BASE_3D}/STOFS-3D-Atl/stofs_3d_atl.{date}/"
                f"stofs_3d_atl.t{cycle}z.points.cwl.nc"
            )
        else:
            raise ValueError(
                f"Unknown model '{model}'. Use '2d_global' or '3d_atlantic'."
            )

    def build_opendap_url(
        self,
        model: str,
        date: str,
        cycle: str,
        region: str = "conus.east",
    ) -> str:
        """Build the NOMADS OPeNDAP URL for a STOFS regional-grid dataset.

        NOMADS serves STOFS as per-region regular-grid products. Each region
        has its own URL. The path format is:
          /stofs_2d_glo/{YYYYMMDD}/stofs_2d_glo_{region}_{cycle}z

        Available regions (2D): conus.east, conus.west, alaska, hawaii,
        puertori, guam, northpacific.
        Available regions (3D): conus.east only.

        Args:
            model: '2d_global' or '3d_atlantic'.
            date: Date in YYYYMMDD format.
            cycle: Cycle hour '00', '06', '12', '18'.
            region: NOMADS region name (default 'conus.east').

        Returns:
            OPeNDAP URL string.

        Raises:
            ValueError: If model is not '2d_global' or '3d_atlantic'.
        """
        if model == "2d_global":
            return f"{OPENDAP_BASE_2D}/{date}/stofs_2d_glo_{region}_{cycle}z"
        elif model == "3d_atlantic":
            return f"{OPENDAP_BASE_3D}/{date}/stofs_3d_atl_{region}_{cycle}z"
        else:
            raise ValueError(
                f"Unknown model '{model}'. Use '2d_global' or '3d_atlantic'."
            )

    async def check_opendap_available(self, url: str) -> tuple[bool, str]:
        """Check if a NOMADS OPeNDAP dataset endpoint is available.

        Fetches the .das (Dataset Attribute Structure). Three outcomes:
          - Service retired: NOMADS redirects to an HTML page announcing that
            OPeNDAP has been retired (Service Change Notice 25-81, Oct 2025).
          - Dataset missing: NOMADS returns 200 with a body starting with ``Error {``.
          - Dataset available: NOMADS returns 200 with a plain-text .das response.

        Args:
            url: Base OPeNDAP URL (without .das extension).

        Returns:
            (available, reason) — ``available`` is True only when the dataset
            is accessible. ``reason`` is one of: 'ok', 'retired', 'missing',
            'http_error', 'network_error'.
        """
        client = await self._get_client()
        try:
            response = await client.get(f"{url}.das", timeout=15.0)
            body = response.text.strip()
            # NOMADS OPeNDAP was retired Oct 2025 (SCN 25-81). The domain now
            # returns an HTML error page (sometimes via 301) for any /dods/ path.
            if (
                body.startswith("<!doctype html")
                or body.startswith("<html")
                or ("OpenDAP" in body[:200] and "retired" in body)
            ):
                return False, "retired"
            if response.status_code != 200:
                return False, "http_error"
            if body.startswith("Error {"):
                return False, "missing"
            return True, "ok"
        except Exception:
            return False, "network_error"

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
