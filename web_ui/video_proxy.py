from __future__ import annotations

import time
import urllib.request
import base64
from collections.abc import Iterator


_PLACEHOLDER_JPEG = base64.b64decode(
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    b"////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////////////"
    b"////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/"
    b"xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/"
    b"9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Al//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEA"
    b"AhEDEQA/AKf/2Q=="
)


def proxy_mjpeg_stream(url: str, *, retry_delay_s: float = 1.0) -> Iterator[bytes]:
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5.0) as response:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    yield chunk
        except Exception:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(_PLACEHOLDER_JPEG)}\r\n\r\n".encode("ascii")
                + _PLACEHOLDER_JPEG
                + b"\r\n"
            )
            time.sleep(retry_delay_s)
