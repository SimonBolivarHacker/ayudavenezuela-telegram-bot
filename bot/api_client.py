"""Cliente HTTP de la API pública de desaparecidos-web.

El bot es stateless: no toca Postgres. Consume los endpoints públicos, que ya
aplican el enmascaramiento de PII y la humanización de fuentes.

La API pública ata `/api/*` a una sesión firmada (anti-scraping): la web emite un
token de sesión en el `Set-Cookie` al servir HTML (`GET /`). Como la cookie es
`Secure` (no viaja sobre HTTP directo al pod), reenviamos el token por el header
`X-App-Session`, que la web también acepta (`security.session_valid`).
"""
import asyncio
import logging

import httpx

from . import config

log = logging.getLogger("desap_bot.api")

_SESSION_COOKIE = "app_sess"


class DesaparecidosAPI:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self._client = httpx.AsyncClient(
            base_url=base_url or config.DESAPARECIDOS_API_URL,
            timeout=timeout or config.HTTP_TIMEOUT,
            headers={"User-Agent": f"desaparecidos-bot/{__import__('bot').__version__}"},
            follow_redirects=True,
        )
        self._session: str | None = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self, force: bool = False):
        if self._session and not force:
            return
        async with self._lock:
            if self._session and not force:
                return
            try:
                r = await self._client.get("/")
                self._session = r.cookies.get(_SESSION_COOKIE)
                if not self._session:
                    log.warning("la web no emitió sesión (status %s)", r.status_code)
            except httpx.HTTPError as e:
                log.warning("no se pudo abrir sesión con la web: %s", e)

    async def _api_get(self, path: str, params: dict | None = None) -> httpx.Response:
        """GET a /api/* con sesión; si expira (403) la renueva y reintenta una vez."""
        await self._ensure_session()
        r = await self._client.get(path, params=params, headers=self._session_headers())
        if r.status_code == 403:
            await self._ensure_session(force=True)
            r = await self._client.get(path, params=params, headers=self._session_headers())
        return r

    def _session_headers(self) -> dict:
        return {"X-App-Session": self._session} if self._session else {}

    async def search(self, term: str):
        """Devuelve lista de fichas, [] si no hay, o None si la API falló."""
        term = (term or "").strip()
        if len(term) < 2:
            return []
        try:
            r = await self._api_get("/api/desaparecidos", params={"q": term})
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except (httpx.HTTPError, ValueError) as e:
            log.warning("búsqueda falló para %r: %s", term, e)
            return None

    async def detail(self, uid: str):
        """Devuelve el dict de la ficha, o None si no existe / falló."""
        try:
            r = await self._api_get(f"/api/desaparecidos/{uid}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and not data.get("error"):
                return data
            return None
        except (httpx.HTTPError, ValueError) as e:
            log.warning("detalle falló para %s: %s", uid, e)
            return None

    async def fetch_photo(self, path: str | None):
        """Descarga best-effort de una foto (/pimg/<token>, sin sesión). None si falla."""
        if not path:
            return None
        try:
            r = await self._client.get(path)
            r.raise_for_status()
            if not r.headers.get("content-type", "").startswith("image/"):
                return None
            return r.content
        except httpx.HTTPError as e:
            log.info("foto no disponible %s: %s", path, e)
            return None

    async def aclose(self):
        await self._client.aclose()
