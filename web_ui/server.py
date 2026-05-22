from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from missions.rescue_competition.mission import RescueStage
from missions.registry import available_mission_names
from web_ui.commands import CommandHistory, WebCommandDispatcher
from web_ui.config_store import ConfigFileStore, MissionConfigStore
from web_ui.processes import YoloProcessManager
from web_ui.state import WebStateProvider
from web_ui.video_proxy import proxy_mjpeg_stream


STATIC_DIR = Path(__file__).resolve().parent / "static"


class CommandRequest(BaseModel):
    command: str


class MissionConfigPatch(BaseModel):
    yaml: str


def create_app(
    *,
    command_handler: Callable[[str], Any] | None = None,
    state_provider: WebStateProvider | None = None,
    config_store: MissionConfigStore | None = None,
    yolo_process: YoloProcessManager | None = None,
    yolo_mjpeg_url: str = "http://127.0.0.1:8010/video.mjpeg",
) -> FastAPI:
    app = FastAPI(title="UAV Web Ground Station", version="0.1.0")
    history = CommandHistory()
    dispatcher = WebCommandDispatcher(command_handler, history)
    provider = state_provider or WebStateProvider(yolo_mjpeg_url=yolo_mjpeg_url)
    store = config_store or MissionConfigStore(lambda: None)
    project_root = Path(__file__).resolve().parent.parent
    system_store = ConfigFileStore(
        {
            "app": project_root / "config" / "app.yaml",
            "telemetry": project_root / "config" / "telemetry.yaml",
            "yolo": project_root / "yolo_app" / "config.yaml",
        }
    )
    yolo_manager = yolo_process

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    def get_state() -> dict[str, Any]:
        return provider.snapshot(history.list(limit=20))

    @app.post("/api/command")
    def post_command(request: CommandRequest) -> dict[str, Any]:
        return dispatcher.dispatch(request.command).to_dict()

    @app.get("/api/commands/history")
    def get_history(limit: int = 100) -> dict[str, Any]:
        return {"items": history.list(limit=limit)}

    @app.get("/api/missions")
    def get_missions() -> dict[str, Any]:
        names = available_mission_names()
        return {
            "ok": True,
            "active": provider.snapshot().get("mission", {}).get("name"),
            "items": [
                {
                    "name": name,
                    "config_path": str(project_root / "missions" / name / "config.yaml"),
                    "stage_options": _mission_stage_options(name),
                }
                for name in names
            ],
        }

    @app.get("/api/config/mission")
    def get_mission_config(mission: str | None = None) -> dict[str, Any]:
        result = _read_mission_config(project_root, mission) if mission else store.read()
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result)
        return result

    @app.patch("/api/config/mission")
    def patch_mission_config(request: MissionConfigPatch, mission: str | None = None) -> dict[str, Any]:
        result = _patch_mission_config(project_root, mission, request.yaml) if mission else store.patch(request.yaml)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @app.post("/api/config/reload")
    def reload_config() -> dict[str, Any]:
        result = store.reload()
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @app.get("/api/config/system")
    def get_system_config(name: str | None = None) -> dict[str, Any]:
        if name is None:
            return system_store.list()
        result = system_store.read(name)
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result)
        return result

    @app.patch("/api/config/system")
    def patch_system_config(request: MissionConfigPatch, name: str) -> dict[str, Any]:
        result = system_store.patch(name, request.yaml)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @app.get("/api/yolo/status")
    def yolo_status() -> dict[str, Any]:
        if yolo_manager is None:
            return {"ok": False, "running": False, "message": "YOLO process manager is unavailable"}
        return yolo_manager.status()

    @app.post("/api/yolo/start")
    def yolo_start() -> dict[str, Any]:
        if yolo_manager is None:
            raise HTTPException(status_code=400, detail={"ok": False, "message": "YOLO process manager is unavailable"})
        return yolo_manager.start()

    @app.post("/api/yolo/stop")
    def yolo_stop() -> dict[str, Any]:
        if yolo_manager is None:
            raise HTTPException(status_code=400, detail={"ok": False, "message": "YOLO process manager is unavailable"})
        return yolo_manager.stop()

    @app.websocket("/ws/state")
    async def websocket_state(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(provider.snapshot(history.list(limit=20)))
                await asyncio.sleep(0.2)
        except WebSocketDisconnect:
            return

    @app.get("/video/yolo.mjpeg")
    def yolo_video() -> StreamingResponse:
        return StreamingResponse(
            proxy_mjpeg_stream(yolo_mjpeg_url),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    return app


def _mission_config_path(project_root: Path, mission: str | None) -> Path | None:
    if not mission:
        return None
    normalized = mission.strip().lower()
    if normalized not in available_mission_names():
        return None
    return project_root / "missions" / normalized / "config.yaml"


def _read_mission_config(project_root: Path, mission: str | None) -> dict[str, Any]:
    path = _mission_config_path(project_root, mission)
    if path is None:
        return {"ok": False, "message": f"unknown mission: {mission}", "path": None}
    return ConfigFileStore({"mission": path}).read("mission")


def _patch_mission_config(project_root: Path, mission: str | None, yaml_text: str) -> dict[str, Any]:
    path = _mission_config_path(project_root, mission)
    if path is None:
        return {"ok": False, "message": f"unknown mission: {mission}", "path": None}
    return ConfigFileStore({"mission": path}).patch("mission", yaml_text)


def _mission_stage_options(mission_name: str) -> list[dict[str, str]]:
    normalized = mission_name.strip().lower()
    if normalized == "visual_tracking":
        return [
            {"value": "APPROACH_TRACK", "label": "Approach Track"},
            {"value": "OVERHEAD_HOLD", "label": "Overhead Hold"},
            {"value": "CORRIDOR_FOLLOW", "label": "Corridor Follow"},
            {"value": "IDLE", "label": "Idle"},
        ]
    if normalized == "rescue_competition":
        return [
            {"value": stage.value, "label": stage.value.replace("_", " ").title()}
            for stage in RescueStage
        ]
    return []


class WebUIServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        command_handler: Callable[[str], Any] | None,
        state_provider: WebStateProvider,
        config_store: MissionConfigStore,
        yolo_process: YoloProcessManager | None = None,
        yolo_mjpeg_url: str,
    ) -> None:
        self.host = host
        self.port = port
        self.app = create_app(
            command_handler=command_handler,
            state_provider=state_provider,
            config_store=config_store,
            yolo_process=yolo_process,
            yolo_mjpeg_url=yolo_mjpeg_url,
        )
        self.yolo_process = yolo_process
        self._server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                host=host,
                port=port,
                log_level="info",
                access_log=False,
            )
        )
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._server.run, name="WebUIGroundStation", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self.yolo_process is not None:
            self.yolo_process.stop()
        self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
