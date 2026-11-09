"""Async HTTP client for RTOFS data via HYCOM THREDDS NCSS and OPeNDAP."""

from __future__ import annotations

import asyncio
import csv
import io
import math
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .models import DATASETS, THREDDS_BASE


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


class RTOFSAPIError(Exception):
    """Custom exception for RTOFS API errors."""


class RTOFSClient:
    """Async client for querying RTOFS/ESPC data on HYCOM THREDDS."""

    def __init__(
        self,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        timeout: float = 120.0,
    ) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._timeout = timeout

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
            )
        return self._client

    def build_ncss_url(self, dataset_path: str) -> str:
        """Build the THREDDS NCSS base URL for a dataset."""
        return f"{THREDDS_BASE}/ncss/{dataset_path}"

    async def fetch_point_csv(
        self,
        dataset_key: str,
        variable: str,
        latitude: float,
        longitude: float,
        time: str | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
        vert_coord: float | None = None,
        time_duration: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch point data from THREDDS NCSS as CSV and parse to list of dicts.

        Args:
            dataset_key: Key into DATASETS (e.g., 'ssh', 'sst').
            variable: THREDDS variable name (e.g., 'water_temp', 'surf_el').
            latitude: Latitude in decimal degrees (-80 to 90).
            longitude: Longitude in decimal degrees (-180 to 180).
            time: Single time in ISO format, or 'present'.
            time_start: Start of time range.
            time_end: End of time range.
            vert_coord: Specific depth level in meters. None for all depths or 2D vars.
            time_duration: ISO 8601 duration (e.g. 'PT24H') for a range given by
                only one end. See _time_params for the defaults.

        Returns:
            List of dicts, one per row, with column names as keys.

        Raises:
            RTOFSAPIError: On HTTP or parsing errors.
        """
        ds = DATASETS.get(dataset_key)
        if not ds:
            raise RTOFSAPIError(f"Unknown dataset key '{dataset_key}'")

        url = self.build_ncss_url(ds["path"])
        params: dict[str, str] = {
            "var": variable,
            "latitude": str(latitude),
            "longitude": str(longitude),
            "accept": "csv",
        }
        params.update(_time_params(ds, time, time_start, time_end, time_duration))

        if vert_coord is not None:
            params["vertCoord"] = str(vert_coord)

        client = await self._get_client()
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return _parse_csv(response.text)
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else ""
            raise RTOFSAPIError(
                f"THREDDS NCSS query failed (HTTP {e.response.status_code}): {body}"
            ) from e
        except httpx.TimeoutException as e:
            raise RTOFSAPIError(
                "THREDDS request timed out. Try a smaller time range."
            ) from e
        except RTOFSAPIError:
            raise
        except Exception as e:
            raise RTOFSAPIError(f"THREDDS request failed: {e}") from e

    async def fetch_multi_var_csv(
        self,
        dataset_key: str,
        variables: list[str],
        latitude: float,
        longitude: float,
        time: str | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
        vert_coord: float | None = None,
        time_duration: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch multiple variables from the same dataset in one NCSS request."""
        ds = DATASETS.get(dataset_key)
        if not ds:
            raise RTOFSAPIError(f"Unknown dataset key '{dataset_key}'")

        url = self.build_ncss_url(ds["path"])

        # NCSS supports multiple var params
        params_list: list[tuple[str, str]] = []
        for v in variables:
            params_list.append(("var", v))
        params_list.extend(
            [
                ("latitude", str(latitude)),
                ("longitude", str(longitude)),
                ("accept", "csv"),
            ]
        )
        params_list.extend(_time_params(ds, time, time_start, time_end, time_duration))

        if vert_coord is not None:
            params_list.append(("vertCoord", str(vert_coord)))

        client = await self._get_client()
        try:
            response = await client.get(url, params=params_list)
            response.raise_for_status()
            return _parse_csv(response.text)
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response else ""
            raise RTOFSAPIError(
                f"THREDDS NCSS query failed (HTTP {e.response.status_code}): {body}"
            ) from e
        except httpx.TimeoutException as e:
            raise RTOFSAPIError(
                "THREDDS request timed out. Try a smaller time range."
            ) from e
        except RTOFSAPIError:
            raise
        except Exception as e:
            raise RTOFSAPIError(f"THREDDS request failed: {e}") from e

    async def check_dataset_available(self, dataset_key: str) -> bool:
        """Check if a THREDDS dataset is reachable by querying its DDS."""
        ds = DATASETS.get(dataset_key)
        if not ds:
            return False
        url = f"{THREDDS_BASE}/dodsC/{ds['path']}.dds"
        client = await self._get_client()
        try:
            response = await client.get(url, timeout=15.0)
            return response.status_code == 200
        except Exception:
            return False

    async def get_dataset_time_range(self, dataset_key: str) -> dict[str, Any]:
        """Read a dataset's first and last times from its THREDDS time coordinate.

        Two small OPeNDAP requests: the DAS, for the units of ``time`` (and of
        ``time_run``, the FMRC run times, when the dataset has it), then the
        ASCII values of those coordinates. The first and last times are the
        smallest and largest valid values of ``time``.

        Returns:
            Dict with 'first' and 'last' (ISO 8601 UTC), 'n_time_steps',
            'time_step_hours' (None unless the spacing is uniform),
            'latest_run' (ISO 8601 UTC, or None without ``time_run``),
            'time_units', 'thredds_path' and 'source_url'.

        Raises:
            RTOFSAPIError: Unknown dataset, HTTP failure, or a response whose
                time coordinate cannot be read.
        """
        ds = DATASETS.get(dataset_key)
        if not ds:
            raise RTOFSAPIError(f"Unknown dataset key '{dataset_key}'")

        base = f"{THREDDS_BASE}/dodsC/{ds['path']}"
        client = await self._get_client()
        try:
            das = await client.get(f"{base}.das", timeout=30.0)
            das.raise_for_status()
            time_attrs = _parse_das_attributes(das.text, "time")
            run_attrs = _parse_das_attributes(das.text, "time_run")
            if "units" not in time_attrs:
                raise RTOFSAPIError(
                    f"the DAS of {ds['path']} has no units for 'time' — "
                    "the dataset layout may have changed; check it on HYCOM THREDDS"
                )
            names = ["time"] + (["time_run"] if "units" in run_attrs else [])
            source_url = f"{base}.ascii?{','.join(names)}"
            values = await client.get(source_url, timeout=30.0)
            values.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RTOFSAPIError(
                f"THREDDS OPeNDAP request failed (HTTP {e.response.status_code}) "
                f"for {ds['path']} — try again later or check rtofs_list_datasets"
            ) from e
        except httpx.TimeoutException as e:
            raise RTOFSAPIError(
                f"THREDDS OPeNDAP request timed out for {ds['path']} — try again later"
            ) from e
        except httpx.TransportError as e:
            raise RTOFSAPIError(
                f"could not reach HYCOM THREDDS ({type(e).__name__}) — try again later"
            ) from e

        arrays = _parse_opendap_ascii(values.text)
        times = [
            _cf_time_to_datetime(v, time_attrs["units"], time_attrs.get("calendar"))
            for v in arrays.get("time", [])
            if math.isfinite(v)
        ]
        if not times:
            raise RTOFSAPIError(
                f"no valid values in the time coordinate of {ds['path']} — "
                "the dataset may be updating; try again later"
            )
        times.sort()
        steps = {
            round((b - a).total_seconds() / 3600, 6) for a, b in zip(times, times[1:])
        }
        latest_run = None
        if "time_run" in arrays:
            runs = [
                _cf_time_to_datetime(v, run_attrs["units"], run_attrs.get("calendar"))
                for v in arrays["time_run"]
                if math.isfinite(v)
            ]
            latest_run = _iso_utc(max(runs)) if runs else None
        return {
            "first": _iso_utc(times[0]),
            "last": _iso_utc(times[-1]),
            "n_time_steps": len(times),
            "time_step_hours": steps.pop() if len(steps) == 1 else None,
            "latest_run": latest_run,
            "time_units": time_attrs["units"],
            "thredds_path": ds["path"],
            "source_url": source_url,
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _time_params(
    ds: dict[str, Any],
    time: str | None,
    time_start: str | None,
    time_end: str | None,
    time_duration: str | None,
) -> list[tuple[str, str]]:
    """Build the NCSS time constraint for a point query. Never unbounded.

    ``temporal=all`` reads every step of the ~16-day FMRC aggregation and
    took from 50 s to several minutes, so the tools timed out. A range given
    by only one end is completed with ``time_duration`` (default: the
    dataset's ``default_window_hours``); a request with no time at all gets
    that window starting at 'present'. NCSS clips a window to the data it has.
    """
    if time:
        return [("time", time)]
    if time_start and time_end:
        return [("time_start", time_start), ("time_end", time_end)]
    duration = time_duration or f"PT{ds['default_window_hours']}H"
    if time_end:
        return [("time_end", time_end), ("time_duration", duration)]
    return [("time_start", time_start or "present"), ("time_duration", duration)]


# CF time units as served in the DAS, e.g. "hours since 2026-10-30 12:00:00.000 UTC"
# (time, time_run) or "hours since 2026-10-30T12:00:00Z" (time_offset).
_CF_UNITS_RE = re.compile(
    r"^\s*(?P<unit>seconds?|minutes?|hours?|days?)\s+since\s+"
    r"(?P<date>\d{4}-\d{1,2}-\d{1,2})"
    r"(?:[ T](?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{1,2}(?:\.\d+)?))?)?"
    r"\s*(?P<tz>Z|UTC|GMT|[+-]00:?00)?\s*$",
    re.IGNORECASE,
)
_GREGORIAN_CALENDARS = {"standard", "gregorian", "proleptic_gregorian"}


def _parse_das_attributes(das_text: str, variable: str) -> dict[str, str]:
    """Return the String attributes of one variable's block in an OPeNDAP DAS.

    A block looks like ``    time {`` ... ``String units "hours since ...";``
    ... ``    }``. Returns {} when the variable has no block.
    """
    attrs: dict[str, str] = {}
    inside = False
    for line in das_text.splitlines():
        stripped = line.strip()
        if not inside:
            inside = stripped == f"{variable} {{"
            continue
        if stripped == "}":
            break
        m = re.match(r'String\s+(\w+)\s+"(.*)";$', stripped)
        if m:
            attrs[m.group(1)] = m.group(2)
    return attrs


def _parse_opendap_ascii(text: str) -> dict[str, list[float]]:
    """Parse an OPeNDAP ``.ascii`` response for one-dimensional variables.

    After the DDS and the dashed separator line, each variable is a header
    ``name[N]`` followed by N comma-separated values. Checks that each
    variable has N values.
    """
    parts = re.split(r"^-{3,}\s*$", text, maxsplit=1, flags=re.MULTILINE)
    if len(parts) != 2:
        raise RTOFSAPIError(f"unexpected OPeNDAP ASCII response: {text[:200]!r}")
    body = parts[1]
    arrays: dict[str, list[float]] = {}
    expected: dict[str, int] = {}
    current: str | None = None
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        header = re.fullmatch(r"(\w+)\[(\d+)\]", line)
        if header:
            current = header.group(1)
            expected[current] = int(header.group(2))
            arrays[current] = []
            continue
        if current is None:
            raise RTOFSAPIError(f"unexpected OPeNDAP ASCII line: {line[:200]!r}")
        try:
            arrays[current].extend(float(v) for v in line.split(",") if v.strip())
        except ValueError as e:
            raise RTOFSAPIError(f"non-numeric value for '{current}': {e}") from e
    for name, n in expected.items():
        if len(arrays[name]) != n:
            raise RTOFSAPIError(
                f"OPeNDAP ASCII '{name}' declares {n} values but has {len(arrays[name])}"
            )
    return arrays


def _cf_time_to_datetime(value: float, units: str, calendar: str | None) -> datetime:
    """Convert one CF time value ("<unit> since <UTC date>") to an aware datetime."""
    if calendar and calendar.lower() not in _GREGORIAN_CALENDARS:
        raise RTOFSAPIError(f"unsupported time calendar '{calendar}'")
    m = _CF_UNITS_RE.match(units)
    if not m:
        raise RTOFSAPIError(f"unsupported time units '{units}'")
    year, month, day = (int(x) for x in m.group("date").split("-"))
    seconds = float(m.group("s") or 0)
    origin = datetime(
        year,
        month,
        day,
        int(m.group("h") or 0),
        int(m.group("m") or 0),
        tzinfo=timezone.utc,
    ) + timedelta(seconds=seconds)
    unit = m.group("unit").lower().rstrip("s") + "s"
    return origin + timedelta(**{unit: value})


def _iso_utc(t: datetime) -> str:
    """Format an aware UTC datetime as 'YYYY-MM-DDTHH:MM:SSZ'."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_csv(text: str) -> list[dict[str, Any]]:
    """Parse THREDDS NCSS CSV response into list of dicts.

    Handles the unit annotations in column names like
    'latitude[unit="degrees_north"]' by stripping them.
    Converts numeric values to float.
    """
    if (
        not text.strip()
        or text.strip().startswith("Error")
        or text.strip().startswith("<!")
    ):
        raise RTOFSAPIError(f"THREDDS returned error: {text[:300]}")

    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw_row in reader:
        row: dict[str, Any] = {}
        for key, val in raw_row.items():
            # Strip unit annotations from column names
            clean_key = key.split("[")[0].strip()
            # Try numeric conversion
            try:
                fval = float(val)
                row[clean_key] = fval
            except (ValueError, TypeError):
                row[clean_key] = val
        rows.append(row)
    return rows


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def handle_rtofs_error(e: Exception) -> str:
    """Format an exception into a user-friendly RTOFS error message."""
    if isinstance(e, RTOFSAPIError):
        return f"RTOFS Error: {e}"

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                "THREDDS dataset or variable not found (HTTP 404). "
                "The dataset may be temporarily unavailable. "
                "Use rtofs_list_datasets to check availability."
            )
        return f"THREDDS HTTP {status} error. Please try again."

    if isinstance(e, httpx.TimeoutException):
        return (
            "THREDDS request timed out. RTOFS queries for large areas or many time steps "
            "can be slow. Try a smaller area, fewer time steps, or a single point query."
        )

    if isinstance(e, ValueError):
        return str(e)

    return f"Unexpected error: {type(e).__name__}: {e}"


def compute_auto_stride(
    lat_start: float,
    lat_end: float,
    lon_start: float,
    lon_end: float,
    max_points: int = 50,
    grid_resolution: float = 1.0 / 12.0,
) -> tuple[int, int]:
    """Compute lat/lon stride to keep total grid points under max_points per axis."""
    lat_points = abs(lat_end - lat_start) / grid_resolution
    lon_points = abs(lon_end - lon_start) / grid_resolution

    lat_stride = max(1, int(math.ceil(lat_points / max_points)))
    lon_stride = max(1, int(math.ceil(lon_points / max_points)))

    return lat_stride, lon_stride
