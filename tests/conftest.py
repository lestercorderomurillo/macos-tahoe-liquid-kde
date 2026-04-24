import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "scripts"))


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
