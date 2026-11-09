"""The opt-in rendering probe must not target the user's compositor."""

from types import SimpleNamespace

import pytest

from tests import acrylic_glass_capture as capture


@pytest.mark.parametrize("key", ["HOME", "XDG_CONFIG_HOME", "MTTKDE_CAPTURE_DIR"])
def test_direct_capture_entry_refuses_non_private_environment(monkeypatch, tmp_path, key):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("MTTKDE_CAPTURE_DIR", str(tmp_path))
    monkeypatch.delenv(key)

    def forbidden(*args, **kwargs):
        raise AssertionError("No processes may start with a non-private environment")

    monkeypatch.setattr(capture.subprocess, "Popen", forbidden)
    with pytest.raises(RuntimeError, match="private session"):
        capture.inside(tmp_path)


def test_capture_refuses_a_different_dbus_owner(monkeypatch):
    calls = []

    def query(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="999\n")

    monkeypatch.setattr(capture.subprocess, "run", query)
    with pytest.raises(RuntimeError, match="refusing mutations"):
        capture.assert_compositor_owner(123)
    assert len(calls) == 1
    assert "org.freedesktop.DBus.GetConnectionUnixProcessID" in calls[0]


@pytest.mark.parametrize("options", [dict(scale=1.5), dict(screenshot_api="dbus")])
def test_x11_probe_rejects_unsupported_capture_modes_before_starting(tmp_path, options):
    output = tmp_path / "capture"
    arguments = dict(plugin=tmp_path / "effect.so", output=output, scale=1,
                     expected="changed", backend="xcb", identity="test",
                     compositor="x11") | options
    with pytest.raises(AssertionError):
        capture.run(**arguments)
    assert not output.exists()
