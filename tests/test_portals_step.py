"""Portal routing restarts through the active init backend safely."""

import os
import signal
import subprocess

from steps import portals


def test_systemd_portals_use_distro_user_manager(monkeypatch):
    calls = []
    monkeypatch.setattr(
        portals, "user_service_manager_command",
        lambda *args: ["manager", "--user", *args],
    )
    monkeypatch.setattr(
        portals, "run_user",
        lambda command, **kwargs: (
            calls.append(command) or subprocess.CompletedProcess(command, 0)
        ),
    )
    monkeypatch.setattr(
        portals.os, "kill",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("systemd path terminated processes directly")),
    )

    portals._bounce_services()

    assert calls == [
        ["manager", "--user", "restart", service]
        for service in portals.PORTAL_SERVICES
    ]


def test_openrc_portals_terminate_only_same_user_managed_processes(
        monkeypatch, tmp_path):
    proc = tmp_path / "proc"
    managed = proc / "101"
    unrelated = proc / "102"
    managed.mkdir(parents=True)
    unrelated.mkdir()
    (managed / "cmdline").write_bytes(
        b"/usr/lib/xdg-desktop-portal-kde\0--replace\0")
    (unrelated / "cmdline").write_bytes(b"/usr/bin/other-process\0")
    monkeypatch.setattr(portals, "_PROC_ROOT", proc)
    monkeypatch.setattr(portals, "user_service_manager_command",
                        lambda *args: None)
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    killed = []
    monkeypatch.setattr(portals.os, "kill",
                        lambda pid, sig: killed.append((pid, sig)))

    portals._bounce_services()

    assert killed == [(101, signal.SIGTERM)]
