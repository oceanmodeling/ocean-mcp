"""Async HTTP client for ERDDAP servers."""

from __future__ import annotations

import asyncio
import ipaddress
import random
import socket
import ssl
import time
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

# A caller supplies `server_url` to every tool, so an unguarded client is an
# SSRF primitive: `http://169.254.169.254/` (cloud metadata), `http://localhost`,
# or any RFC1918 address would be fetched. We allow only http(s) to hosts that
# resolve exclusively to public IPs, and re-check every redirect hop.
_MAX_REDIRECTS = 5


class ERDDAPSecurityError(ValueError):
    """Raised when a request URL is blocked by the SSRF guard."""


def _validate_public_http_url(url: str) -> None:
    """Reject non-HTTP(S) schemes and hosts resolving to non-public IPs.

    Raises ERDDAPSecurityError if the URL is unsafe to fetch. DNS is resolved
    and *every* returned address is checked, so a name that resolves to a mix
    of public and private addresses is still rejected.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ERDDAPSecurityError(
            f"Blocked URL scheme {parsed.scheme or '(none)'!r}; "
            f"only http/https are allowed: {url}"
        )
    host = parsed.hostname
    if not host:
        raise ERDDAPSecurityError(f"URL has no host: {url}")
    try:
        infos = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ERDDAPSecurityError(f"Could not resolve host {host!r}: {e}") from e
    for info in infos:
        addr = info[4][0].split("%")[0]  # strip IPv6 zone id
        ip = ipaddress.ip_address(addr)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ERDDAPSecurityError(
                f"Blocked request to non-public address {ip} "
                f"(host {host!r}): refusing potential SSRF."
            )


# Transient responses worth retrying: rate-limit + the upstream/gateway 5xx
# family that NOAA endpoints intermittently emit under load.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def cert_verify_error(exc: BaseException) -> ssl.SSLCertVerificationError | None:
    """The TLS certificate-verification failure behind ``exc``, if there is one.

    httpx raises it as ConnectError <- httpcore.ConnectError <-
    ssl.SSLCertVerificationError, so walk the cause/context chain. Re-raised
    exceptions can make that chain loop, hence the visited set.
    """
    visited: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in visited:
        if isinstance(current, ssl.SSLCertVerificationError):
            return current
        visited.add(id(current))
        current = current.__cause__ or current.__context__
    return None


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
                # A certificate the CA bundle cannot verify fails the same
                # way every time; retrying only delays the error.
                if cert_verify_error(exc) is not None:
                    raise
                last_exc = exc
                continue
            if response.status_code in _RETRY_STATUS and attempt < self._max_retries:
                await response.aclose()
                continue
            return response
        assert last_exc is not None  # loop ran at least once
        raise last_exc


class ERDDAPClient:
    """Async client for ERDDAP REST API."""

    def __init__(
        self,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        search_cache_ttl: float = 600.0,
    ) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        # Cache dataset-search responses per (server, query, page) for a short
        # TTL — the catalog changes rarely and the same search is often
        # repeated within a session. search_cache_ttl=0 disables it (tests).
        self._search_cache: dict[tuple, tuple[float, dict]] = {}
        self._search_cache_ttl = search_cache_ttl

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Redirects are followed manually so each hop is SSRF-checked;
            # httpx auto-redirect would let an allowed host bounce us to an
            # internal address.
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=False,
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
            )
        return self._client

    async def _get_json(self, url: str) -> dict:
        """Fetch a URL and return parsed JSON, handling ERDDAP error responses."""
        client = await self._get_client()
        redirects = 0
        while True:
            _validate_public_http_url(url)
            response = await client.get(url)
            if response.is_redirect and response.headers.get("location"):
                redirects += 1
                if redirects > _MAX_REDIRECTS:
                    raise ERDDAPSecurityError(
                        f"Too many redirects (>{_MAX_REDIRECTS}) starting from {url}"
                    )
                url = urljoin(url, response.headers["location"])
                continue
            break

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "html" in content_type and "json" not in content_type:
            raise ValueError(
                f"ERDDAP returned HTML instead of JSON. This usually means an error occurred. "
                f"URL: {url}"
            )

        return response.json()

    async def search(
        self,
        server_url: str,
        search_for: str,
        page: int = 1,
        items_per_page: int = 20,
    ) -> dict:
        """Search for datasets on an ERDDAP server.

        Args:
            server_url: Base ERDDAP server URL.
            search_for: Free-text search terms.
            page: Page number (1-indexed).
            items_per_page: Results per page.

        Returns:
            Raw ERDDAP JSON response.
        """
        key = (server_url, search_for, page, items_per_page)
        now = time.monotonic()
        hit = self._search_cache.get(key)
        if hit is not None and now - hit[0] < self._search_cache_ttl:
            return hit[1]

        encoded_search = quote(search_for)
        url = (
            f"{server_url}/search/index.json"
            f"?searchFor={encoded_search}"
            f"&page={page}"
            f"&itemsPerPage={items_per_page}"
        )
        result = await self._get_json(url)
        self._search_cache[key] = (now, result)
        return result

    async def get_info(self, server_url: str, dataset_id: str) -> dict:
        """Get dataset metadata/info.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/info/{dataset_id}/index.json"
        return await self._get_json(url)

    async def get_tabledap(
        self,
        server_url: str,
        dataset_id: str,
        query: str,
    ) -> dict:
        """Fetch data from a tabledap dataset.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.
            query: Pre-built query string (variables & constraints).

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/tabledap/{dataset_id}.json"
        if query:
            url += f"?{query}"
        return await self._get_json(url)

    async def get_griddap(
        self,
        server_url: str,
        dataset_id: str,
        query: str,
    ) -> dict:
        """Fetch data from a griddap dataset.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.
            query: Pre-built griddap query with bracket notation.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/griddap/{dataset_id}.json?{query}"
        return await self._get_json(url)

    async def get_all_datasets(
        self,
        server_url: str,
        query: str = "",
    ) -> dict:
        """List all datasets on an ERDDAP server.

        Args:
            server_url: Base ERDDAP server URL.
            query: Optional query string for filtering.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/tabledap/allDatasets.json"
        if query:
            url += f"?{query}"
        return await self._get_json(url)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
