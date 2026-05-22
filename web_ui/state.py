from __future__ import annotations

import math
import threading
import time
from typing import Any


def _clean(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    return _clean(getattr(obj, name, default))


class WebStateProvider:
    def __init__(self, runner: Any | None = None, *, yolo_mjpeg_url: str = "/video/yolo.mjpeg") -> None:
        self.runner = runner
        self.yolo_mjpeg_url = yolo_mjpeg_url
        self._lock = threading.Lock()

    def snapshot(self, command_history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        now = time.time()
        runner = self.runner
        state = _default_state(now, self.yolo_mjpeg_url)
        if runner is None:
            state["commands"]["history"] = command_history or []
            return state

        config = getattr(runner, "config", None)
        services = getattr(runner, "services", None)
        link_status = _safe_call(services, "get_link_status")
        drone = _safe_call(services, "get_drone_state")
        perception = _safe_call(services, "get_perception", now)
        scene = _safe_call(services, "get_scene_detections", now)
        switches = getattr(runner, "controller_switches", None)
        controller = _safe_call(switches, "snapshot")

        source = _attr(getattr(config, "telemetry", None), "active_source", "UNKNOWN")
        state["link"].update(
            {
                "source": source,
                "connected": bool(_attr(link_status, "connected", _attr(drone, "connected", False))),
                "mode": _attr(drone, "mode", "UNKNOWN"),
                "armed": bool(_attr(drone, "armed", False)),
                "status": _attr(link_status, "status_text", "disconnected"),
                "transport": _attr(link_status, "transport", ""),
            }
        )
        state["drone"].update(
            {
                "lat": _attr(drone, "lat") if _attr(drone, "global_position_valid", False) else None,
                "lon": _attr(drone, "lon") if _attr(drone, "global_position_valid", False) else None,
                "alt": _attr(drone, "relative_altitude") if _attr(drone, "relative_alt_valid", False) else None,
                "battery": _attr(drone, "battery_remaining") if _attr(drone, "battery_valid", False) else None,
                "voltage": _attr(drone, "battery_voltage") if _attr(drone, "battery_valid", False) else None,
            }
        )
        with getattr(runner, "control_command_log_lock", self._lock):
            state["mission"].update(
                {
                    "name": getattr(runner, "latest_mission_name", _attr(config, "mission_name", "UNKNOWN")),
                    "stage": getattr(runner, "latest_mission_stage", "UNKNOWN"),
                    "stage_controller": getattr(runner, "latest_stage_controller", "UNKNOWN"),
                    "hold_reason": getattr(runner, "latest_hold_reason", "") or "none",
                }
            )
            state["logs"]["recent"] = list(getattr(runner, "control_command_log", []))[:40]
        state["control"].update(
            {
                "send_commands": bool(_attr(controller, "send_commands", False)),
                "gimbal": bool(_attr(controller, "gimbal", False)),
                "body": bool(_attr(controller, "body", False)),
                "approach": bool(_attr(controller, "approach", False)),
            }
        )
        state["target"].update(
            {
                "valid": bool(_attr(perception, "target_valid", False)),
                "track_id": _none_if_negative(_attr(perception, "track_id")),
                "class_name": _attr(perception, "class_name", ""),
                "confidence": _attr(perception, "confidence"),
                "state": _attr(perception, "tracking_state", "lost"),
                "ex": _attr(perception, "ex"),
                "ey": _attr(perception, "ey"),
                "size": _attr(perception, "target_size"),
            }
        )
        state["scene"].update(
            {
                "valid": bool(_attr(scene, "valid", False)),
                "count": len(getattr(scene, "detections", []) or []),
                "frame_id": _attr(scene, "frame_id"),
            }
        )
        state["commands"]["history"] = command_history or []
        return state


def _default_state(now: float, yolo_mjpeg_url: str) -> dict[str, Any]:
    return {
        "timestamp": now,
        "link": {"source": "UNKNOWN", "connected": False, "mode": "UNKNOWN", "armed": False, "status": "disconnected", "transport": ""},
        "drone": {"lat": None, "lon": None, "alt": None, "battery": None, "voltage": None},
        "mission": {"name": "UNKNOWN", "stage": "UNKNOWN", "stage_controller": "UNKNOWN", "hold_reason": "none"},
        "control": {"send_commands": False, "gimbal": False, "body": False, "approach": False},
        "target": {"valid": False, "track_id": None, "class_name": "", "confidence": None, "state": "lost", "ex": None, "ey": None, "size": None},
        "scene": {"valid": False, "count": 0, "frame_id": None},
        "video": {"url": "/video/yolo.mjpeg", "source_url": yolo_mjpeg_url, "frame_age_ms": None, "stream_fps": None},
        "logs": {"recent": []},
        "commands": {"history": []},
    }


def _safe_call(obj: Any, name: str, *args: Any) -> Any:
    if obj is None:
        return None
    method = getattr(obj, name, None)
    if not callable(method):
        return None
    try:
        return method(*args)
    except Exception:
        return None


def _none_if_negative(value: Any) -> Any:
    if isinstance(value, (int, float)) and value < 0:
        return None
    return value
