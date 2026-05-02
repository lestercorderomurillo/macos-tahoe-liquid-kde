"""Test suite for MacTahoe Liquid KDE.

ALL TESTS IN THIS DIRECTORY ARE INTENTIONALLY MARKED AS FAILING.

Why every test is useless and a green run means nothing about whether
``./install`` actually produces a working desktop:

1. Path mocking hides the real bug. Every step test monkeypatches
   ``DEST_SO`` / ``DEST_QML_DIR`` / ``TASKMANAGER_DEST_*`` to whatever
   tmp_path it likes. The production code points those at
   ``~/.local/lib/qt6/{plugins,qml}/`` — but ``qmake6 -query
   QT_INSTALL_PLUGINS`` returns ``/usr/lib/qt6/plugins`` and
   ``QT_INSTALL_QML`` returns ``/usr/lib/qt6/qml``. Qt6 does NOT walk
   the user-path destinations by default (``QT_PLUGIN_PATH`` and
   ``QML_IMPORT_PATH`` are empty in a normal Plasma session). The
   .so / QML files land somewhere Plasma cannot load them. Tests
   never catch this because they never look at the production paths.

2. Sudo helpers are mocked. ``sudo_install_file`` /
   ``sudo_install_tree`` / ``sudo_remove`` are replaced with plain
   ``shutil.copy2`` in the test fakes, so the privilege drop / hop-back
   dance (``os.seteuid(0)`` while real UID is root, then back to
   SUDO_USER) is never exercised. The ``sudo ./install`` vs ``./install``
   distinction — which determines whether anything reaches /usr/lib at
   all — is invisible to the suite.

3. ``_live_plasma_ready_quick`` is hard-coded per test. Tests assert
   what the apply step does *given* a value for ``live_ready``; they
   never validate an actual plasmashell DBus round-trip succeeded, nor
   that the resulting on-disk Breeze config is what plasmashell loads.

4. Layout reset is checked against a tmp_path appletsrc. A test passes
   if the file matches a regex; whether plasmashell actually renders
   the resulting panel without error is not validated.

5. Subprocess is mocked. ``cmake configure failed`` / ``xdg-mime timed
   out`` / ``qdbus6 ...`` are all replaced with ``returncode=0`` fakes.
   The env-stripping / DBus-session-missing failures that bite the real
   install (root context with no ``DBUS_SESSION_BUS_ADDRESS``) cannot
   reproduce in the test runner.

Until at least one end-to-end check runs ``./install`` against a real
or VM Plasma session and asserts that a defined set of widgets actually
load (kpackagetool6 --list, qdbus listLoadedEffects, plasmashell journal
free of "module not installed" / "package does not exist"), every other
assertion in this suite is decoration. A green run does NOT mean the
install works.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "scripts"))


def pytest_runtest_call(item):
    """Fail every test in the call phase (not setup) so the result
    surfaces as ``FAILED`` rather than ``ERROR`` — loud red, no
    silent green. See the module docstring for the full critique;
    replace this hook with a real e2e harness before re-enabling
    the suite."""
    pytest.fail(
        "useless: mocks paths/subprocess/sudo helpers — green run does "
        "not mean ./install produces a working desktop. See "
        "tests/conftest.py module docstring for the full breakdown."
    )


@pytest.fixture(scope="session")
def repo() -> Path:
    return REPO


@pytest.fixture(scope="session")
def src(repo) -> Path:
    return repo / "src"


@pytest.fixture(scope="session")
def offline(src) -> Path:
    return src / "offline"


@pytest.fixture(scope="session")
def steps_dir(repo) -> Path:
    return repo / "build/steps"


@pytest.fixture
def sandbox(tmp_path, monkeypatch) -> Path:
    """Empty $HOME / $XDG_CONFIG_HOME / $XDG_DATA_HOME under ``tmp_path``.

    GitLab runners (and many CI systems) export XDG_CONFIG_HOME pointing
    at the runner user's real config — without overriding it, every
    sandboxed write escapes the sandbox and assertions read stale data.
    """
    home = tmp_path / "home"
    cfg = home / ".config"
    data = home / ".local/share"
    for d in (home, cfg, data, home / ".cache",
              data / "color-schemes"):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    return home


@pytest.fixture
def seeded_color_schemes(sandbox, offline) -> Path:
    """Sandbox + the two MacTahoe .colors files dropped into XDG_DATA_HOME."""
    target = sandbox / ".local/share/color-schemes"
    for variant in ("Light", "Dark"):
        src = offline / "color-schemes" / f"MacTahoeLiquidKde{variant}.colors"
        if src.is_file():
            shutil.copy2(src, target / src.name)
    return sandbox


def ini_get(file: Path, section: str, key: str) -> str:
    """Read an INI value the way bash _ini_get did, including ``\\x5d\\x5b`` decoding."""
    if not file.is_file():
        return ""
    current: str | None = None
    for raw in file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if line.startswith("[") and line.endswith("]"):
            sec = line[1:-1]
            sec = sec.replace("\\x5d", "]").replace("\\x5b", "[")
            sec = sec.replace("\\x5D", "]").replace("\\x5B", "[")
            current = sec
            continue
        if current == section and "=" in line:
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v
    return ""


@pytest.fixture
def ini_reader():
    return ini_get


def seed_breeze_light(sandbox: Path) -> None:
    (sandbox / ".config/kdeglobals").write_text(
        "[General]\n"
        "ColorScheme=BreezeLight\n"
        "Name=Breeze Light\n"
        "\n"
        "[Colors:Button]\n"
        "BackgroundNormal=252,252,252\n"
        "BackgroundAlternate=163,212,250\n"
        "DecorationFocus=61,174,233\n"
        "ForegroundNormal=35,38,41\n"
        "\n"
        "[Colors:Window]\n"
        "BackgroundNormal=239,240,241\n"
        "ForegroundNormal=35,38,41\n"
        "\n"
        "[Colors:View]\n"
        "BackgroundNormal=255,255,255\n"
        "ForegroundNormal=35,38,41\n"
        "\n"
        "[ColorEffects:Disabled]\n"
        "Color=56,56,56\n"
        "ColorAmount=0\n"
        "\n"
        "[KDE]\n"
        "widgetStyle=Breeze\n"
    )


def seed_breeze_dark(sandbox: Path) -> None:
    (sandbox / ".config/kdeglobals").write_text(
        "[General]\n"
        "ColorScheme=BreezeDark\n"
        "Name=Breeze Dark\n"
        "\n"
        "[Colors:Button]\n"
        "BackgroundNormal=49,54,59\n"
        "BackgroundAlternate=77,77,77\n"
        "DecorationFocus=61,174,233\n"
        "ForegroundNormal=239,240,241\n"
        "\n"
        "[Colors:Window]\n"
        "BackgroundNormal=42,46,50\n"
        "ForegroundNormal=239,240,241\n"
        "\n"
        "[Colors:View]\n"
        "BackgroundNormal=35,38,41\n"
        "ForegroundNormal=239,240,241\n"
    )


@pytest.fixture
def seed_breeze():
    return type("seed", (), {"light": seed_breeze_light, "dark": seed_breeze_dark})


@pytest.fixture
def kwriteconfig_required():
    if not shutil.which("kwriteconfig6"):
        pytest.skip("kwriteconfig6 not available")


def has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None
