from __future__ import annotations

from http import HTTPStatus

import numpy as np

from yolo_app.frame_hub import FrameHub
from yolo_app.mjpeg_server import write_mjpeg_response


def test_frame_hub_keeps_only_latest_frame() -> None:
    hub = FrameHub(max_fps=0)
    first = np.zeros((16, 16, 3), dtype=np.uint8)
    second = np.full((16, 16, 3), 255, dtype=np.uint8)

    hub.update_bgr(first, frame_id=1, timestamp=10.0)
    hub.update_bgr(second, frame_id=2, timestamp=11.0)
    jpeg, meta = hub.latest()

    assert jpeg is not None
    assert jpeg.startswith(b"\xff\xd8")
    assert meta["frame_id"] == 2
    assert meta["timestamp"] == 11.0


class _OneWrite:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, data: bytes) -> int:
        self.data.extend(data)
        raise BrokenPipeError()

    def flush(self) -> None:
        return None


class _FakeHandler:
    def __init__(self) -> None:
        self.status = None
        self.headers: list[tuple[str, str]] = []
        self.wfile = _OneWrite()

    def send_response(self, status: HTTPStatus) -> None:
        self.status = status

    def send_header(self, key: str, value: str) -> None:
        self.headers.append((key, value))

    def end_headers(self) -> None:
        return None


def test_mjpeg_response_contains_boundary() -> None:
    hub = FrameHub(max_fps=0)
    hub.update_bgr(np.zeros((8, 8, 3), dtype=np.uint8), frame_id=1, timestamp=1.0)
    handler = _FakeHandler()

    write_mjpeg_response(handler, hub)

    assert handler.status == HTTPStatus.OK
    assert b"--frame\r\n" in handler.wfile.data
    assert b"Content-Type: image/jpeg" in handler.wfile.data
