from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from pathlib import Path

import yaml

from app.app_config import AppConfig, load_mission_stage_runtime_config
from app.blackbox_recorder import BlackboxRecorder
from app.debug_runtime import DebugRuntime
from app.health_monitor import HealthMonitor, HealthMonitorConfig
from app.mission_manager import MissionMode
from app.mission_runner import MissionRunner
from app.stage_registry import StageRegistry, copy_dataclass_values
from app.service_manager import ServiceManager
from missions.common.control import (
    CommandShaper,
    FlightCommand,
    FlightCommandExecutor,
    StageInputAdapter,
)
from missions.base import MissionContext
from missions.registry import available_mission_names, build_mission, build_mission_from_settings
from uav_ui.control_switches import ControlRuntimeSwitches
from uav_ui.terminal_ui import run_terminal_ui
from uav_ui.ui_commands import CommandResult, build_ui_command_handler, format_controller_snapshot
from uav_ui.yolo_command_client import YoloCommandClient
from web_ui.config_store import MissionConfigStore
from web_ui.processes import YoloProcessManager
from web_ui.state import WebStateProvider


class SystemRunner:
    def __init__(self, config: AppConfig, stop_event: threading.Event | None = None) -> None:
        self.config = config
        self.stop_event = stop_event or threading.Event()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.services = ServiceManager(config, self.stop_event)
        self.input_adapter = StageInputAdapter(config=config.input_adapter)
        self.health_monitor = HealthMonitor(
            HealthMonitorConfig(
                max_vision_age_s=config.control.mode.max_vision_age_s,
                max_drone_age_s=config.control.mode.max_drone_age_s,
                max_gimbal_age_s=config.control.mode.max_gimbal_age_s,
            )
        )
        self.mission_runner = MissionRunner(
            build_mission(config.mission_name, config),
            link_manager=self.services.link_manager,
            yolo_client=YoloCommandClient(config.yolo_command),
        )
        self.stage_registry = StageRegistry(
            approach_config=config.approach_track,
            overhead_config=config.overhead_hold,
        )
        self.command_shaper = CommandShaper(config=config.shaper)
        self.executor = FlightCommandExecutor(config=config.executor)
        self.blackbox = BlackboxRecorder(config.blackbox)
        self.debug_runtime = DebugRuntime(config.debug)
        self.controller_switches = ControlRuntimeSwitches(
            gimbal=config.start_gimbal,
            body=config.start_body,
            approach=config.start_approach,
            send_commands=config.start_send_commands,
        )
        self.control_command_log: deque[str] = deque(maxlen=120)
        self.control_command_log_lock = threading.Lock()
        self.runtime_config_lock = threading.RLock()
        self.latest_mission_name = config.mission_name
        self.latest_mission_stage = "UNKNOWN"
        self.latest_stage_controller = "UNKNOWN"
        self.latest_hold_reason = ""
        self.last_send_commands: bool | None = None
        self.target_lost_since: float | None = None
        self.lost_target_recenter_sent = False
        self.web_ui_server = None

    def run(self) -> None:
        self.services.start()
        self.mission_runner.link_manager = self.services.link_manager
        self.blackbox.start()
        self.executor.set_telemetry_link(self.services.link_manager)
        try:
            if self.config.runtime.web_ui_enabled:
                self._run_with_web_ui()
            elif self.config.runtime.ui_enabled and self.services.link_manager is not None:
                self._run_with_ui()
            else:
                if self.config.runtime.ui_enabled and self.services.link_manager is None:
                    self.logger.warning("UI disabled because telemetry is not connected")
                self._control_loop()
        finally:
            self.stop()

    def stop(self) -> None:
        self.stop_event.set()
        self.executor.reset()
        self.blackbox.close()
        if self.web_ui_server is not None:
            self.web_ui_server.stop()
            self.web_ui_server = None
        self.services.stop()
        self.logger.info("app runtime stopped")

    def _build_runtime_command_handler(self):
        if self.services.link_manager is None:
            return None
        return build_ui_command_handler(
            self.services.link_manager,
            controller_switches=self.controller_switches,
            yolo_client=YoloCommandClient(self.config.yolo_command),
            mission_command_handler=self._handle_mission_command,
            stage_override_handler=self._set_stage_override,
            stage_config_reload_handler=self._reload_mission_stage_config,
        )

    def _run_with_ui(self) -> None:
        assert self.services.link_manager is not None
        ui_command_handler = self._build_runtime_command_handler()
        assert ui_command_handler is not None
        control_thread = threading.Thread(
            name="AppControlLoop",
            target=self._control_loop,
            daemon=True,
        )
        control_thread.start()
        try:
            run_terminal_ui(
                self.services.link_manager,
                self.stop_event,
                self._get_mission_control_lines,
                ui_command_handler,
            )
        finally:
            self.stop_event.set()
            control_thread.join(timeout=1.0)

    def _run_with_web_ui(self) -> None:
        from web_ui.server import WebUIServer

        self.web_ui_server = WebUIServer(
            host=self.config.runtime.web_host,
            port=self.config.runtime.web_port,
            command_handler=self._build_runtime_command_handler(),
            state_provider=WebStateProvider(
                self,
                yolo_mjpeg_url=self.config.runtime.yolo_mjpeg_url,
            ),
            config_store=MissionConfigStore(
                lambda: self.config.mission_config_path,
                self._reload_mission_stage_config,
            ),
            yolo_process=YoloProcessManager(
                project_root=Path(__file__).resolve().parent.parent,
            ),
            yolo_mjpeg_url=self.config.runtime.yolo_mjpeg_url,
        )
        self.web_ui_server.start()
        self.logger.info(
            "Web UI listening at http://%s:%s",
            self.config.runtime.web_host,
            self.config.runtime.web_port,
        )
        self._control_loop()

    def _control_loop(self) -> None:
        loop_sleep_sec = 1.0 / max(self.config.runtime.loop_hz, 0.1)
        print_sleep_sec = 1.0 / max(self.config.runtime.print_rate_hz, 0.1)
        started_at = time.time()
        last_print_time = 0.0

        try:
            while not self.stop_event.is_set():
                now = time.time()
                run_seconds = self.config.runtime.run_seconds
                if run_seconds is not None and (now - started_at) >= run_seconds:
                    self.stop_event.set()
                    break

                perception = self.services.get_perception(now)
                scene = self.services.get_scene_detections(now)
                drone = self.services.get_drone_state()
                gimbal = self.services.get_gimbal_state()
                link = self.services.get_link_status()
                fused = self.services.fusion_manager.update(perception, drone, gimbal)
                controller_enabled = self.controller_switches.snapshot()
                with self.runtime_config_lock:
                    inputs = self.input_adapter.adapt(fused)
                    health = self.health_monitor.update(inputs)
                    context = MissionContext(
                        timestamp=now,
                        inputs=inputs,
                        health=health,
                        perception=perception,
                        drone=drone,
                        gimbal=gimbal,
                        link=link,
                        scene=scene,
                        actions_enabled=bool(controller_enabled.send_commands),
                    )
                    self.mission_runner.send_actions = bool(controller_enabled.send_commands)
                    mission = self.mission_runner.update(context)
                    mission = self.debug_runtime.apply_mission_override(mission)
                    raw_command, mode_status = self._update_active_mode(mission.active_mode, inputs)
                    raw_command = self.debug_runtime.apply_command_override(raw_command)
                    raw_command = self._apply_controller_switches(raw_command)
                    raw_for_log = FlightCommand(
                        vx_cmd=raw_command.vx_cmd,
                        vy_cmd=raw_command.vy_cmd,
                        vz_cmd=raw_command.vz_cmd,
                        yaw_rate_cmd=raw_command.yaw_rate_cmd,
                        gimbal_yaw_rate_cmd=raw_command.gimbal_yaw_rate_cmd,
                        gimbal_pitch_rate_cmd=raw_command.gimbal_pitch_rate_cmd,
                        enable_body=raw_command.enable_body,
                        enable_gimbal=raw_command.enable_gimbal,
                        enable_approach=raw_command.enable_approach,
                        active=raw_command.active,
                        valid=raw_command.valid,
                    )
                    shaped = self.command_shaper.update(raw_command, inputs.dt)

                self.executor.config.send_commands = bool(controller_enabled.send_commands)
                if controller_enabled.send_commands:
                    self.executor.execute(shaped)
                    self._record_control_command(now, shaped, send_commands=True)
                    self._maybe_recenter_gimbal_after_target_loss(now, bool(inputs.target_valid), True)
                else:
                    if self.last_send_commands is not False:
                        with self.control_command_log_lock:
                            self.control_command_log.clear()
                            self.control_command_log.appendleft(
                                f"{time.strftime('%H:%M:%S', time.localtime(now))} "
                                "DRY continuous command sending disabled"
                            )
                    self._maybe_recenter_gimbal_after_target_loss(now, bool(inputs.target_valid), False)
                self.last_send_commands = bool(controller_enabled.send_commands)

                self.blackbox.record(
                    now=now,
                    dt=inputs.dt,
                    perception=perception,
                    drone=drone,
                    gimbal=gimbal,
                    link=link,
                    fused=fused,
                    inputs=inputs,
                    mission=mission,
                    health=health,
                    mode_status=mode_status,
                    raw_command=raw_for_log,
                    shaped_command=shaped,
                    send_commands=bool(controller_enabled.send_commands),
                )

                with self.control_command_log_lock:
                    self.latest_mission_name = self.mission_runner.mission.name
                    self.latest_mission_stage = mission.stage or "UNKNOWN"
                    self.latest_stage_controller = mission.active_mode
                    self.latest_hold_reason = mode_status.hold_reason or mission.hold_reason

                if (now - last_print_time) >= print_sleep_sec:
                    self.logger.info(
                        "mode=%s mission=%s health=%s hold=%s enabled=(gimbal:%s body:%s approach:%s send:%s) "
                        "control_allowed=%s target_valid=%s track_id=%s target_size=%.3f "
                        "raw=(vx=%.3f vy=%.3f vz=%.3f yaw=%.3f gimbal=%.3f,%.3f) "
                        "shaped=(vx=%.3f vy=%.3f vz=%.3f yaw=%.3f gimbal=%.3f,%.3f)",
                        mode_status.mode_name,
                        mission.active_mode,
                        health.hold_reason,
                        mode_status.hold_reason or mission.hold_reason,
                        shaped.enable_gimbal,
                        shaped.enable_body,
                        shaped.enable_approach,
                        controller_enabled.send_commands,
                        inputs.control_allowed,
                        inputs.target_valid,
                        inputs.track_id,
                        inputs.target_size,
                        raw_for_log.vx_cmd,
                        raw_for_log.vy_cmd,
                        raw_for_log.vz_cmd,
                        raw_for_log.yaw_rate_cmd,
                        raw_for_log.gimbal_yaw_rate_cmd,
                        raw_for_log.gimbal_pitch_rate_cmd,
                        shaped.vx_cmd,
                        shaped.vy_cmd,
                        shaped.vz_cmd,
                        shaped.yaw_rate_cmd,
                        shaped.gimbal_yaw_rate_cmd,
                        shaped.gimbal_pitch_rate_cmd,
                    )
                    last_print_time = now

                time.sleep(loop_sleep_sec)
        except Exception:
            self.logger.exception("app control loop failed")
            self.stop_event.set()

    def _update_active_mode(self, mode_name: str, inputs) -> tuple[FlightCommand, object]:
        if mode_name == MissionMode.IDLE.value:
            return FlightCommand(valid=True), _Status("IDLE", False, True, "idle")
        try:
            mode = self.stage_registry.get(mode_name)
        except KeyError:
            self.logger.warning("unknown mission stage controller %s; commanding zero", mode_name)
            return FlightCommand(valid=True), _Status(mode_name, False, False, "unknown_mode")
        return mode.update(inputs)

    def _apply_controller_switches(self, command: FlightCommand) -> FlightCommand:
        snapshot = self.controller_switches.snapshot()
        if not snapshot.gimbal:
            command.enable_gimbal = False
            command.gimbal_yaw_rate_cmd = 0.0
            command.gimbal_pitch_rate_cmd = 0.0
        if not snapshot.body:
            command.enable_body = False
            command.vy_cmd = 0.0
            command.vz_cmd = 0.0
            command.yaw_rate_cmd = 0.0
        if not snapshot.approach:
            command.enable_approach = False
            command.vx_cmd = 0.0
        command.active = bool(command.enable_gimbal or command.enable_body or command.enable_approach)
        return command

    def _format_control_command(self, now: float, shaped: FlightCommand, send_commands: bool) -> str:
        return (
            f"{time.strftime('%H:%M:%S', time.localtime(now))} "
            f"{'TX' if send_commands else 'DRY'} "
            f"vx={shaped.vx_cmd:.3f} vy={shaped.vy_cmd:.3f} vz={shaped.vz_cmd:.3f} "
            f"yaw={shaped.yaw_rate_cmd:.3f} "
            f"gimbal=({shaped.gimbal_yaw_rate_cmd:.3f},{shaped.gimbal_pitch_rate_cmd:.3f}) "
            f"en=G{int(shaped.enable_gimbal)} B{int(shaped.enable_body)} A{int(shaped.enable_approach)} "
            f"active={shaped.active} valid={shaped.valid}"
        )

    def _record_control_command(self, now: float, shaped: FlightCommand, send_commands: bool) -> None:
        line = self._format_control_command(now, shaped, send_commands)
        with self.control_command_log_lock:
            self.control_command_log.appendleft(line)

    def _get_mission_control_lines(self) -> list[str]:
        with self.control_command_log_lock:
            return [
                f"Controllers {format_controller_snapshot(self.controller_switches.snapshot())}",
                f"Mission {self.latest_mission_name} stage={self.latest_mission_stage}",
                f"Stage controller {self.latest_stage_controller}",
                f"Hold {self.latest_hold_reason or 'none'}",
                *self.mission_runner.get_action_log_lines(),
                *list(self.control_command_log),
            ]

    def _set_stage_override(self, mode_name: str | None) -> CommandResult:
        with self.runtime_config_lock:
            if mode_name is None:
                self.debug_runtime.config.force_mode = None
                self.stage_registry.reset_all()
                return CommandResult(True, "stage override auto")
            normalized = mode_name.strip().upper()
            if normalized == MissionMode.IDLE.value:
                self.debug_runtime.config.force_mode = normalized
                return CommandResult(True, "stage override forced IDLE")
            try:
                self.stage_registry.get(normalized)
            except KeyError:
                return CommandResult(
                    False,
                    "stage override must be APPROACH_TRACK, OVERHEAD_HOLD, CORRIDOR_FOLLOW, IDLE, or auto",
                )
            self.debug_runtime.config.force_mode = normalized
            return CommandResult(True, f"stage override forced {normalized}")

    def _handle_mission_command(self, parts: list[str]) -> CommandResult:
        if not parts:
            return CommandResult(
                False,
                "format: mission list | mission switch <name> | mission start | mission reset | mission current",
            )
        action = parts[0].lower()
        if action in {"list", "ls"}:
            names = ", ".join(available_mission_names())
            return CommandResult(
                True,
                f"missions: {names}; active={self.mission_runner.mission.name}",
            )
        if action in {"current", "status"}:
            return CommandResult(True, f"active mission={self.mission_runner.mission.name}")
        if action == "stage":
            if len(parts) != 2:
                return CommandResult(False, "format: mission stage <stage_name>")
            setter = getattr(self.mission_runner.mission, "set_stage", None)
            if not callable(setter):
                return CommandResult(False, f"mission stage unsupported: {self.mission_runner.mission.name}")
            try:
                with self.runtime_config_lock:
                    setter(parts[1])
                    self.stage_registry.reset_all()
                    with self.control_command_log_lock:
                        self.latest_mission_stage = parts[1].strip().upper()
                return CommandResult(True, f"mission stage set: {parts[1].strip().upper()}")
            except Exception as exc:
                return CommandResult(False, f"mission stage failed: {exc}")
        if action == "start":
            starter = getattr(self.mission_runner.mission, "start", None)
            if not callable(starter):
                return CommandResult(
                    False,
                    f"mission start unsupported: {self.mission_runner.mission.name}",
                )
            with self.runtime_config_lock:
                starter()
                return CommandResult(True, f"mission start requested: {self.mission_runner.mission.name}")
        if action == "reset":
            with self.runtime_config_lock:
                self._reset_mission_runtime(clear_for_safety=True)
                return CommandResult(True, f"mission reset: {self.mission_runner.mission.name}; SEND=OFF")
        if action in {"switch", "select", "use"}:
            if len(parts) != 2:
                return CommandResult(False, "format: mission switch <name>")
            return self._switch_mission(parts[1])
        return CommandResult(
            False,
            "format: mission list | mission switch <name> | mission start | mission reset | mission current",
        )

    def _switch_mission(self, mission_name: str) -> CommandResult:
        normalized = mission_name.strip().lower()
        if normalized not in available_mission_names():
            return CommandResult(
                False,
                f"unknown mission: {mission_name}; available={', '.join(available_mission_names())}",
            )
        try:
            settings = self._load_mission_settings(normalized)
            mission = build_mission_from_settings(
                normalized,
                settings,
                visual_config=self.config.mission,
            )
        except Exception as exc:
            self.logger.exception("failed to switch mission")
            return CommandResult(False, f"mission switch failed: {exc}")

        with self.runtime_config_lock:
            previous = self.mission_runner.mission.name
            self.mission_runner.mission = mission
            self.config.mission_name = normalized
            self.config.mission_settings = dict(settings)
            config_path = self._mission_config_path(normalized)
            self.config.mission_config_path = str(config_path)
            self.debug_runtime.config.force_mode = None
            self._reset_mission_runtime(clear_for_safety=True)
            return CommandResult(
                True,
                f"mission switched {previous} -> {mission.name}; stage auto; SEND=OFF",
            )

    def _reset_mission_runtime(self, *, clear_for_safety: bool) -> None:
        self.mission_runner.reset()
        self.stage_registry.reset_all()
        self.command_shaper.reset()
        self.target_lost_since = None
        self.lost_target_recenter_sent = False
        with self.control_command_log_lock:
            self.latest_mission_name = self.mission_runner.mission.name
            self.latest_mission_stage = "UNKNOWN"
            self.latest_stage_controller = "UNKNOWN"
            self.latest_hold_reason = ""
            self.control_command_log.clear()
        if clear_for_safety:
            self.controller_switches.set_send_commands(False)
            if self.services.link_manager is not None:
                clear_sender = getattr(self.services.link_manager, "clear_continuous_commands", None)
                if callable(clear_sender):
                    clear_sender()

    def _load_mission_settings(self, mission_name: str) -> dict[str, object]:
        config_path = self._mission_config_path(mission_name)
        if not config_path.exists():
            if mission_name == self.config.mission_name:
                return dict(self.config.mission_settings)
            return {"name": mission_name}
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"mission config must be a mapping: {config_path}")
        return dict(data)

    def _mission_config_path(self, mission_name: str) -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "missions"
            / mission_name
            / "config.yaml"
        )

    def _reload_mission_stage_config(self) -> CommandResult:
        path = self.config.mission_config_path
        if not path:
            return CommandResult(False, "mission config reload is unavailable for legacy config")
        try:
            input_adapter_cfg, approach_cfg, overhead_cfg, shaper_cfg = load_mission_stage_runtime_config(
                self.config.mission_config_path,
            )
        except Exception as exc:
            self.logger.exception("failed to reload mission config")
            return CommandResult(False, f"mission config reload failed: {exc}")

        with self.runtime_config_lock:
            copy_dataclass_values(self.config.input_adapter, input_adapter_cfg)
            copy_dataclass_values(self.config.approach_track, approach_cfg)
            copy_dataclass_values(self.config.overhead_hold, overhead_cfg)
            copy_dataclass_values(self.config.shaper, shaper_cfg)
            self.stage_registry.apply_configs(
                approach_config=approach_cfg,
                overhead_config=overhead_cfg,
                reset=True,
            )
            self.input_adapter.config = self.config.input_adapter
            self.command_shaper.config = self.config.shaper
            self.command_shaper.reset()

        self.logger.info("reloaded mission config from %s", path)
        return CommandResult(True, f"mission config reloaded: {path}")

    def _maybe_recenter_gimbal_after_target_loss(
        self,
        now: float,
        target_valid: bool,
        send_commands: bool,
    ) -> None:
        if target_valid:
            self.target_lost_since = None
            self.lost_target_recenter_sent = False
            return
        if self.target_lost_since is None:
            self.target_lost_since = now
            return
        if self.lost_target_recenter_sent or not send_commands:
            return
        if self.services.link_manager is None:
            return
        if not self.config.runtime.lost_target_recenter_enabled:
            return
        if (now - self.target_lost_since) < self.config.runtime.lost_target_recenter_timeout_sec:
            return
        clear_sender = getattr(self.services.link_manager, "clear_continuous_commands", None)
        if callable(clear_sender):
            clear_sender()
        self.services.link_manager.send_gimbal_angle(
            pitch=self.config.runtime.lost_target_recenter_pitch_deg,
            yaw=self.config.runtime.lost_target_recenter_yaw_deg,
            roll=self.config.executor.gimbal_roll_deg,
        )
        self.lost_target_recenter_sent = True
        with self.control_command_log_lock:
            self.control_command_log.appendleft(
                f"{time.strftime('%H:%M:%S', time.localtime(now))} "
                "TX lost target recenter gimbal "
                f"pitch={self.config.runtime.lost_target_recenter_pitch_deg:.1f} "
                f"yaw={self.config.runtime.lost_target_recenter_yaw_deg:.1f}"
            )


class _Status:
    def __init__(self, mode_name: str, active: bool, valid: bool, hold_reason: str) -> None:
        self.mode_name = mode_name
        self.active = active
        self.valid = valid
        self.hold_reason = hold_reason
        self.detail = {}
