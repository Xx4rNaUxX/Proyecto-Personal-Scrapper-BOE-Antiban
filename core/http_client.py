"""
Core - Cliente HTTP compartido con reintentos, rate-limiting y cache.
Todas las peticiones de los tres engines pasan por aquí.
"""
import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("arbitraje.http")


class RateLimiter:
    """Rate limiter por dominio para respetar los servidores públicos."""

    def __init__(self, requests_per_second: float = 1.0):
        self._min_interval = 1.0 / requests_per_second
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, domain: str):
        async with self._lock:
            now = time.monotonic()
            last = self._last_request.get(domain, 0)
            wait_time = self._min_interval - (now - last)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request[domain] = time.monotonic()


class DiskCache:
    """Cache en disco para evitar descargas repetidas de pliegos/PDFs/XMLs."""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[bytes]:
        path = self.cache_dir / self._key(url)
        if path.exists():
            # Cache válido por 24h
            if time.time() - path.stat().st_mtime < 86400:
                return path.read_bytes()
            path.unlink()
        return None

    def put(self, url: str, data: bytes):
        path = self.cache_dir / self._key(url)
        path.write_bytes(data)


class HttpClient:
    """
    Cliente HTTP async compartido.
    - Rate limiting por dominio (1 req/s por defecto para fuentes públicas)
    - Reintentos con backoff exponencial
    - Cache en disco para PDFs y XMLs
    - User-Agent respetuoso
    """

    def __init__(
        self,
        requests_per_second: float = 1.0,
        max_retries: int = 3,
        timeout: float = 30.0,
        cache_dir: str = "data/cache",
    ):
        self.rate_limiter = RateLimiter(requests_per_second)
        self.max_retries = max_retries
        self.timeout = timeout
        self.cache = DiskCache(cache_dir)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "ArbitrajeBot/1.0 (Investigacion Academica; "
                        "contacto@ejemplo.es) Python/httpx"
                    ),
                    "Accept": "application/xml, application/atom+xml, "
                              "application/json, text/html, */*",
                    "Accept-Language": "es-ES,es;q=0.9",
                },
                http2=True,
            )
        return self._client

    async def get(
        self,
        url: str,
        use_cache: bool = True,
        raw: bool = False,
    ) -> bytes | str:
        """
        GET con rate-limiting, reintentos y cache.
        raw=True devuelve bytes (para PDFs), raw=False devuelve texto.
        """
        # Intentar cache primero
        if use_cache:
            cached = self.cache.get(url)
            if cached is not None:
                logger.debug(f"Cache HIT: {url[:80]}")
                return cached if raw else cached.decode("utf-8", errors="replace")

        # Extraer dominio para rate limiting
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        client = await self._get_client()

        for attempt in range(1, self.max_retries + 1):
            try:
                await self.rate_limiter.wait(domain)
                logger.debug(f"GET ({attempt}/{self.max_retries}): {url[:100]}")

                response = await client.get(url)
                response.raise_for_status()

                data = response.content
                # Guardar en cache
                if use_cache:
                    self.cache.put(url, data)

                return data if raw else data.decode("utf-8", errors="replace")

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - esperar más
                    wait = 2 ** attempt * 5
                    logger.warning(f"Rate limited en {domain}. Esperando {wait}s...")
                    await asyncio.sleep(wait)
                elif e.response.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning(f"Error {e.response.status_code} en {url}. Reintento en {wait}s")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"HTTP {e.response.status_code}: {url}")
                    raise

            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                wait = 2 ** attempt
                logger.warning(f"Error conexión: {e}. Reintento en {wait}s")
                await asyncio.sleep(wait)

        raise ConnectionError(f"Agotados {self.max_retries} reintentos para {url}")

    async def get_xml(self, url: str) -> str:
        """Descarga XML/ATOM como texto."""
        return await self.get(url, raw=False)

    async def get_pdf(self, url: str) -> bytes:
        """Descarga PDF como bytes."""
        return await self.get(url, raw=True)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
