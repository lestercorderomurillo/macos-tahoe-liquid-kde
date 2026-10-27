#!/usr/bin/env python3
"""Run as tester in Dockerfile.artix-dinit with the repo mounted read-only.

Exercise real PID-1 detection and user crontab execution with dinit supervising
cronie. This proves the scheduling transport, not KDE desktop compatibility.
"""

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--tick":
        target = Path(sys.argv[2])
        staging = target.with_suffix(".tmp")
        staging.write_text(json.dumps({"uid": os.getuid()}))
        staging.replace(target)
        return

    if not Path("/.dockerenv").exists() or os.getuid() == 0:
        raise SystemExit("Run only as tester in the disposable dinit container")
    if "MTTKDE_INIT" in os.environ:
        raise SystemExit("The probe must detect the real init without an override")
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "src/scripts"))
    import distro
    from steps import _scheduler

    assert distro.current_distro() == "artix"
    assert distro.init_system() == "dinit"
    assert distro.user_service_manager_command("daemon-reload") is None
    assert distro.package_for("crontab") == "cronie"
    if "--inactive" in sys.argv:
        assert not distro.cron_daemon_running()
        print("PASS: stopped cron daemon is not reported as running")
        return
    assert distro.cron_daemon_running()
    (Path.home() / ".cache").mkdir(exist_ok=True)
    original = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    assert original.returncode != 0 and "no crontab" in original.stderr.lower()

    with tempfile.TemporaryDirectory(prefix="mttkde-dinit-") as directory:
        root = Path(directory)
        unrelated = "# preserve this user's unrelated configuration"
        subprocess.run(["crontab", "-"], input=unrelated + "\n", text=True, check=True)
        periodic = root / "periodic.json"
        fixed = root / "fixed.json"
        command = lambda output: _scheduler.cron_command(
            sys.executable, Path(__file__).resolve(), "--tick", output)
        try:
            assert _scheduler.install_periodic("oled", 1, command(periodic))
            assert _scheduler.install_periodic("oled", 1, command(periodic))
            # Two upcoming boundaries avoid missing a tick during setup.
            now = datetime.datetime.now()
            times = [now + datetime.timedelta(minutes=n) for n in (1, 2)]
            assert _scheduler.install_at_times(
                "theme", [(t.hour, t.minute) for t in times], command(fixed))
            entries = subprocess.check_output(["crontab", "-l"], text=True)
            assert entries.count("mac-tahoe-liquid-kde:oled") == 1
            assert entries.count("mac-tahoe-liquid-kde:theme") == 2
            assert unrelated in entries
            print("dinit detected; real user cron entries installed", flush=True)
            deadline = time.monotonic() + 135
            while not (periodic.exists() and fixed.exists()):
                if time.monotonic() >= deadline:
                    raise AssertionError("Cron did not execute both scheduled commands")
                time.sleep(1)
            assert json.loads(periodic.read_text())["uid"] == os.getuid()
            assert json.loads(fixed.read_text())["uid"] == os.getuid()
            assert _scheduler.remove_periodic("oled") == _scheduler.RemovalStatus.REMOVED
            assert _scheduler.remove_periodic("theme") == _scheduler.RemovalStatus.REMOVED
            assert subprocess.check_output(["crontab", "-l"], text=True).strip() == unrelated
            assert _scheduler.remove_periodic("oled") == _scheduler.RemovalStatus.ABSENT
            print("PASS: both jobs executed as tester; reinstall and cleanup preserved unrelated entries")
        finally:
            subprocess.run(["crontab", "-r"], check=True)


if __name__ == "__main__":
    main()
