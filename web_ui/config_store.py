from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from typing import Any

import yaml


class MissionConfigStore:
    def __init__(self, path_getter, reload_handler=None) -> None:
        self._path_getter = path_getter
        self._reload_handler = reload_handler
        self._lock = threading.RLock()

    def read(self) -> dict[str, Any]:
        path = self._path()
        if path is None:
            return {"ok": False, "path": None, "yaml": "", "data": None, "message": "no mission config path"}
        with self._lock:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text) or {}
        return {"ok": True, "path": str(path), "yaml": text, "data": data, "message": "ok"}

    def patch(self, yaml_text: str) -> dict[str, Any]:
        path = self._path()
        if path is None:
            return {"ok": False, "path": None, "message": "no mission config path"}
        try:
            parsed = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as exc:
            return {"ok": False, "path": str(path), "message": f"invalid yaml: {exc}"}
        if not isinstance(parsed, dict):
            return {"ok": False, "path": str(path), "message": "mission config must be a YAML mapping"}

        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=str(path.parent),
                text=True,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(yaml_text)
                    if yaml_text and not yaml_text.endswith("\n"):
                        handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, path)
            except Exception:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
                raise
        return {"ok": True, "path": str(path), "data": parsed, "message": "mission config saved"}

    def reload(self) -> dict[str, Any]:
        if self._reload_handler is None:
            return {"ok": False, "message": "reload handler is unavailable"}
        try:
            raw = self._reload_handler()
            return {"ok": bool(getattr(raw, "ok", False)), "message": str(getattr(raw, "message", raw))}
        except Exception as exc:
            return {"ok": False, "message": f"reload failed: {exc}"}

    def _path(self) -> Path | None:
        value = self._path_getter()
        if not value:
            return None
        return Path(value).expanduser().resolve()


class ConfigFileStore:
    def __init__(self, allowed_paths: dict[str, Path]) -> None:
        self.allowed_paths = {name: path.expanduser().resolve() for name, path in allowed_paths.items()}
        self._lock = threading.RLock()

    def list(self) -> dict[str, Any]:
        return {
            "ok": True,
            "items": [
                {"name": name, "path": str(path), "exists": path.exists()}
                for name, path in self.allowed_paths.items()
            ],
        }

    def read(self, name: str) -> dict[str, Any]:
        path = self._path(name)
        if path is None:
            return {"ok": False, "message": f"unknown config: {name}", "path": None}
        if not path.exists():
            return {"ok": False, "message": f"config does not exist: {path}", "path": str(path)}
        with self._lock:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text) or {}
        return {"ok": True, "name": name, "path": str(path), "yaml": text, "data": data, "message": "ok"}

    def patch(self, name: str, yaml_text: str) -> dict[str, Any]:
        path = self._path(name)
        if path is None:
            return {"ok": False, "message": f"unknown config: {name}", "path": None}
        try:
            parsed = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as exc:
            return {"ok": False, "message": f"invalid yaml: {exc}", "path": str(path)}
        if not isinstance(parsed, dict):
            return {"ok": False, "message": "config must be a YAML mapping", "path": str(path)}

        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=str(path.parent),
                text=True,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(yaml_text)
                    if yaml_text and not yaml_text.endswith("\n"):
                        handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, path)
            except Exception:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
                raise
        return {"ok": True, "name": name, "path": str(path), "data": parsed, "message": "config saved"}

    def _path(self, name: str) -> Path | None:
        return self.allowed_paths.get(name)
