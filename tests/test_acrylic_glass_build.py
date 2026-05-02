# USELESS: end-to-end cmake build, but the resulting .so ships to a path Qt6/KWin does not walk — green means nothing
"""End-to-end build test for the Acrylic Glass KWin effect.

Runs `cmake -S <effect> -B <tmp> && cmake --build <tmp>` and asserts that
both the effect .so (liquidglass.so) and the KCM .so
(kwin_liquidglass_config.so) are produced. Skips cleanly when KF6 / KWin
development packages aren't available on the test host (CI runners
without a full KDE stack).
"""

import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    shutil.which("cmake") is None,
    reason="cmake not installed",
)


@pytest.fixture(scope="module")
def effect_root(repo) -> Path:
    return repo / "src/offline/kwin-effects/acrylic-glass"


def _can_configure(effect_root: Path, build_dir: Path) -> bool:
    """Probe whether KF6/KWin headers are reachable on this host."""
    res = subprocess.run(
        ["cmake", "-S", str(effect_root), "-B", str(build_dir)],
        check=False, capture_output=True, text=True,
    )
    return res.returncode == 0


def test_acrylic_glass_builds(effect_root, tmp_path):
    build_dir = tmp_path / "build"
    if not _can_configure(effect_root, build_dir):
        pytest.skip("KF6 / KWin / KDecoration3 dev headers not available")

    res = subprocess.run(
        ["cmake", "--build", str(build_dir), "--parallel"],
        check=False, capture_output=True, text=True,
    )
    assert res.returncode == 0, (
        "cmake build failed. Last 40 lines of output:\n"
        + "\n".join((res.stdout + res.stderr).splitlines()[-40:])
    )

    effect_so = build_dir / "src/liquidglass.so"
    kcm_so = build_dir / "src/kcm/kwin_liquidglass_config.so"
    assert effect_so.is_file(), f"{effect_so} was not produced"
    assert kcm_so.is_file(), f"{kcm_so} was not produced"
