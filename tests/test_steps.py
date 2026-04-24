"""Sandboxed install/uninstall behaviour for individual step modules."""

import os
import subprocess
from pathlib import Path

import pytest

from .conftest import has_command


def _run(step: str, phase: str, env: dict[str, str] | None = None) -> int:
    full = os.environ.copy()
    if env:
        full.update(env)
    return subprocess.run(
        ["python3", "-c",
         f"from steps.{step} import {phase}; {phase}()"],
        check=False, env=full,
        cwd=str(Path(__file__).resolve().parent.parent / "src/scripts"),
    ).returncode


# ── color schemes ────────────────────────────────────────────────────────
def test_color_schemes_install_uninstall_cycle(sandbox):
    css_dir = sandbox / ".local/share/color-schemes"

    assert _run("color_schemes", "install") == 0
    assert (css_dir / "MacTahoeLiquidKdeLight.colors").is_file()
    assert (css_dir / "MacTahoeLiquidKdeDark.colors").is_file()

    assert _run("color_schemes", "uninstall") == 0
    assert not (css_dir / "MacTahoeLiquidKdeLight.colors").exists()
    assert not (css_dir / "MacTahoeLiquidKdeDark.colors").exists()

    assert _run("color_schemes", "install") == 0
    assert (css_dir / "MacTahoeLiquidKdeLight.colors").is_file()

    # Double install / uninstall must not error.
    assert _run("color_schemes", "install") == 0
    assert _run("color_schemes", "uninstall") == 0
    assert _run("color_schemes", "uninstall") == 0


@pytest.mark.parametrize("iteration", [1, 2, 3])
def test_color_schemes_loop(sandbox, iteration):
    assert _run("color_schemes", "install") == 0
    assert (sandbox / ".local/share/color-schemes/MacTahoeLiquidKdeDark.colors").is_file()
    assert _run("color_schemes", "uninstall") == 0
    assert not (sandbox / ".local/share/color-schemes/MacTahoeLiquidKdeDark.colors").exists()


# ── nautilus ─────────────────────────────────────────────────────────────
def test_nautilus_no_fatal(sandbox, monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    (sandbox / ".config/gtk-3.0").mkdir(parents=True, exist_ok=True)
    rc = _run("nautilus", "install", {"XDG_CURRENT_DESKTOP": "KDE"})
    assert rc == 0
    rc = _run("nautilus", "uninstall", {"XDG_CURRENT_DESKTOP": "KDE"})
    assert rc == 0


# ── crash / regression guards ────────────────────────────────────────────
def test_no_globalmenu_crashes_in_journal():
    if not has_command("journalctl"):
        pytest.skip("journalctl unavailable")
    res = subprocess.run(
        ["journalctl", "--user", "-p", "err",
         "--since", "24 hours ago", "--no-pager"],
        check=False, capture_output=True, text=True,
    )
    import re
    bad = re.compile(
        r"(org\.kde\.mac\.tahoe\.liquid\.(globalmenu|menu))\.so.*"
        r"(segfault|coredump|terminated|aborted)",
        re.IGNORECASE,
    )
    matches = [l for l in res.stdout.splitlines() if bad.search(l)]
    assert not matches, "\n".join(matches[:5])
