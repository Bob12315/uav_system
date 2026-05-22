from __future__ import annotations

import threading
import time
from typing import Any

import cv2
import numpy as np


class FrameHub:
    def __init__(
        self,
        *,
        quality: int = 75,
        max_fps: float = 15.0,
        max_width: int = 1280,
    ) -> None:
        self.quality = int(max(1, min(100, quality)))
        self.max_fps = float(max_fps)
        self.max_width = int(max_width)
        self._lock = threading.Lock()
        self._jpeg: bytes | None = None
        self._meta: dict[str, Any] = {
            "frame_id": None,
            "timestamp": None,
            "updated_at": None,
            "encode_fps": 0.0,
        }
        self._last_encode_at = 0.0
        self._set_placeholder("WAITING FOR YOLO FRAMES")

    def update_bgr(self, frame, *, frame_id: int, timestamp: float) -> None:
        now = time.time()
        min_interval = 1.0 / self.max_fps if self.max_fps > 0 else 0.0
        if min_interval > 0 and (now - self._last_encode_at) < min_interval:
            return

        output = frame
        height, width = output.shape[:2]
        if self.max_width > 0 and width > self.max_width:
            scale = self.max_width / float(width)
            output = cv2.resize(output, (self.max_width, max(1, int(height * scale))))

        ok, encoded = cv2.imencode(
            ".jpg",
            output,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.quality],
        )
        if not ok:
            return

        elapsed = now - self._last_encode_at if self._last_encode_at else 0.0
        encode_fps = 1.0 / elapsed if elapsed > 0 else 0.0
        with self._lock:
            self._jpeg = encoded.tobytes()
            self._meta = {
                "frame_id": int(frame_id),
                "timestamp": float(timestamp),
                "updated_at": now,
                "encode_fps": encode_fps,
                "width": int(output.shape[1]),
                "height": int(output.shape[0]),
            }
            self._last_encode_at = now

    def latest(self) -> tuple[bytes | None, dict[str, Any]]:
        with self._lock:
            return self._jpeg, dict(self._meta)

    def _set_placeholder(self, text: str) -> None:
        image = np.zeros((360, 640, 3), dtype=np.uint8)
        image[:] = (18, 22, 26)
        cv2.putText(
            image,
            text,
            (78, 184),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (180, 196, 205),
            2,
            cv2.LINE_AA,
        )
        ok, encoded = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.quality],
        )
        if ok:
            self._jpeg = encoded.tobytes()
            self._meta = {
                "frame_id": -1,
                "timestamp": time.time(),
                "updated_at": time.time(),
                "encode_fps": 0.0,
                "width": 640,
                "height": 360,
            }
