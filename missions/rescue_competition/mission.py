from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from missions.base import MissionAction, MissionContext, MissionOutput
from missions.common.navigation import (
    LocalMissionFrame,
    goal_target_tuple,
    hold_elapsed,
    local_goal_stable,
    mission_to_local_position,
    to_mission_position,
)
from missions.common.recce import RecceAccumulator, RecceConfig, RecceResultItem
from missions.common.recce_output import write_recce_results


class RescueStage(str, Enum):
    PREPARE = "PREPARE"
    TAKEOFF = "TAKEOFF"
    FOLLOW_ROUTE_TO_DROP_ZONE = "FOLLOW_ROUTE_TO_DROP_ZONE"
    SEARCH_DROP_TARGETS = "SEARCH_DROP_TARGETS"
    ALIGN_AND_DROP = "ALIGN_AND_DROP"
    WAIT_PAYLOAD_RELEASE = "WAIT_PAYLOAD_RELEASE"
    RESUME_ROUTE_TO_RECCE_ZONE = "RESUME_ROUTE_TO_RECCE_ZONE"
    SCAN_RECCE_AREA = "SCAN_RECCE_AREA"
    FOLLOW_ROUTE_HOME = "FOLLOW_ROUTE_HOME"
    LAND = "LAND"
    DONE = "DONE"
    ABORT = "ABORT"


@dataclass(slots=True)
class RoutePoint:
    name: str
    x: float
    y: float
    z: float
    xy_tolerance_m: float = 1.0
    z_tolerance_m: float = 0.5
    max_speed_mps: float = 0.5


@dataclass(slots=True)
class MissionZone:
    name: str
    x: float
    y: float
    radius_m: float
    z: float | None = None


@dataclass(slots=True)
class PayloadRelease:
    type: str
    channel: int | None = None
    pwm: int | None = None
    relay_id: int | None = None
    state: bool | None = None


@dataclass(slots=True)
class PayloadSlot:
    payload_id: int
    label: str = ""
    release: PayloadRelease | None = None


@dataclass(slots=True)
class DropAlignConfig:
    max_ex_cam: float = 0.08
    max_ey_cam: float = 0.08
    min_target_size: float = 0.0
    require_target_locked: bool = True
    require_target_stable: bool = True
    hold_s: float = 0.8
    timeout_s: float = 15.0
    lost_timeout_s: float = 2.0


@dataclass(slots=True)
class PayloadReleaseTiming:
    delay_after_action_s: float = 1.0


@dataclass(slots=True)
class RecceMissionConfig:
    config: RecceConfig = field(default_factory=RecceConfig)
    scan_duration_s: float = 8.0
    output_dir: str = "logs/recce"
    output_json: bool = True
    output_csv: bool = True


@dataclass(slots=True)
class DropTargetSelection:
    track_id: int | None
    class_name: str
    confidence: float
    ex: float
    ey: float
    target_size: float
    selected_at: float

    def to_detail(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "ex": self.ex,
            "ey": self.ey,
            "target_size": self.target_size,
            "selected_at": self.selected_at,
        }


@dataclass(slots=True)
class RescueCompetitionMissionConfig:
    initial_stage: RescueStage = RescueStage.PREPARE
    idle_mode: str = "IDLE"
    auto_start: bool = False
    takeoff_altitude_m: float = 5.0
    takeoff_altitude_tolerance_m: float = 0.5
    local_position_frame: int = 1
    drop_route_end_name: str = "drop_center"
    recce_route_end_name: str = "recce_center"
    home_route_end_name: str = "home"
    route_hold_s: float = 0.0
    align_mode: str = "OVERHEAD_HOLD"
    dry_run_skip_vision: bool = False
    dry_run_skip_payload_release: bool = False
    search_drop_duration_s: float = 2.0
    align_drop_duration_s: float = 1.0
    drop_target_classes: list[str] = field(
        default_factory=lambda: ["drop_cylinder", "cylinder", "target"]
    )
    drop_target_min_confidence: float = 0.45
    drop_target_stable_frames: int = 5
    drop_target_max_center_error: float = 0.35
    align: DropAlignConfig = field(default_factory=DropAlignConfig)
    payload_release: PayloadReleaseTiming = field(default_factory=PayloadReleaseTiming)
    recce: RecceMissionConfig = field(default_factory=RecceMissionConfig)
    scan_duration_s: float = 3.0
    land_complete_altitude_m: float = 0.3
    route: list[RoutePoint] = field(default_factory=list)
    drop_zones: list[MissionZone] = field(default_factory=list)
    recce_zones: list[MissionZone] = field(default_factory=list)
    payloads: list[PayloadSlot] = field(default_factory=list)


@dataclass(slots=True)
class RescueCompetitionMission:
    config: RescueCompetitionMissionConfig = field(
        default_factory=RescueCompetitionMissionConfig
    )

    name: str = "rescue_competition"
    _stage: RescueStage = field(init=False)
    _origin: LocalMissionFrame | None = field(init=False, default=None)
    _route_index: int = field(init=False, default=0)
    _payload_index: int = field(init=False, default=0)
    _stage_started_at: float | None = field(init=False, default=None)
    _goal_reached_since: float | None = field(init=False, default=None)
    _drop_candidate_track_id: int | None = field(init=False, default=None)
    _drop_candidate_seen_frames: int = field(init=False, default=0)
    _drop_candidate_last_center: tuple[float, float] | None = field(init=False, default=None)
    _drop_candidate_class_name: str = field(init=False, default="")
    _selected_drop_target: DropTargetSelection | None = field(init=False, default=None)
    _align_ready_since: float | None = field(init=False, default=None)
    _target_lost_since: float | None = field(init=False, default=None)
    _payload_release_started_at: float | None = field(init=False, default=None)
    _recce_accumulator: RecceAccumulator = field(init=False)
    _recce_output_written: bool = field(init=False, default=False)
    _recce_results: list[RecceResultItem] = field(init=False, default_factory=list)
    _recce_output_paths: list[str] = field(init=False, default_factory=list)
    _start_requested: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self._stage = self._stage_value(self.config.initial_stage)
        self._recce_accumulator = RecceAccumulator(self.config.recce.config)

    def reset(self) -> None:
        self._stage = self._stage_value(self.config.initial_stage)
        self._origin = None
        self._route_index = 0
        self._payload_index = 0
        self._stage_started_at = None
        self._goal_reached_since = None
        self._reset_drop_candidate()
        self._selected_drop_target = None
        self._align_ready_since = None
        self._target_lost_since = None
        self._payload_release_started_at = None
        self._recce_accumulator.reset()
        self._recce_output_written = False
        self._recce_results = []
        self._recce_output_paths = []
        self._start_requested = False

    def start(self) -> None:
        self._start_requested = True

    def update(self, context: MissionContext) -> MissionOutput:
        previous = self._stage
        self._ensure_stage_started(context)
        actions: list[MissionAction] = []
        hold_reason = ""
        active_mode = self.config.idle_mode

        if self._stage == RescueStage.PREPARE:
            hold_reason = self._update_prepare(context)
        elif self._stage == RescueStage.TAKEOFF:
            actions.append(
                MissionAction(
                    "takeoff",
                    params={"altitude_m": self.config.takeoff_altitude_m},
                    key="rescue_takeoff",
                    once=True,
                    priority=2,
                )
            )
            if context.drone.relative_alt_valid and context.drone.relative_altitude >= (
                self.config.takeoff_altitude_m - self.config.takeoff_altitude_tolerance_m
            ):
                self._stage = RescueStage.FOLLOW_ROUTE_TO_DROP_ZONE
        elif self._stage == RescueStage.FOLLOW_ROUTE_TO_DROP_ZONE:
            hold_reason = self._update_route_follow(context, actions)
        elif self._stage == RescueStage.SEARCH_DROP_TARGETS:
            hold_reason = "searching_drop_targets"
            candidate = None
            if not self.config.dry_run_skip_vision:
                candidate = self._update_drop_candidate(context)
            if candidate is not None:
                self._select_drop_target(candidate, context, actions)
                self._transition_to(RescueStage.ALIGN_AND_DROP)
                active_mode = self.config.align_mode
                hold_reason = "drop_target_acquired"
            elif self.config.dry_run_skip_vision and hold_elapsed(
                context.timestamp,
                self._stage_started_at,
                self.config.search_drop_duration_s,
            ):
                self._transition_to(RescueStage.ALIGN_AND_DROP)
                active_mode = self.config.align_mode
                hold_reason = "dry_run_drop_target_skip"
        elif self._stage == RescueStage.ALIGN_AND_DROP:
            active_mode = self.config.align_mode
            hold_reason = self._update_align_and_drop(context, actions)
        elif self._stage == RescueStage.WAIT_PAYLOAD_RELEASE:
            active_mode = self.config.align_mode
            hold_reason = self._update_wait_payload_release(context, actions)
        elif self._stage == RescueStage.RESUME_ROUTE_TO_RECCE_ZONE:
            hold_reason = self._follow_route_until(
                context,
                actions,
                self.config.recce_route_end_name,
                RescueStage.SCAN_RECCE_AREA,
                "enroute",
            )
        elif self._stage == RescueStage.SCAN_RECCE_AREA:
            hold_reason = self._update_scan_recce_area(context)
        elif self._stage == RescueStage.FOLLOW_ROUTE_HOME:
            hold_reason = self._follow_route_until(
                context,
                actions,
                self.config.home_route_end_name,
                RescueStage.LAND,
                "returning_home",
            )
        elif self._stage == RescueStage.LAND:
            actions.append(
                MissionAction(
                    "land",
                    key="rescue_land",
                    once=True,
                    priority=2,
                )
            )
            if context.drone.relative_alt_valid and context.drone.relative_altitude <= self.config.land_complete_altitude_m:
                self._transition_to(RescueStage.DONE)

        return MissionOutput(
            active_mode=active_mode,
            actions=actions,
            stage=self._stage.value,
            previous_stage=previous.value if previous != self._stage else None,
            hold_reason=hold_reason,
            done=self._stage == RescueStage.DONE,
            aborted=self._stage == RescueStage.ABORT,
            detail={
                "mission": self.name,
                "timestamp": float(context.timestamp),
                "origin_captured": self._origin is not None,
                "route_index": self._route_index,
                "payload_index": self._payload_index,
                "route_points": len(self.config.route),
                "drop_zones": len(self.config.drop_zones),
                "recce_zones": len(self.config.recce_zones),
                "payloads": len(self.config.payloads),
                "selected_drop_target": (
                    None
                    if self._selected_drop_target is None
                    else self._selected_drop_target.to_detail()
                ),
                "recce_observation_count": self._recce_accumulator.observation_count,
                "recce_confirmed_count": self._recce_confirmed_count(),
                "recce_results": [item.to_dict() for item in self._recce_results],
                "recce_output_paths": list(self._recce_output_paths),
            },
        )

    @staticmethod
    def _stage_value(stage: RescueStage | str) -> RescueStage:
        if isinstance(stage, RescueStage):
            return stage
        return RescueStage(str(stage))

    def _update_prepare(self, context: MissionContext) -> str:
        if not context.drone.local_position_valid:
            return "local_position_not_ready"
        if self._origin is None:
            self._origin = LocalMissionFrame(
                origin_x=float(context.drone.local_x),
                origin_y=float(context.drone.local_y),
                origin_z=float(context.drone.local_z),
                yaw_rad=float(context.drone.yaw),
            )
        if self.config.auto_start or self._start_requested:
            self._transition_to(RescueStage.TAKEOFF)
            self._start_requested = False
        return ""

    def _update_route_follow(
        self,
        context: MissionContext,
        actions: list[MissionAction],
    ) -> str:
        return self._follow_route_until(
            context,
            actions,
            self.config.drop_route_end_name,
            RescueStage.SEARCH_DROP_TARGETS,
            "enroute",
        )

    def _follow_route_until(
        self,
        context: MissionContext,
        actions: list[MissionAction],
        end_name: str,
        next_stage: RescueStage,
        progress_reason: str,
    ) -> str:
        if not self.config.route:
            self._transition_to(next_stage)
            return "route_empty"
        end_index = self._route_index_for_name(end_name)
        if end_index is None:
            self._transition_to(RescueStage.ABORT)
            return "route_invalid"
        if self._origin is None:
            if not context.drone.local_position_valid:
                return "local_position_not_ready"
            self._origin = LocalMissionFrame(
                origin_x=float(context.drone.local_x),
                origin_y=float(context.drone.local_y),
                origin_z=float(context.drone.local_z),
                yaw_rad=float(context.drone.yaw),
            )
        if self._route_index > end_index:
            self._transition_to(next_stage)
            return f"route_end_reached:{end_name}"

        current_point = self.config.route[min(self._route_index, end_index)]
        current = to_mission_position(context.drone, self._origin)
        target = goal_target_tuple(current_point)
        local_target = mission_to_local_position(target, self._origin)
        actions.append(
            MissionAction(
                "local_position",
                params={
                    "x": local_target[0],
                    "y": local_target[1],
                    "z": local_target[2],
                    "frame": self.config.local_position_frame,
                },
                key=f"rescue_route_{self._route_index}_{current_point.name}",
                once=False,
                priority=4,
            )
        )
        if local_goal_stable(
            context.drone,
            current,
            target,
            current_point.xy_tolerance_m,
            current_point.z_tolerance_m,
            current_point.max_speed_mps,
        ):
            if self._goal_reached_since is None:
                self._goal_reached_since = float(context.timestamp)
            if not hold_elapsed(
                context.timestamp,
                self._goal_reached_since,
                self.config.route_hold_s,
            ):
                return f"arrived:{current_point.name}"
            arrived_name = current_point.name
            self._route_index += 1
            self._goal_reached_since = None
            if arrived_name == end_name or self._route_index > end_index:
                self._transition_to(next_stage)
                return f"route_end_reached:{end_name}"
            return f"arrived:{arrived_name}"

        self._goal_reached_since = None
        return f"{progress_reason}:{current_point.name}"

    def _update_align_and_drop(
        self,
        context: MissionContext,
        actions: list[MissionAction],
    ) -> str:
        if self.config.dry_run_skip_payload_release and not context.actions_enabled:
            if not hold_elapsed(
                context.timestamp,
                self._stage_started_at,
                self.config.align_drop_duration_s,
            ):
                return "aligning_drop_dry_run"
            self._payload_release_started_at = float(context.timestamp)
            self._transition_to(RescueStage.WAIT_PAYLOAD_RELEASE)
            return "payload_release_simulated"

        lost_reason = self._align_lost_reason(context)
        if lost_reason:
            self._align_ready_since = None
            if self._target_lost_since is None:
                self._target_lost_since = float(context.timestamp)
            if hold_elapsed(
                context.timestamp,
                self._target_lost_since,
                self.config.align.lost_timeout_s,
            ):
                self._return_to_drop_search(actions)
                return "drop_target_lost"
            return lost_reason
        self._target_lost_since = None

        if hold_elapsed(
            context.timestamp,
            self._stage_started_at,
            self.config.align.timeout_s,
        ):
            self._return_to_drop_search(actions)
            return "drop_align_timeout"

        if not self._drop_alignment_ready(context):
            self._align_ready_since = None
            return "aligning_drop"

        if self._align_ready_since is None:
            self._align_ready_since = float(context.timestamp)
        if not hold_elapsed(
            context.timestamp,
            self._align_ready_since,
            self.config.align.hold_s,
        ):
            return "aligning_drop"

        if self._payload_index >= len(self.config.payloads):
            return "no_payload_configured"

        payload = self.config.payloads[self._payload_index]
        action = self._release_action(payload)
        if action is None:
            return "payload_release_not_configured"
        if not context.actions_enabled:
            return "payload_release_actions_disabled"

        actions.append(action)
        self._payload_release_started_at = float(context.timestamp)
        self._transition_to(RescueStage.WAIT_PAYLOAD_RELEASE)
        return "payload_release_requested"

    def _update_wait_payload_release(
        self,
        context: MissionContext,
        actions: list[MissionAction],
    ) -> str:
        if self._payload_release_started_at is None:
            self._payload_release_started_at = float(context.timestamp)
        if not hold_elapsed(
            context.timestamp,
            self._payload_release_started_at,
            self.config.payload_release.delay_after_action_s,
        ):
            return "waiting_payload_release"

        if self._payload_index < len(self.config.payloads):
            self._payload_index += 1
        actions.append(
            MissionAction(
                "yolo_unlock_target",
                key="unlock_drop_target_after_release",
                once=True,
                priority=5,
            )
        )
        self._clear_drop_target_selection()
        self._transition_to(RescueStage.RESUME_ROUTE_TO_RECCE_ZONE)
        return "payload_release_complete"

    def _update_scan_recce_area(self, context: MissionContext) -> str:
        if context.scene is not None and context.scene.valid:
            self._recce_accumulator.update(context.scene, context.timestamp)
        elapsed = 0.0 if self._stage_started_at is None else float(context.timestamp) - self._stage_started_at
        if elapsed >= self.config.recce.scan_duration_s:
            self._finalize_recce_results(context.timestamp)
            self._transition_to(RescueStage.FOLLOW_ROUTE_HOME)
            return ""
        return "scanning_recce_area"

    def _finalize_recce_results(self, timestamp: float) -> None:
        self._recce_results = self._recce_accumulator.results()
        if self._recce_output_written:
            return
        paths = write_recce_results(
            output_dir=self.config.recce.output_dir,
            mission=self.name,
            timestamp=timestamp,
            items=self._recce_results,
            write_json=self.config.recce.output_json,
            write_csv=self.config.recce.output_csv,
        )
        self._recce_output_paths = [str(path) for path in paths]
        self._recce_output_written = True

    def _recce_confirmed_count(self) -> int:
        return sum(1 for item in self._recce_results if item.status == "confirmed")

    def _ensure_stage_started(self, context: MissionContext) -> None:
        if self._stage_started_at is None:
            self._stage_started_at = float(context.timestamp)

    def _transition_to(self, stage: RescueStage) -> None:
        if self._stage == stage:
            return
        self._stage = stage
        self._stage_started_at = None
        self._goal_reached_since = None
        self._align_ready_since = None
        self._target_lost_since = None

    def _route_index_for_name(self, name: str) -> int | None:
        for index, point in enumerate(self.config.route):
            if point.name == name:
                return index
        return None

    def _select_drop_target(
        self,
        candidate,
        context: MissionContext,
        actions: list[MissionAction],
    ) -> None:
        self._selected_drop_target = DropTargetSelection(
            track_id=candidate.track_id,
            class_name=str(candidate.class_name),
            confidence=float(candidate.confidence),
            ex=float(getattr(candidate, "ex", 0.0)),
            ey=float(getattr(candidate, "ey", 0.0)),
            target_size=float(getattr(candidate, "target_size", 0.0)),
            selected_at=float(context.timestamp),
        )
        if candidate.track_id is not None:
            actions.append(
                MissionAction(
                    "yolo_lock_target",
                    params={"track_id": int(candidate.track_id)},
                    key=f"lock_drop_target_{int(candidate.track_id)}",
                    once=True,
                    priority=5,
                )
            )

    def _clear_drop_target_selection(self) -> None:
        self._selected_drop_target = None
        self._reset_drop_candidate()
        self._payload_release_started_at = None

    def _return_to_drop_search(self, actions: list[MissionAction]) -> None:
        actions.append(
            MissionAction(
                "yolo_unlock_target",
                key="unlock_drop_target_for_search",
                once=True,
                priority=5,
            )
        )
        self._clear_drop_target_selection()
        self._transition_to(RescueStage.SEARCH_DROP_TARGETS)

    def _align_lost_reason(self, context: MissionContext) -> str:
        if not context.health.vision_fresh:
            return "drop_target_vision_stale"
        if not context.inputs.target_valid:
            return "drop_target_not_ready"
        return ""

    def _drop_alignment_ready(self, context: MissionContext) -> bool:
        inputs = context.inputs
        config = self.config.align
        if not context.health.vision_fresh or not inputs.target_valid:
            return False
        if config.require_target_locked and not inputs.target_locked:
            return False
        if config.require_target_stable and not inputs.target_stable:
            return False
        if abs(float(inputs.ex_cam)) > config.max_ex_cam:
            return False
        if abs(float(inputs.ey_cam)) > config.max_ey_cam:
            return False
        if float(inputs.target_size) < config.min_target_size:
            return False
        return True

    def _update_drop_candidate(self, context: MissionContext):
        candidate = self._select_drop_candidate(context.scene)
        if candidate is None:
            self._reset_drop_candidate()
            return None
        if self._same_drop_candidate(candidate):
            self._drop_candidate_seen_frames += 1
        else:
            self._drop_candidate_track_id = candidate.track_id
            self._drop_candidate_seen_frames = 1
            self._drop_candidate_class_name = str(candidate.class_name).lower()
        self._drop_candidate_last_center = (float(candidate.cx), float(candidate.cy))
        if self._drop_candidate_seen_frames >= max(1, int(self.config.drop_target_stable_frames)):
            self._selected_drop_target = {
                "track_id": candidate.track_id,
                "class_name": candidate.class_name,
                "confidence": candidate.confidence,
                "seen_frames": self._drop_candidate_seen_frames,
            }
            return candidate
        return None

    def _select_drop_candidate(self, scene):
        if scene is None or not getattr(scene, "valid", False):
            return None
        classes = {name.strip().lower() for name in self.config.drop_target_classes if name.strip()}
        candidates = []
        for detection in getattr(scene, "detections", []):
            class_name = str(getattr(detection, "class_name", "")).lower()
            if classes and class_name not in classes:
                continue
            if float(getattr(detection, "confidence", 0.0)) < self.config.drop_target_min_confidence:
                continue
            center_error = self._center_error(detection)
            if center_error > self.config.drop_target_max_center_error:
                continue
            candidates.append((center_error, detection))
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]

    def _same_drop_candidate(self, candidate) -> bool:
        if candidate.track_id is not None and self._drop_candidate_track_id is not None:
            return int(candidate.track_id) == int(self._drop_candidate_track_id)
        if self._drop_candidate_last_center is None:
            return False
        if str(candidate.class_name).lower() != self._drop_candidate_class_name:
            return False
        dx = float(candidate.cx) - self._drop_candidate_last_center[0]
        dy = float(candidate.cy) - self._drop_candidate_last_center[1]
        return (dx * dx + dy * dy) <= 64.0

    @staticmethod
    def _center_error(detection) -> float:
        ex = float(getattr(detection, "ex", 0.0))
        ey = float(getattr(detection, "ey", 0.0))
        return (ex * ex + ey * ey) ** 0.5

    def _reset_drop_candidate(self) -> None:
        self._drop_candidate_track_id = None
        self._drop_candidate_seen_frames = 0
        self._drop_candidate_last_center = None
        self._drop_candidate_class_name = ""

    @staticmethod
    def _target_ready(context: MissionContext) -> bool:
        return bool(
            context.health.vision_fresh
            and context.inputs.target_valid
            and context.inputs.target_locked
            and context.inputs.target_stable
        )

    @staticmethod
    def _release_action(payload: PayloadSlot) -> MissionAction | None:
        release = payload.release
        if release is None:
            return None
        release_type = str(release.type).strip().lower()
        key = f"rescue_release_payload_{payload.payload_id}"
        if release_type == "servo":
            if release.channel is None or release.pwm is None:
                return None
            return MissionAction(
                "set_servo",
                params={"channel": int(release.channel), "pwm": int(release.pwm)},
                key=key,
                once=True,
                priority=3,
            )
        if release_type == "relay":
            if release.relay_id is None or release.state is None:
                return None
            return MissionAction(
                "set_relay",
                params={"relay_id": int(release.relay_id), "state": bool(release.state)},
                key=key,
                once=True,
                priority=3,
            )
        return None


def build_rescue_config(settings: dict[str, Any]) -> RescueCompetitionMissionConfig:
    config = RescueCompetitionMissionConfig(
        initial_stage=RescueStage(str(settings.get("initial_stage", RescueStage.PREPARE.value))),
        idle_mode=str(settings.get("idle_mode", "IDLE")),
        auto_start=_strict_bool(settings.get("auto_start", False)),
        takeoff_altitude_m=float(settings.get("takeoff_altitude_m", 5.0)),
        takeoff_altitude_tolerance_m=float(settings.get("takeoff_altitude_tolerance_m", 0.5)),
        local_position_frame=int(settings.get("local_position_frame", 1)),
        drop_route_end_name=str(settings.get("drop_route_end_name", "drop_center")),
        recce_route_end_name=str(settings.get("recce_route_end_name", "recce_center")),
        home_route_end_name=str(settings.get("home_route_end_name", "home")),
        route_hold_s=float(settings.get("route_hold_s", 0.0)),
        align_mode=str(settings.get("align_mode", "OVERHEAD_HOLD")),
        dry_run_skip_vision=_strict_bool(settings.get("dry_run_skip_vision", False)),
        dry_run_skip_payload_release=_strict_bool(settings.get("dry_run_skip_payload_release", False)),
        search_drop_duration_s=float(settings.get("search_drop_duration_s", 2.0)),
        align_drop_duration_s=float(settings.get("align_drop_duration_s", 1.0)),
        drop_target_classes=_string_list(
            settings,
            "drop_target_classes",
            ["drop_cylinder", "cylinder", "target"],
        ),
        drop_target_min_confidence=float(settings.get("drop_target_min_confidence", 0.45)),
        drop_target_stable_frames=int(settings.get("drop_target_stable_frames", 5)),
        drop_target_max_center_error=float(settings.get("drop_target_max_center_error", 0.35)),
        align=_align_config(settings.get("align", {})),
        payload_release=_payload_release_timing(settings.get("payload_release", {})),
        recce=_recce_mission_config(settings.get("recce", {}), settings.get("scan_duration_s", None)),
        scan_duration_s=float(settings.get("scan_duration_s", 3.0)),
        land_complete_altitude_m=float(settings.get("land_complete_altitude_m", 0.3)),
        route=[_route_point(item, index) for index, item in enumerate(_list(settings, "route"))],
        drop_zones=[_mission_zone(item, index, "drop_zone") for index, item in enumerate(_list(settings, "drop_zones"))],
        recce_zones=[_mission_zone(item, index, "recce_zone") for index, item in enumerate(_list(settings, "recce_zones"))],
        payloads=[_payload_slot(item, index) for index, item in enumerate(_list(settings, "payloads"))],
    )
    _validate_route_end_names(config)
    return config


def _list(settings: dict[str, Any], key: str) -> list[Any]:
    value = settings.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"rescue_competition.{key} must be a list")
    return value


def _string_list(
    settings: dict[str, Any],
    key: str,
    default: list[str],
) -> list[str]:
    value = settings.get(key, default)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"rescue_competition.{key} must be a list")
    return [str(item) for item in value]


def _route_point(item: Any, index: int) -> RoutePoint:
    data = _mapping(item, "route", index)
    return RoutePoint(
        name=str(data.get("name", f"route_{index + 1}")),
        x=float(data["x"]),
        y=float(data["y"]),
        z=float(data["z"]),
        xy_tolerance_m=float(data.get("xy_tolerance_m", data.get("radius_m", 1.0))),
        z_tolerance_m=float(data.get("z_tolerance_m", 0.5)),
        max_speed_mps=float(data.get("max_speed_mps", 0.5)),
    )


def _mission_zone(item: Any, index: int, prefix: str) -> MissionZone:
    data = _mapping(item, prefix, index)
    return MissionZone(
        name=str(data.get("name", f"{prefix}_{index + 1}")),
        x=float(data["x"]),
        y=float(data["y"]),
        radius_m=float(data["radius_m"]),
        z=None if data.get("z") is None else float(data["z"]),
    )


def _payload_slot(item: Any, index: int) -> PayloadSlot:
    data = _mapping(item, "payloads", index)
    return PayloadSlot(
        payload_id=int(data.get("payload_id", index + 1)),
        label=str(data.get("label", "")),
        release=_payload_release(data.get("release"), index),
    )


def _payload_release(item: Any, index: int) -> PayloadRelease | None:
    if item is None:
        return None
    data = _mapping(item, "payloads.release", index)
    release_type = str(data.get("type", "")).strip().lower()
    if release_type == "servo":
        return PayloadRelease(
            type=release_type,
            channel=int(data["channel"]) if data.get("channel") is not None else None,
            pwm=int(data["pwm"]) if data.get("pwm") is not None else None,
        )
    if release_type == "relay":
        return PayloadRelease(
            type=release_type,
            relay_id=int(data["relay_id"]) if data.get("relay_id") is not None else None,
            state=_strict_bool(data["state"]) if data.get("state") is not None else None,
        )
    raise ValueError(f"rescue_competition.payloads[{index}].release.type must be servo or relay")


def _align_config(item: Any) -> DropAlignConfig:
    if item is None:
        item = {}
    if not isinstance(item, dict):
        raise ValueError("rescue_competition.align must be a mapping")
    return DropAlignConfig(
        max_ex_cam=float(item.get("max_ex_cam", 0.08)),
        max_ey_cam=float(item.get("max_ey_cam", 0.08)),
        min_target_size=float(item.get("min_target_size", 0.0)),
        require_target_locked=_strict_bool(item.get("require_target_locked", True)),
        require_target_stable=_strict_bool(item.get("require_target_stable", True)),
        hold_s=float(item.get("hold_s", 0.8)),
        timeout_s=float(item.get("timeout_s", 15.0)),
        lost_timeout_s=float(item.get("lost_timeout_s", 2.0)),
    )


def _payload_release_timing(item: Any) -> PayloadReleaseTiming:
    if item is None:
        item = {}
    if not isinstance(item, dict):
        raise ValueError("rescue_competition.payload_release must be a mapping")
    return PayloadReleaseTiming(
        delay_after_action_s=float(item.get("delay_after_action_s", 1.0)),
    )


def _recce_mission_config(item: Any, legacy_scan_duration: Any = None) -> RecceMissionConfig:
    if item is None:
        item = {}
    if not isinstance(item, dict):
        raise ValueError("rescue_competition.recce must be a mapping")
    scan_default = 3.0 if legacy_scan_duration is None else float(legacy_scan_duration)
    return RecceMissionConfig(
        config=RecceConfig(
            cylinder_classes=set(_string_list(item, "cylinder_classes", ["recce_cylinder", "cylinder"])),
            hazard_classes=set(
                _string_list(
                    item,
                    "hazard_classes",
                    [
                        "explosive",
                        "flammable",
                        "corrosive",
                        "toxic",
                        "oxidizer",
                        "biohazard",
                        "hazard_sign",
                    ],
                )
            ),
            min_cylinder_confidence=float(item.get("min_cylinder_confidence", 0.35)),
            min_hazard_confidence=float(item.get("min_hazard_confidence", 0.35)),
            vote_min_count=int(item.get("vote_min_count", 3)),
            vote_min_confidence_sum=float(item.get("vote_min_confidence_sum", 1.2)),
        ),
        scan_duration_s=float(item.get("scan_duration_s", scan_default)),
        output_dir=str(item.get("output_dir", "logs/recce")),
        output_json=_strict_bool(item.get("output_json", True)),
        output_csv=_strict_bool(item.get("output_csv", True)),
    )


def _mapping(item: Any, key: str, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"rescue_competition.{key}[{index}] must be a mapping")
    return item


def _validate_route_end_names(config: RescueCompetitionMissionConfig) -> None:
    if not config.route:
        return
    names = {point.name for point in config.route}
    for field_name, end_name in (
        ("drop_route_end_name", config.drop_route_end_name),
        ("recce_route_end_name", config.recce_route_end_name),
        ("home_route_end_name", config.home_route_end_name),
    ):
        if end_name not in names:
            raise ValueError(f"rescue_competition.{field_name} not found in route: {end_name}")


def _strict_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError(f"invalid payload release boolean: {value!r}")
