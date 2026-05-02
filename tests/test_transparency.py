# USELESS: SVG opacity values only — visual correctness on a real Plasma session is not validated
"""set-transparency / set-transparency end-to-end behaviour."""

import gzip
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def trans_fixture(tmp_path, repo, offline):
    """Sandboxed copy of the offline subdirs + src/scripts/ + entry script."""
    fx = tmp_path / "fx"
    (fx / "src/scripts").mkdir(parents=True)
    (fx / "src/offline").mkdir(parents=True)
    entry = repo / "src/scripts/set-transparency"
    target = fx / "src/scripts/set-transparency"
    shutil.copy2(entry, target)
    target.chmod(0o755)
    for sub in ("kvantum", "plasma-theme", "gtk"):
        shutil.copytree(offline / sub, fx / "src/offline" / sub)
    for item in (repo / "src/scripts").iterdir():
        if item.name not in ("__pycache__",):
            dst = fx / "src/scripts" / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
    (fx / "VERSION").write_text("0.0.0\n")
    return fx


def _svg_has(file: Path, opacity: str) -> bool:
    if not file.is_file():
        return False
    text = gzip.decompress(file.read_bytes()).decode("utf-8")
    return f"opacity:{opacity};fill" in text


def _run(fx, *args):
    rc = subprocess.run(
        [str(fx / "src/scripts/set-transparency"), *args],
        check=False, cwd=str(fx),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode
    assert rc == 0


@pytest.mark.parametrize("variant", ["MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark"])
def test_default_dock_stays_at_0_12(trans_fixture, variant):
    _run(trans_fixture, "50")
    panel = (trans_fixture / "src/offline/plasma-theme"
             / variant / "widgets/panel-background.svgz")
    assert _svg_has(panel, "0.12")
    assert not _svg_has(panel, "0.50")


@pytest.mark.parametrize("variant", ["MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark"])
def test_general_opacity_becomes_0_50(trans_fixture, variant):
    _run(trans_fixture, "50")
    bg = (trans_fixture / "src/offline/plasma-theme"
          / variant / "widgets/translucentbackground.svgz")
    assert _svg_has(bg, "0.50")


@pytest.mark.parametrize("variant", ["MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark"])
def test_dock_override(trans_fixture, variant):
    _run(trans_fixture, "50", "--dock", "15")
    panel = (trans_fixture / "src/offline/plasma-theme"
             / variant / "widgets/panel-background.svgz")
    bg = (trans_fixture / "src/offline/plasma-theme"
          / variant / "widgets/translucentbackground.svgz")
    assert _svg_has(panel, "0.15")
    assert _svg_has(bg, "0.50")
