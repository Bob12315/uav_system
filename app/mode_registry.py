from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass

from flight_modes.approach_track import ApproachTrackConfig, ApproachTrackMode
from flight_modes.base_mode import FlightMode
from flight_modes.corridor_follow import CorridorFollowMode
from flight_modes.overhead_hold import OverheadHoldConfig, OverheadHoldMode


@dataclass(slots=True)
class ModeRegistry:
    approach_config: ApproachTrackConfig
    overhead_config: OverheadHoldConfig
    _modes: dict[str, FlightMode] = field(init=False)

    def __post_init__(self) -> None:
        self._modes = {
            ApproachTrackMode.name: ApproachTrackMode(config=self.approach_config),
            OverheadHoldMode.name: OverheadHoldMode(config=self.overhead_config),
            CorridorFollowMode.name: CorridorFollowMode(),
        }

    def get(self, name: str) -> FlightMode:
        try:
            return self._modes[name]
        except KeyError as exc:
            raise KeyError(f"unknown flight mode: {name}") from exc

    def reset_all(self) -> None:
        for mode in self._modes.values():
            mode.reset()

    def apply_configs(
        self,
        *,
        approach_config: ApproachTrackConfig,
        overhead_config: OverheadHoldConfig,
        reset: bool = True,
    ) -> None:
        copy_dataclass_values(self.approach_config, approach_config)
        copy_dataclass_values(self.overhead_config, overhead_config)
        if reset:
            self.reset_all()


def copy_dataclass_values(target: object, source: object) -> None:
    if not (is_dataclass(target) and is_dataclass(source)):
        raise TypeError("runtime config updates require dataclass instances")
    for item in fields(target):
        next_value = getattr(source, item.name)
        current_value = getattr(target, item.name)
        if is_dataclass(current_value) and is_dataclass(next_value):
            copy_dataclass_values(current_value, next_value)
        else:
            setattr(target, item.name, next_value)
