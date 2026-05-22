from __future__ import annotations

import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from frame_hub import FrameHub
except ImportError:
    from yolo_app.frame_hub import FrameHub


class MjpegServer:
    def __init__(self, hub: FrameHub, *, host: str, port: int, path: str = "/video.mjpeg") -> None:
        self.hub = hub
        self.host = host
        self.port = int(port)
        self.path = path
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        hub = self.hub
        path = self.path

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != path:
                    self.send_error(HTTPStatus.NOT_FOUND, "not found")
                    return
                write_mjpeg_response(self, hub)

            def log_message(self, _format: str, *args) -> None:
                return

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="YoloMjpegServer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


def write_mjpeg_response(handler: BaseHTTPRequestHandler, hub: FrameHub, *, poll_s: float = 0.05) -> None:
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
    handler.end_headers()

    last_frame_id = object()
    while True:
        jpeg, meta = hub.latest()
        frame_id = meta.get("frame_id")
        if jpeg is None or frame_id == last_frame_id:
            time.sleep(poll_s)
            continue
        last_frame_id = frame_id
        try:
            handler.wfile.write(
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
                + jpeg
                + b"\r\n"
            )
            handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
