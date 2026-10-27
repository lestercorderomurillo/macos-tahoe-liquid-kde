"""Exercise the native menu importer and real X11 task changes on a private bus."""

import os
import select
import shutil
import subprocess

import pytest


def test_native_globalmenu_recovers_across_focus_and_service_changes(repo, tmp_path):
    for tool in ("cmake", "Xvfb", "dbus-run-session", "pkg-config"):
        if not shutil.which(tool):
            pytest.skip(f"{tool} required for the native Global Menu test")
    sdk = subprocess.run(["pkg-config", "--exists", "Qt6Widgets", "Qt6Test", "xcb"],
                         capture_output=True, timeout=10)
    if sdk.returncode:
        pytest.skip("Qt6 and XCB development files required")
    build = tmp_path / "build"
    result = subprocess.run(["cmake", "-S", str(repo / "tests/native/globalmenu"),
                             "-B", str(build)], capture_output=True, text=True, timeout=60)
    if result.returncode and "Could not find a package configuration file provided by" in result.stderr:
        pytest.skip("Plasma development SDK required: " + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(["cmake", "--build", str(build), "--parallel", "2"],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    bus_config = tmp_path / "bus.conf"
    # Disable service activation so no host desktop services enter the test bus.
    bus_config.write_text(
        '<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen>'
        '<policy context="default"><allow user="*"/><allow send_destination="*"/>'
        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>'
    )
    env = os.environ.copy()
    for key in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "SESSION_MANAGER"):
        env.pop(key, None)
    env.update({"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
                "XDG_DATA_HOME": str(tmp_path / "data"), "XDG_STATE_HOME": str(tmp_path / "state"),
                "XDG_CACHE_HOME": str(tmp_path / "cache"), "XDG_RUNTIME_DIR": str(runtime),
                "QT_QPA_PLATFORM": "xcb",
                "QT_QPA_PLATFORMTHEME": "generic", "QT_FORCE_STDERR_LOGGING": "1",
                "XDG_CURRENT_DESKTOP": "", "MTTKDE_TEST_X11": "1"})
    read_fd, write_fd = os.pipe()
    server = subprocess.Popen(["Xvfb", "-displayfd", str(write_fd), "-screen", "0",
                               "800x600x24", "-nolisten", "tcp"], pass_fds=(write_fd,),
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    os.close(write_fd)
    try:
        assert select.select([read_fd], [], [], 10)[0], "Xvfb did not start"
        env["DISPLAY"] = ":" + os.read(read_fd, 32).decode().strip()
        for binary in ("globalmenu-model-test", "globalmenu-popup-test"):
            result = subprocess.run(["dbus-run-session", "--config-file", str(bus_config),
                                     "--", str(build / binary)],
                                    env=env, capture_output=True, text=True, timeout=90)
            assert result.returncode == 0, result.stdout + result.stderr
    finally:
        os.close(read_fd)
        server.terminate()
        server.wait(timeout=10)
