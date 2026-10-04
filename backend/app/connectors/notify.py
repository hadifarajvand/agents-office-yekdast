"""Tells the OWNER (never a client) that something needs them: a gate, a parked job, a finished job,
a production result. Telegram when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in the
environment (config holds the names only); otherwise nothing is sent and the Jobs screen's
"Needs you" list is the only signal.

Messages carry the job title, the stage and a link to the office page, nothing from the brief
or the evidence, so a leaked chat holds no client data beyond a title."""
from __future__ import annotations

import logging
import os

import httpx

from ..config import load_config

log = logging.getLogger("agents_office.notify")


class NullNotifier:
    enabled = False

    async def send(self, text: str) -> bool:
        return False


class TelegramNotifier:
    enabled = True

    def __init__(self, token: str, chat_id: str, http: httpx.AsyncClient | None = None):
        self._token, self._chat, self._http = token, chat_id, http

    async def send(self, text: str) -> bool:
        client = self._http or httpx.AsyncClient(timeout=10)
        try:
            r = await client.post(f"https://api.telegram.org/bot{self._token}/sendMessage",
                                  json={"chat_id": self._chat, "text": text[:900], "disable_web_page_preview": True})
            return r.status_code == 200
        except httpx.HTTPError as e:
            log.warning("telegram notify failed: %s", type(e).__name__)  # never log the URL: it holds the token
            return False
        finally:
            if self._http is None:
                await client.aclose()


def from_config():
    n = load_config().notify
    token, chat = os.environ.get(n.get("telegram_token_env", ""), ""), os.environ.get(n.get("telegram_chat_env", ""), "")
    return TelegramNotifier(token, chat) if token and chat else NullNotifier()
