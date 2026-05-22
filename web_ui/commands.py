from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


_DANGEROUS_PREFIXES = (
    "arm",
    "takeoff",
    "land",
    "disarm",
    "control send on",
    "mission start",
    "set_servo",
    "set_relay",
    "release_payload",
)


@dataclass(slots=True)
class WebCommandResult:
    ok: bool
    message: str
    command: str
    timestamp: float
    dangerous: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CommandHistory:
    def __init__(self, maxlen: int = 200) -> None:
        self._items: deque[WebCommandResult] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, item: WebCommandResult) -> None:
        with self._lock:
            self._items.appendleft(item)

    def list(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._items)
        if limit is not None:
            items = items[: max(0, limit)]
        return [item.to_dict() for item in items]


class WebCommandDispatcher:
    def __init__(
        self,
        handler: Callable[[str], Any] | None,
        history: CommandHistory | None = None,
    ) -> None:
        self.handler = handler
        self.history = history or CommandHistory()

    def dispatch(self, command: str) -> WebCommandResult:
        normalized = " ".join(command.strip().split())
        timestamp = time.time()
        dangerous = is_dangerous_command(normalized)
        if not normalized:
            result = WebCommandResult(False, "empty command", command, timestamp, dangerous)
            self.history.append(result)
            return result
        if self.handler is None:
            result = WebCommandResult(
                False,
                "command handler is unavailable; telemetry/control runtime is not attached",
                normalized,
                timestamp,
                dangerous,
            )
            self.history.append(result)
            return result
        try:
            raw = self.handler(normalized)
            ok = bool(getattr(raw, "ok", False))
            message = str(getattr(raw, "message", raw))
        except Exception as exc:
            ok = False
            message = f"command failed: {exc}"
        result = WebCommandResult(ok, message, normalized, timestamp, dangerous)
        self.history.append(result)
        return result


def is_dangerous_command(command: str) -> bool:
    normalized = " ".join(command.lower().strip().split())
    return any(
        normalized == prefix or normalized.startswith(prefix + " ")
        for prefix in _DANGEROUS_PREFIXES
    )
