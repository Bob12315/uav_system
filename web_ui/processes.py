from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


class YoloProcessManager:
    def __init__(
        self,
        *,
        project_root: Path,
        log_path: Path | None = None,
    ) -> None:
        self.project_root = project_root
        self.log_path = log_path or project_root / "runtime" / "logs" / "web_yolo.log"
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._started_at: float | None = None

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self.status(message="YOLO is already running")
            discovered = self._discover_yolo_pids()
            if discovered:
                self._process = None
                self._started_at = None
                return self.status(message="YOLO is already running")

            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text("", encoding="utf-8")
            log_handle = self.log_path.open("ab")
            command = self._build_command()
            self._process = subprocess.Popen(
                command,
                cwd=str(self.project_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            log_handle.close()
            self._started_at = time.time()
            time.sleep(1.0)
            if self._process.poll() is not None:
                message = "YOLO failed to start"
                log_tail = self._log_tail()
                if log_tail:
                    message = f"{message}: {log_tail}"
                return self.status(message=message)
            return self.status(message="YOLO started")

    def stop(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                self._terminate_pid(process.pid)
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    pass
                self._process = None
                self._started_at = None
                return self.status(message="YOLO stopped")

            discovered = self._discover_yolo_pids()
            if discovered:
                for pid in discovered:
                    self._terminate_pid(pid)
                self._process = None
                self._started_at = None
                return self.status(message="YOLO stopped")

            self._process = None
            self._started_at = None
            return self.status(message="YOLO is not running")

    def status(self, message: str = "") -> dict[str, Any]:
        process = self._process
        running = process is not None and process.poll() is None
        discovered = [] if running else self._discover_yolo_pids()
        if discovered:
            running = True
        returncode = None if running or process is None else process.poll()
        if not running and not message and returncode is not None:
            tail = self._log_tail()
            message = f"YOLO exited rc={returncode}"
            if tail:
                message = f"{message}: {tail}"
        return {
            "ok": True,
            "running": running,
            "pid": process.pid if process is not None and process.poll() is None else (discovered[0] if discovered else None),
            "pids": [process.pid] if process is not None and process.poll() is None else discovered,
            "returncode": returncode,
            "started_at": self._started_at if running else None,
            "log_path": str(self.log_path),
            "command": self._command_label(),
            "message": message,
        }

    def _discover_yolo_pids(self) -> list[int]:
        script = str(self.project_root / "yolo_app" / "main.py")
        try:
            output = subprocess.check_output(
                ["pgrep", "-f", script],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []
        current = os.getpid()
        pids: list[int] = []
        for line in output.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != current:
                pids.append(pid)
        return sorted(set(pids))

    def _terminate_pid(self, pid: int) -> None:
        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            return
        try:
            if pgid == pid:
                os.killpg(pgid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if not self._pid_exists(pid):
                return
            time.sleep(0.1)
        try:
            if pgid == pid:
                os.killpg(pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    def _pid_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def _log_tail(self, max_chars: int = 1200) -> str:
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[-max_chars:].strip()

    def _build_command(self) -> list[str]:
        override = os.environ.get("UAV_YOLO_START_COMMAND")
        if override:
            return ["bash", "-lc", override]

        script = self.project_root / "yolo_app" / "main.py"
        shell = (
            "set -e; "
            "if command -v conda >/dev/null 2>&1; then "
            "  eval \"$(conda shell.bash hook)\"; "
            "elif [ -f \"$HOME/miniconda3/etc/profile.d/conda.sh\" ]; then "
            "  . \"$HOME/miniconda3/etc/profile.d/conda.sh\"; "
            "elif [ -f \"$HOME/anaconda3/etc/profile.d/conda.sh\" ]; then "
            "  . \"$HOME/anaconda3/etc/profile.d/conda.sh\"; "
            "elif [ -f \"/opt/conda/etc/profile.d/conda.sh\" ]; then "
            "  . \"/opt/conda/etc/profile.d/conda.sh\"; "
            "else "
            "  echo 'conda was not found'; exit 127; "
            "fi; "
            f"conda activate yolo; exec python3 {script} --show false"
        )
        return ["bash", "-lc", shell]

    def _command_label(self) -> str:
        return os.environ.get(
            "UAV_YOLO_START_COMMAND",
            "conda activate yolo && python3 ~/uav_project/src/yolo_app/main.py --show false",
        )
