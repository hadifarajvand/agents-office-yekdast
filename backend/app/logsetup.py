"""Make the app's own log lines visible.

Everything under the `ao.*` loggers (context, brain, activity, the boot checks) logs at INFO, but nothing
configured a handler, so Python dropped every line below WARNING and "what was cut, what fell back" never
reached the log. `configure()` gives the `ao` namespace one stderr handler at INFO; it does not touch the root
logger, so library noise (httpx, asyncio) stays as quiet as before. Safe to call from every entry point."""
from __future__ import annotations

import logging


def configure() -> None:
    ao = logging.getLogger("ao")
    ao.setLevel(logging.INFO)
    if any(getattr(h, "_ao", False) for h in ao.handlers):
        return
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    h._ao = True  # type: ignore[attr-defined]
    ao.addHandler(h)
