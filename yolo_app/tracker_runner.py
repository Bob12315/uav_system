from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from .config import AppConfig
    from .models import Track
    from .rknn_detector import Detection, RknnDetector
except ImportError:
    from config import AppConfig
    from models import Track
    from rknn_detector import Detection, RknnDetector


class TrackerRunner:
    """Expose detector results as project-level tracks for either supported backend."""

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.rknn_detector: RknnDetector | None = None
        self.model = None
        self.iou_tracker: _IoUTracker | None = None

        if Path(cfg.model_path).suffix.lower() == ".rknn":
            self.rknn_detector = RknnDetector(
                model_path=cfg.model_path,
                conf_thres=cfg.conf_thres,
                iou_thres=cfg.iou_thres,
                classes=cfg.classes,
                class_names=tuple(cfg.class_names),
            )
            self.iou_tracker = _IoUTracker(max_lost_frames=cfg.max_lost_frames)
        else:
            from ultralytics import YOLO

            self.model = YOLO(cfg.model_path)

    def run(self, frame) -> list[Track]:
        if self.rknn_detector is not None and self.iou_tracker is not None:
            return self.iou_tracker.update(self.rknn_detector.detect(frame))
        return self._run_ultralytics(frame)

    def release(self) -> None:
        if self.rknn_detector is not None:
            self.rknn_detector.release()

    def _run_ultralytics(self, frame) -> list[Track]:
        results = self.model.track(
            source=frame,
            persist=True,
            tracker=self.cfg.tracker,
            conf=self.cfg.conf_thres,
            iou=self.cfg.iou_thres,
            imgsz=self.cfg.img_size,
            device=self.cfg.device if self.cfg.device else None,
            classes=self.cfg.classes or None,
            verbose=False,
        )
        if not results:
            return []

        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None or boxes.xyxy is None:
            return []

        names = result.names or {}
        xyxy_list = boxes.xyxy.cpu().tolist()
        id_list = boxes.id.int().cpu().tolist()
        cls_list = boxes.cls.int().cpu().tolist() if boxes.cls is not None else [0] * len(id_list)
        conf_list = boxes.conf.cpu().tolist() if boxes.conf is not None else [0.0] * len(id_list)

        tracks: list[Track] = []
        for xyxy, track_id, class_id, confidence in zip(xyxy_list, id_list, cls_list, conf_list):
            x1, y1, x2, y2 = [float(value) for value in xyxy]
            tracks.append(
                Track(
                    track_id=int(track_id),
                    class_id=int(class_id),
                    class_name=str(names.get(int(class_id), int(class_id))),
                    confidence=float(confidence),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return tracks


@dataclass(slots=True)
class _TrackState:
    track: Track
    lost_frames: int = 0


class _IoUTracker:
    """Maintain short-lived IDs for RKNN detections consumed by target management."""

    def __init__(self, max_lost_frames: int, match_iou: float = 0.25) -> None:
        self.max_lost_frames = max(1, max_lost_frames)
        self.match_iou = match_iou
        self.next_id = 1
        self.states: dict[int, _TrackState] = {}

    def update(self, detections: list[Detection]) -> list[Track]:
        for state in self.states.values():
            state.lost_frames += 1

        candidates = []
        for detection_index, detection in enumerate(detections):
            for track_id, state in self.states.items():
                if state.track.class_id != detection.class_id:
                    continue
                overlap = _iou(detection, state.track)
                if overlap >= self.match_iou:
                    candidates.append((overlap, detection_index, track_id))

        assignments: dict[int, int] = {}
        used_track_ids: set[int] = set()
        for _, detection_index, track_id in sorted(candidates, reverse=True):
            if detection_index in assignments or track_id in used_track_ids:
                continue
            assignments[detection_index] = track_id
            used_track_ids.add(track_id)

        visible: list[Track] = []
        for index, detection in enumerate(detections):
            track_id = assignments.get(index)
            if track_id is None:
                track_id = self.next_id
                self.next_id += 1
            track = Track(
                track_id=track_id,
                class_id=detection.class_id,
                class_name=detection.class_name,
                confidence=detection.confidence,
                x1=detection.x1,
                y1=detection.y1,
                x2=detection.x2,
                y2=detection.y2,
            )
            self.states[track_id] = _TrackState(track=track)
            visible.append(track)

        self.states = {
            track_id: state
            for track_id, state in self.states.items()
            if state.lost_frames <= self.max_lost_frames
        }
        return visible


def _iou(first, second) -> float:
    left = max(first.x1, second.x1)
    top = max(first.y1, second.y1)
    right = min(first.x2, second.x2)
    bottom = min(first.y2, second.y2)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first.x2 - first.x1) * max(0.0, first.y2 - first.y1)
    second_area = max(0.0, second.x2 - second.x1) * max(0.0, second.y2 - second.y1)
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0
