"""Sarvam TTS runtime hardening helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import TypeVar

import aiohttp
from livekit.agents import APIConnectionError
from livekit.agents.utils.connection_pool import ConnectionPool
from livekit.plugins import sarvam
from livekit.plugins.sarvam import tts as sarvam_tts

import config

logger = logging.getLogger("आकृति.sarvam")

T = TypeVar("T")


class NoReuseConnectionPool(ConnectionPool[T]):
    """Close a connection after each use instead of reusing it."""

    def put(self, conn: T) -> None:  # type: ignore[override]
        self.remove(conn)


class StableSarvamTTS(sarvam.TTS):
    """Sarvam TTS with heartbeat-enabled, non-reused websocket sessions."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not config.SARVAM_REUSE_WS_CONNECTIONS:
            self._pool = NoReuseConnectionPool[aiohttp.ClientWebSocketResponse](
                connect_cb=self._connect_ws,
                close_cb=self._close_ws,
                connect_timeout=config.TTS_TIMEOUT_SECONDS,
            )

    async def _connect_ws(self, timeout: float) -> aiohttp.ClientWebSocketResponse:
        session = self._ensure_session()
        headers = {
            "api-subscription-key": self._opts.api_key,
            "User-Agent": sarvam_tts.USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
        }
        ws_url = (
            f"{self._opts.ws_url}?model={self._opts.model}"
            f"&send_completion_event={self._opts.send_completion_event}"
        )

        logger.info(
            "[SARVAM_WS] connecting heartbeat=%ss reuse=%s",
            config.SARVAM_WS_HEARTBEAT_SECONDS,
            config.SARVAM_REUSE_WS_CONNECTIONS,
        )

        try:
            return await asyncio.wait_for(
                session.ws_connect(
                    ws_url,
                    headers=headers,
                    heartbeat=config.SARVAM_WS_HEARTBEAT_SECONDS,
                    autoping=True,
                    autoclose=True,
                ),
                timeout,
            )
        except Exception as exc:
            logger.error("[SARVAM_WS] connect failed: %s", exc, exc_info=True)
            raise APIConnectionError(f"WebSocket connection failed: {exc}") from exc
