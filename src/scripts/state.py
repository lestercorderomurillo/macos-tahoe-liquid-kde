import datetime as _dt
import json
import os
from pathlib import Path
from typing import Literal


Status = Literal["running", "completed", "exited", "failed", "aborted"]


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(base) / "mac-tahoe-liquid-kde"


def last_run_file() -> Path:
    return state_dir() / "last-run.json"


def _now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


class RunTracker:
    def __init__(self, script: str, argv: list[str], theme_mode: str = "auto"):
        self.script = script
        self.argv = list(argv)
        self.theme_mode = theme_mode
        self.started_at = ""
        self.completed = False
        self.aborted = False
        self.active = False

    def start(self) -> None:
        self.started_at = _now_iso()
        self.active = True
        self._write("running", finished_at=None, exit_code=0)

    def mark_completed(self) -> None:
        self.completed = True

    def mark_aborted(self) -> None:
        self.aborted = True

    def finalize(self, exit_code: int) -> None:
        if not self.active:
            return
        if self.aborted:
            status: Status = "aborted"
        elif self.completed and exit_code == 0:
            status = "completed"
        elif exit_code == 0:
            status = "exited"
        else:
            status = "failed"
        self._write(status, finished_at=_now_iso(), exit_code=exit_code)

    def _command(self) -> str:
        return "./" + " ".join([self.script, *self.argv]).rstrip()

    def _write(self, status: Status, finished_at: str | None,
               exit_code: int) -> None:
        out = last_run_file()
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "script": self.script,
            "argv": self.argv,
            "command": self._command(),
            "cwd": str(Path.cwd()),
            "theme_mode": self.theme_mode,
            "status": status,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "exit_code": exit_code,
        }
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
