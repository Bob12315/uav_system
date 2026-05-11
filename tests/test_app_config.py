from __future__ import annotations

import pytest

from app.mode_registry import ModeRegistry
from app.app_config import build_arg_parser, load_app_config
from flight_modes.approach_track.config import ApproachBodyConfig, ApproachTrackConfig
from flight_modes.overhead_hold.config import OverheadBodyConfig, OverheadHoldConfig


def test_loads_new_flight_mode_config_layout() -> None:
    args = build_arg_parser().parse_args(
        ["--no-yolo-udp", "--no-ui", "--run-seconds", "1", "--send-commands", "false"]
    )

    config = load_app_config(args)

    assert config.runtime.ui_enabled is False
    assert config.runtime.connect_telemetry is True
    assert config.blackbox.enabled is True
    assert config.blackbox.sample_hz == pytest.approx(20.0)
    assert config.approach_track.approach.kp_vx == pytest.approx(4.0)
    assert config.approach_track.require_yaw_aligned_for_approach is False
    assert config.overhead_hold.gimbal.downward_pitch_rad == pytest.approx(
        -1.5707963267948966
    )
    assert config.overhead_hold.body.kp_vy == pytest.approx(3.0)
    assert config.overhead_hold.approach.kp_vx == pytest.approx(3.0)
    assert config.shaper.max_vx == pytest.approx(3.0)


def test_mode_registry_runtime_config_update_preserves_controller_references() -> None:
    registry = ModeRegistry(
        approach_config=ApproachTrackConfig(body=ApproachBodyConfig(kp_yaw=0.2)),
        overhead_config=OverheadHoldConfig(body=OverheadBodyConfig(kp_vy=1.0)),
    )
    overhead_mode = registry.get("OVERHEAD_HOLD")

    registry.apply_configs(
        approach_config=ApproachTrackConfig(body=ApproachBodyConfig(kp_yaw=0.7)),
        overhead_config=OverheadHoldConfig(body=OverheadBodyConfig(kp_vy=3.5)),
    )

    assert registry.approach_config.body.kp_yaw == pytest.approx(0.7)
    assert overhead_mode.body.config.kp_vy == pytest.approx(3.5)
