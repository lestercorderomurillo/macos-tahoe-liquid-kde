# USELESS: subprocess + live_ready hard-coded per test — never exercises a real Plasma DBus round-trip
from types import SimpleNamespace

from steps import apply
from steps import nautilus as nautilus_step


def _result(returncode: int = 0, stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def test_apply_install_command_profile_is_safe(monkeypatch, tmp_path):
    home = tmp_path / "home"
    switch = home / ".local/bin/mac-tahoe-theme-switch"
    switch.parent.mkdir(parents=True, exist_ok=True)
    switch.write_text("#!/bin/sh\nexit 0\n")
    switch.chmod(0o755)

    subprocess_calls = []
    subprocess_kwargs = []
    qdbus_calls = []
    markers = []

    monkeypatch.setattr(apply, "HOME", home)
    monkeypatch.setattr(apply, "theme_mode", lambda: "dark")
    monkeypatch.setattr(apply, "_flush_caches", lambda: markers.append("flush"))
    monkeypatch.setattr(apply, "qdbus_call", lambda *args: qdbus_calls.append(args) or True)
    monkeypatch.setattr(apply.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(apply, "ok", lambda _msg: None)
    monkeypatch.setattr(apply, "warn", lambda _msg: markers.append("warn"))
    monkeypatch.setattr(
        apply,
        "feat_enabled",
        lambda name, default=True: {
            "FONTS": False,
            "WALLPAPERS": False,
            "ACRYLIC_GLASS": False,
        }.get(name, default),
    )
    monkeypatch.setattr(apply, "have", lambda cmd: cmd == "nautilus")

    def fake_run(cmd, **kwargs):
        subprocess_calls.append(tuple(cmd))
        subprocess_kwargs.append(kwargs)
        return _result()

    monkeypatch.setattr(apply.subprocess, "run", fake_run)

    apply.install()

    assert "flush" in markers
    assert (str(switch), "dark", "install") in subprocess_calls
    assert not any("timeout" in kwargs for kwargs in subprocess_kwargs)
    assert ("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure") in qdbus_calls
    assert not any(cmd[0] == "plasma-apply-lookandfeel" for cmd in subprocess_calls)
    assert not any(cmd[0] == "nautilus" for cmd in subprocess_calls)
    assert not any(cmd[:2] == ("systemctl", "--user") for cmd in subprocess_calls)
    assert not any(args[0] == "org.kde.plasmashell" for args in qdbus_calls)


def test_apply_uninstall_command_profile_is_safe(monkeypatch, tmp_path):
    home = tmp_path / "home"
    plasmarc = home / ".config/plasmarc"
    plasmarc.parent.mkdir(parents=True, exist_ok=True)
    plasmarc.write_text(
        "[Theme]\nname=default\n\n"
        "[Theme-plasmathemeexplorer]\nname=MacTahoeLiquidKde-Dark\n"
    )

    subprocess_calls = []
    markers = []
    kw_writes = []
    live_calls = []

    monkeypatch.setattr(apply, "HOME", home)
    monkeypatch.setattr(apply, "_scrub_kdedefaults", lambda: markers.append("scrub"))
    monkeypatch.setattr(apply, "_flush_caches", lambda: markers.append("flush"))
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: True)
    monkeypatch.setattr(apply, "kw_write", lambda *args: kw_writes.append(args))
    monkeypatch.setattr(
        apply,
        "reset_kde_color_scheme_config",
        lambda scheme: markers.append(("scheme", scheme)),
    )
    monkeypatch.setattr(
        apply,
        "_apply_lookandfeel_live",
        lambda laf: live_calls.append(("laf", laf)) or True,
    )
    monkeypatch.setattr(
        apply,
        "apply_cursortheme_live",
        lambda theme: live_calls.append(("cursor", theme)) or True,
    )
    # cycle_widget_style_live and qdbus_call are imported at module level
    # in apply.py and were previously NOT mocked. The real
    # cycle_widget_style_live writes ``widgetStyle=Breeze`` to the
    # invoking user's real ``~/.config/kdeglobals`` and broadcasts a
    # KGlobalSettings refresh — which, combined with the
    # LookAndFeelPackage=org.kde.breeze.desktop write earlier in
    # uninstall(), causes plasmashell to swap the live wallpaper to
    # Breeze's default. Mock both so the test is hermetic.
    monkeypatch.setattr(
        apply,
        "cycle_widget_style_live",
        lambda target: live_calls.append(("cycle", target)) or True,
    )
    monkeypatch.setattr(
        apply, "qdbus_call",
        lambda *args: live_calls.append(("qdbus", args)) or True,
    )
    monkeypatch.setattr(apply.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(apply, "ok", lambda _msg: None)
    monkeypatch.setattr(apply, "warn", lambda _msg: markers.append("warn"))
    monkeypatch.setattr(
        apply,
        "feat_enabled",
        lambda name, default=True: {
            "FONTS": False,
            "CURSORS": True,
            "ICONS": False,
            "WALLPAPERS": False,
        }.get(name, default),
    )
    monkeypatch.setattr(
        apply,
        "have",
        lambda cmd: cmd in {
            "plasma-apply-lookandfeel",
            "plasma-apply-cursortheme",
            "kwriteconfig6",
            "qdbus6",
        },
    )

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(tuple(cmd))
        return _result()

    monkeypatch.setattr(apply.subprocess, "run", fake_run)
    # run_user is the v0.10 wrapper used by apply.py; same fake.
    monkeypatch.setattr(apply, "run_user", fake_run)

    apply.uninstall()

    assert "scrub" in markers
    assert "flush" in markers
    assert ("scheme", "BreezeLight") in markers
    assert ("laf", "org.kde.breeze.desktop") in live_calls
    assert ("cursor", "breeze_cursors") in live_calls
    # The widget-style cycle is invoked with target Breeze (this is what
    # forces running Qt apps off Kvantum onto plain Breeze). Pin it so a
    # future "skip the cycle on uninstall" change leaves a regression
    # trail in the test rather than in the user's right-click menus.
    assert ("cycle", "Breeze") in live_calls
    assert "[Theme-plasmathemeexplorer]" not in plasmarc.read_text()
    assert not any("nautilus" in part for cmd in subprocess_calls for part in cmd)
    assert not any("plasma-plasmashell" in part for cmd in subprocess_calls for part in cmd)
    assert (
        "--file", "kdeglobals", "--group", "KDE",
        "--key", "LookAndFeelPackage", "org.kde.breeze.desktop",
    ) in kw_writes
    assert (
        "--file", "kcminputrc", "--group", "Mouse",
        "--key", "cursorTheme", "breeze_cursors",
    ) in kw_writes


def test_apply_uninstall_skips_live_mutation_when_plasma_not_ready(monkeypatch, tmp_path):
    home = tmp_path / "home"
    plasmarc = home / ".config/plasmarc"
    plasmarc.parent.mkdir(parents=True, exist_ok=True)
    plasmarc.write_text("[Theme]\nname=default\n")

    markers = []
    live_calls = []
    qdbus_calls = []

    monkeypatch.setattr(apply, "HOME", home)
    monkeypatch.setattr(apply, "_scrub_kdedefaults", lambda: markers.append("scrub"))
    monkeypatch.setattr(apply, "_flush_caches", lambda: markers.append("flush"))
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: False)
    monkeypatch.setattr(apply, "kw_write", lambda *_args: True)
    monkeypatch.setattr(
        apply,
        "reset_kde_color_scheme_config",
        lambda scheme: markers.append(("scheme", scheme)),
    )
    monkeypatch.setattr(
        apply,
        "_apply_lookandfeel_live",
        lambda laf: live_calls.append(("laf", laf)) or True,
    )
    monkeypatch.setattr(
        apply,
        "apply_cursortheme_live",
        lambda theme: live_calls.append(("cursor", theme)) or True,
    )
    monkeypatch.setattr(
        apply,
        "cycle_widget_style_live",
        lambda style: live_calls.append(("cycle", style)) or True,
    )
    monkeypatch.setattr(apply, "qdbus_call", lambda *args: qdbus_calls.append(args) or True)
    monkeypatch.setattr(apply.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(apply, "ok", lambda _msg: None)
    monkeypatch.setattr(apply, "warn", lambda msg: markers.append(msg))
    monkeypatch.setattr(
        apply,
        "feat_enabled",
        lambda name, default=True: {
            "FONTS": False,
            "CURSORS": True,
            "ICONS": False,
            "WALLPAPERS": False,
        }.get(name, default),
    )
    monkeypatch.setattr(
        apply,
        "have",
        lambda cmd: cmd in {
            "plasma-apply-lookandfeel",
            "plasma-apply-cursortheme",
            "kwriteconfig6",
            "qdbus6",
        },
    )

    apply.uninstall()

    assert "flush" in markers
    assert ("scheme", "BreezeLight") in markers
    # When plasma session is not ready, the live mutations are intentionally
    # silenced — the final plasmashell restart picks up on-disk Breeze state.
    # No alarming ⚠ markers in this path.
    assert "Live Breeze look-and-feel apply skipped" not in markers
    assert "Live cursor apply skipped" not in markers
    assert live_calls == []
    assert qdbus_calls == []


def test_restart_plasma_prefers_sigkill_over_sigterm(monkeypatch):
    subprocess_calls = []
    popen_calls = []

    monkeypatch.setattr(apply.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(apply, "ok", lambda _msg: None)

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(tuple(cmd))
        if cmd[:4] == ["systemctl", "--user", "start", "plasma-plasmashell"]:
            return _result(0)
        if cmd[:2] == ["pgrep", "-x"]:
            return _result(0)
        return _result(0, stdout="")

    monkeypatch.setattr(apply.subprocess, "run", fake_run)
    monkeypatch.setattr(
        apply.subprocess,
        "Popen",
        lambda cmd, **_kwargs: popen_calls.append(tuple(cmd)) or _result(),
    )

    apply.restart_plasma()

    assert (
        "systemctl",
        "--user",
        "kill",
        "--signal=KILL",
        "plasma-plasmashell",
    ) in subprocess_calls
    assert ("systemctl", "--user", "start", "plasma-plasmashell") in subprocess_calls
    assert not any("SIGTERM" in part for cmd in subprocess_calls for part in cmd)
    assert not any(part == "kquitapp6" for cmd in subprocess_calls for part in cmd)
    assert not popen_calls


def test_restart_plasma_falls_back_when_systemctl_hangs(monkeypatch):
    subprocess_calls = []
    popen_calls = []

    monkeypatch.setattr(apply.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(apply, "ok", lambda _msg: None)

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(tuple(cmd))
        if cmd[:4] == ["systemctl", "--user", "kill", "--signal=KILL"]:
            raise apply.subprocess.TimeoutExpired(cmd, timeout=8)
        if cmd[:4] == ["systemctl", "--user", "start", "plasma-plasmashell"]:
            raise apply.subprocess.TimeoutExpired(cmd, timeout=8)
        if cmd[:2] == ["pgrep", "-x"]:
            return _result(1, stdout="")
        return _result(0, stdout="")

    monkeypatch.setattr(apply.subprocess, "run", fake_run)
    monkeypatch.setattr(
        apply.subprocess,
        "Popen",
        lambda cmd, **_kwargs: popen_calls.append(tuple(cmd)) or _result(),
    )

    apply.restart_plasma()

    assert ("systemctl", "--user", "start", "plasma-plasmashell") in subprocess_calls
    assert ("kstart", "plasmashell") in popen_calls


def test_nautilus_install_does_not_force_quit(monkeypatch):
    """Install must NEVER use ``nautilus -q``. The graceful gdbus
    Application.Quit + gapplication relaunch IS allowed and is what
    actually picks up the new gsettings without leaving stale state.

    v0.10: default-handler binding is written via direct
    ``kwriteconfig6 mimeapps.list`` (``_set_default``) instead of the
    ``xdg-mime`` shell dispatcher; pgrep + gdbus go through ``run_user``
    so the child fully drops privs. The fake unifies both paths so
    ``gdbus_seen`` stays consistent across run_user and subprocess.run."""
    subprocess_calls = []
    popen_calls = []
    set_default_calls = []

    monkeypatch.setattr(nautilus_step, "_is_kde", lambda: True)
    monkeypatch.setattr(nautilus_step, "_apply_overrides", lambda: None)
    monkeypatch.setattr(nautilus_step, "_apply_gsettings", lambda: None)
    monkeypatch.setattr(nautilus_step, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus_step, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus_step.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(
        nautilus_step,
        "have",
        lambda cmd: cmd in {"nautilus", "gdbus", "gapplication"},
    )
    monkeypatch.setattr(
        nautilus_step,
        "_set_default",
        lambda desktop, mime: set_default_calls.append((desktop, mime)) or True,
    )

    gdbus_seen = {"v": False}

    def unified_run(cmd, **_kwargs):
        subprocess_calls.append(tuple(cmd))
        if cmd[:2] == ["pgrep", "-x"]:
            # Nautilus reports running until the gdbus Quit has fired.
            return _result(1 if gdbus_seen["v"] else 0)
        if cmd[:2] == ["gdbus", "call"]:
            gdbus_seen["v"] = True
        return _result(0)

    monkeypatch.setattr(nautilus_step.subprocess, "run", unified_run)
    monkeypatch.setattr(nautilus_step, "run_user", unified_run)
    monkeypatch.setattr(
        nautilus_step.subprocess,
        "Popen",
        lambda cmd, **_kwargs: popen_calls.append(tuple(cmd)) or _result(),
    )

    nautilus_step.install()

    # mimeapps.list bindings are written via _set_default, not xdg-mime.
    assert (nautilus_step.NAUTILUS_DESKTOP, nautilus_step.MIME_FOLDER) in set_default_calls
    assert (nautilus_step.NAUTILUS_DESKTOP, nautilus_step.MIME_SEARCH) in set_default_calls
    # Force-quit is the unsafe path — must never appear.
    assert not any(cmd[:2] == ("nautilus", "-q") for cmd in subprocess_calls)
    # No xdg-mime spawn — v0.10 went direct to kwriteconfig6.
    assert not any(cmd[:1] == ("xdg-mime",) for cmd in subprocess_calls)
    # Graceful gdbus quit + relaunch IS expected when nautilus is running.
    assert any(cmd[:2] == ("gdbus", "call") for cmd in subprocess_calls)
    assert any(cmd[:2] == ("gapplication", "launch") for cmd in popen_calls)


def test_nautilus_install_writes_mimeapps_via_kwriteconfig6(monkeypatch):
    """v0.10: ``_set_default`` calls ``kw_write`` against
    ``mimeapps.list`` directly. Replaces the prior xdg-mime timeout
    assertion — there is no xdg-mime path to time out anymore."""
    kw_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(nautilus_step, "_is_kde", lambda: True)
    monkeypatch.setattr(nautilus_step, "_apply_overrides", lambda: None)
    monkeypatch.setattr(nautilus_step, "_apply_gsettings", lambda: None)
    monkeypatch.setattr(nautilus_step, "_nautilus_running", lambda: False)
    monkeypatch.setattr(nautilus_step, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus_step, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus_step, "have", lambda cmd: cmd == "nautilus")
    monkeypatch.setattr(
        nautilus_step,
        "kw_write",
        lambda *args: kw_calls.append(tuple(args)) or True,
    )

    nautilus_step.install()

    # Two mime bindings → two kwriteconfig6 invocations against mimeapps.list.
    assert any(
        "--file" in args and "mimeapps.list" in args and
        "--key" in args and nautilus_step.MIME_FOLDER in args and
        nautilus_step.NAUTILUS_DESKTOP in args
        for args in kw_calls
    )
    assert any(
        "--file" in args and "mimeapps.list" in args and
        "--key" in args and nautilus_step.MIME_SEARCH in args and
        nautilus_step.NAUTILUS_DESKTOP in args
        for args in kw_calls
    )
