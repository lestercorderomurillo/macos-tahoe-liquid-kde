import io
import tarfile
from types import SimpleNamespace

from steps import layout


def test_has_panel_colorizer_checks_user_and_system_paths(monkeypatch, tmp_path):
    user_home = tmp_path / "home"
    user_dir = user_home / ".local/share/plasma/plasmoids" / layout.COLORIZER_ID
    system_dir = tmp_path / "usr/share/plasma/plasmoids" / layout.COLORIZER_ID

    monkeypatch.setattr(layout, "HOME", user_home)
    monkeypatch.setattr(
        layout,
        "_colorizer_dirs",
        lambda: [user_dir, system_dir],
    )

    assert layout._has_panel_colorizer() is False

    system_dir.mkdir(parents=True, exist_ok=True)
    (system_dir / "metadata.json").write_text("{}\n")
    assert layout._has_panel_colorizer() is True


def test_install_panel_colorizer_from_release_copies_package(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setattr(layout, "HOME", home)

    blob = io.BytesIO()
    with tarfile.open(fileobj=blob, mode="w:gz") as tf:
        metadata = b'{"KPlugin":{"Id":"luisbocanegra.panel.colorizer"}}\n'
        info = tarfile.TarInfo(
            "plasma-panel-colorizer-7.0.1/package/metadata.json"
        )
        info.size = len(metadata)
        tf.addfile(info, io.BytesIO(metadata))

        ui = b"import QtQuick\nItem {}\n"
        info = tarfile.TarInfo(
            "plasma-panel-colorizer-7.0.1/package/contents/ui/main.qml"
        )
        info.size = len(ui)
        tf.addfile(info, io.BytesIO(ui))

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return blob.getvalue()

    monkeypatch.setattr(
        layout.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResp(),
    )

    assert layout._install_panel_colorizer_from_release() is True
    assert (
        home / ".local/share/plasma/plasmoids"
        / layout.COLORIZER_ID / "metadata.json"
    ).is_file()
    assert (
        home / ".local/share/plasma/plasmoids"
        / layout.COLORIZER_ID / "contents/ui/main.qml"
    ).is_file()


def test_evaluate_layout_retries_via_bounded_qdbus(monkeypatch, tmp_path):
    script = tmp_path / "layout.js"
    script.write_text("print('ok');")

    calls = []
    sleeps = []
    outcomes = iter([False, False, True])

    monkeypatch.setattr(layout, "qdbus_cmd", lambda: "qdbus6")
    monkeypatch.setattr(
        layout,
        "qdbus_call",
        lambda *args: calls.append(args) or next(outcomes),
    )
    monkeypatch.setattr(layout.time, "sleep", sleeps.append)

    assert layout._evaluate_layout(script) is True
    assert len(calls) == 3
    assert calls[0][:3] == (
        "org.kde.plasmashell",
        "/PlasmaShell",
        "org.kde.PlasmaShell.evaluateScript",
    )
    assert calls[0][3] == "print('ok');"
    assert sleeps == [3, 3]


def test_evaluate_layout_warns_without_qdbus(monkeypatch, tmp_path):
    script = tmp_path / "layout.js"
    script.write_text("print('ok');")

    warnings = []
    monkeypatch.setattr(layout, "qdbus_cmd", lambda: None)
    monkeypatch.setattr(layout, "warn", warnings.append)

    assert layout._evaluate_layout(script) is False
    assert warnings == ["qdbus not found — layout not installed"]


def test_reset_layout_builtin_applies_breeze_and_rejects_help_output(monkeypatch):
    calls = []

    monkeypatch.setattr(layout, "have", lambda cmd: cmd == "plasma-apply-lookandfeel")

    def fake_run(cmd, **kwargs):
        calls.append((tuple(cmd), kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout="Usage: plasma-apply-lookandfeel [options]\n",
            stderr="",
        )

    monkeypatch.setattr(layout.subprocess, "run", fake_run)

    assert layout._reset_layout_builtin() is False
    assert calls == [(
        (
            "plasma-apply-lookandfeel",
            "-a",
            "org.kde.breeze.desktop",
            "--resetLayout",
        ),
        {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 20,
        },
    )]


def test_reset_layout_builtin_succeeds_on_real_completion(monkeypatch):
    monkeypatch.setattr(layout, "have", lambda cmd: cmd == "plasma-apply-lookandfeel")
    monkeypatch.setattr(
        layout.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    assert layout._reset_layout_builtin() is True


def test_layout_looks_reset_detects_default_panel_and_no_custom_widgets(monkeypatch, tmp_path):
    home = tmp_path / "home"
    appletsrc = home / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    appletsrc.parent.mkdir(parents=True, exist_ok=True)
    appletsrc.write_text(
        "\n".join((
            "[Containments][1]",
            "location=4",
            "plugin=org.kde.panel",
            "plugin=org.kde.plasma.kickoff",
            "plugin=org.kde.plasma.pager",
            "plugin=org.kde.plasma.icontasks",
            "plugin=org.kde.plasma.systemtray",
            "plugin=org.kde.plasma.digitalclock",
            "plugin=org.kde.plasma.showdesktop",
        ))
    )

    monkeypatch.setattr(layout, "HOME", home)

    assert layout._layout_looks_reset() is True


def test_layout_looks_reset_rejects_custom_mactahoe_widgets(monkeypatch, tmp_path):
    home = tmp_path / "home"
    appletsrc = home / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    appletsrc.parent.mkdir(parents=True, exist_ok=True)
    appletsrc.write_text(
        "\n".join((
            "plugin=org.kde.plasma.kickoff",
            "plugin=org.kde.plasma.pager",
            "plugin=org.kde.plasma.icontasks",
            "plugin=org.kde.plasma.systemtray",
            "plugin=org.kde.plasma.digitalclock",
            "plugin=org.kde.plasma.showdesktop",
            "plugin=org.kde.mac.tahoe.liquid.globalmenu",
        ))
    )

    monkeypatch.setattr(layout, "HOME", home)

    assert layout._layout_looks_reset() is False


def test_uninstall_prefers_builtin_layout_reset(monkeypatch, tmp_path):
    script = tmp_path / "default.js"
    script.write_text("print('reset');")

    oks = []
    warnings = []

    monkeypatch.setattr(layout, "LAYOUT_RESET", script)
    monkeypatch.setattr(layout, "_layout_looks_reset", lambda: False)
    monkeypatch.setattr(layout, "_reset_layout_builtin", lambda: True)
    monkeypatch.setattr(
        layout,
        "_evaluate_layout",
        lambda _script: (_ for _ in ()).throw(AssertionError("unexpected fallback")),
    )
    monkeypatch.setattr(layout, "ok", oks.append)
    monkeypatch.setattr(layout, "warn", warnings.append)

    layout.uninstall()

    assert oks == ["Layout reset"]
    assert warnings == []


def test_uninstall_falls_back_to_script_reset(monkeypatch, tmp_path):
    script = tmp_path / "default.js"
    script.write_text("print('reset');")

    oks = []
    warnings = []
    calls = []

    monkeypatch.setattr(layout, "LAYOUT_RESET", script)
    monkeypatch.setattr(layout, "_layout_looks_reset", lambda: False)
    monkeypatch.setattr(layout, "_reset_layout_builtin", lambda: False)
    monkeypatch.setattr(
        layout,
        "_evaluate_layout",
        lambda path: calls.append(path) or True,
    )
    monkeypatch.setattr(layout, "ok", oks.append)
    monkeypatch.setattr(layout, "warn", warnings.append)

    layout.uninstall()

    assert calls == [script]
    assert oks == ["Layout reset"]
    assert warnings == []


def test_uninstall_warns_when_builtin_and_script_reset_fail(monkeypatch, tmp_path):
    script = tmp_path / "default.js"
    script.write_text("print('reset');")

    oks = []
    warnings = []

    monkeypatch.setattr(layout, "LAYOUT_RESET", script)
    monkeypatch.setattr(layout, "_layout_looks_reset", lambda: False)
    monkeypatch.setattr(layout, "_reset_layout_builtin", lambda: False)
    monkeypatch.setattr(layout, "_evaluate_layout", lambda _path: False)
    monkeypatch.setattr(layout, "ok", oks.append)
    monkeypatch.setattr(layout, "warn", warnings.append)

    layout.uninstall()

    assert oks == []
    assert warnings == ["layout reset failed"]


def test_uninstall_accepts_on_disk_default_layout_after_failed_live_reset(monkeypatch, tmp_path):
    script = tmp_path / "default.js"
    script.write_text("print('reset');")

    oks = []
    warnings = []
    states = iter([False, True])

    monkeypatch.setattr(layout, "LAYOUT_RESET", script)
    monkeypatch.setattr(layout, "_layout_looks_reset", lambda: next(states))
    monkeypatch.setattr(layout, "_reset_layout_builtin", lambda: False)
    monkeypatch.setattr(layout, "_evaluate_layout", lambda _path: False)
    monkeypatch.setattr(layout, "ok", oks.append)
    monkeypatch.setattr(layout, "warn", warnings.append)

    layout.uninstall()

    assert oks == ["Layout reset"]
    assert warnings == []
