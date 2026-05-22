from __future__ import annotations

from web_ui.config_store import MissionConfigStore
from web_ui.state import WebStateProvider


def test_state_snapshot_defaults_without_runner() -> None:
    state = WebStateProvider(None).snapshot()

    assert state["link"]["connected"] is False
    assert state["link"]["mode"] == "UNKNOWN"
    assert state["mission"]["stage"] == "UNKNOWN"
    assert state["target"]["valid"] is False


def test_config_patch_rejects_invalid_yaml(tmp_path) -> None:
    path = tmp_path / "mission.yaml"
    path.write_text("name: visual_tracking\n", encoding="utf-8")
    store = MissionConfigStore(lambda: path)

    result = store.patch("name: [")

    assert result["ok"] is False
    assert "invalid yaml" in result["message"]
    assert path.read_text(encoding="utf-8") == "name: visual_tracking\n"


def test_config_patch_writes_valid_yaml_atomically(tmp_path) -> None:
    path = tmp_path / "mission.yaml"
    path.write_text("name: old\n", encoding="utf-8")
    store = MissionConfigStore(lambda: path)

    result = store.patch("name: new\ninitial_mode: IDLE\n")

    assert result["ok"] is True
    assert path.read_text(encoding="utf-8") == "name: new\ninitial_mode: IDLE\n"

