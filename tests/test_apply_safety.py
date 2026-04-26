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

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(tuple(cmd))
        return _result()

    monkeypatch.setattr(apply.subprocess, "run", fake_run)

    apply.install()

    assert "flush" in markers
    assert (str(switch), "dark", "install") in subprocess_calls
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
        },
    )

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(tuple(cmd))
        return _result()

    monkeypatch.setattr(apply.subprocess, "run", fake_run)

    apply.uninstall()

    assert "scrub" in markers
    assert "flush" in markers
    assert ("scheme", "BreezeLight") in markers
    assert ("laf", "org.kde.breeze.desktop") in live_calls
    assert ("cursor", "breeze_cursors") in live_calls
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


def test_nautilus_install_does_not_force_quit(monkeypatch):
    subprocess_calls = []
    popen_calls = []
    warnings = []
    running = {"value": True}

    monkeypatch.setattr(nautilus_step, "_is_kde", lambda: True)
    monkeypatch.setattr(nautilus_step, "_apply_overrides", lambda: None)
    monkeypatch.setattr(nautilus_step, "_apply_gsettings", lambda: None)
    monkeypatch.setattr(nautilus_step, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus_step, "warn", lambda msg: warnings.append(msg))
    monkeypatch.setattr(nautilus_step.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(
        nautilus_step,
        "have",
        lambda cmd: cmd in {"nautilus", "xdg-mime", "gdbus", "gapplication"},
    )

    def fake_run(cmd, **_kwargs):
        subprocess_calls.append(tuple(cmd))
        if cmd[:2] == ["pgrep", "-x"]:
            return _result(0 if running["value"] else 1)
        if cmd[:2] == ["gdbus", "call"]:
            running["value"] = False
        return _result(0)

    monkeypatch.setattr(nautilus_step.subprocess, "run", fake_run)
    monkeypatch.setattr(
        nautilus_step.subprocess,
        "Popen",
        lambda cmd, **_kwargs: popen_calls.append(tuple(cmd)) or _result(),
    )

    nautilus_step.install()

    assert ("xdg-mime", "default", nautilus_step.NAUTILUS_DESKTOP, nautilus_step.MIME_FOLDER) in subprocess_calls
    assert any(cmd[:2] == ("gdbus", "call") for cmd in subprocess_calls)
    assert ("gapplication", "launch", "org.gnome.Nautilus") in popen_calls
    assert not any(cmd[:2] == ("nautilus", "-q") for cmd in subprocess_calls)
    assert not warnings
