from __future__ import annotations

from dataclasses import dataclass

from web_ui.commands import WebCommandDispatcher, is_dangerous_command


@dataclass(slots=True)
class DummyResult:
    ok: bool
    message: str


def test_web_command_dispatcher_calls_handler_and_records_history() -> None:
    calls: list[str] = []

    def handle(command: str) -> DummyResult:
        calls.append(command)
        return DummyResult(True, f"handled {command}")

    dispatcher = WebCommandDispatcher(handle)

    result = dispatcher.dispatch("  control   send off  ")

    assert result.ok is True
    assert result.command == "control send off"
    assert calls == ["control send off"]
    assert dispatcher.history.list()[0]["message"] == "handled control send off"


def test_web_command_dispatcher_records_handler_failure() -> None:
    def handle(_command: str) -> DummyResult:
        raise RuntimeError("boom")

    dispatcher = WebCommandDispatcher(handle)

    result = dispatcher.dispatch("mission current")

    assert result.ok is False
    assert "boom" in result.message
    assert dispatcher.history.list()[0]["ok"] is False


def test_dangerous_command_detection() -> None:
    assert is_dangerous_command("control send on")
    assert is_dangerous_command("set_servo 9 1200")
    assert not is_dangerous_command("control send off")

