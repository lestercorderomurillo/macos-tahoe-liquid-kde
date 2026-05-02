# USELESS: cmake configure-time check — green while the produced .so lands at a path Plasma will not load from
"""Configure + build the C++ plasmoids.

These tests run a full cmake configure + native compile per applet (~33s
combined on a modern laptop) and dominate the suite's wall-clock. They
are guaranteed to run on CI and any release-time invocation
(``MAC_TAHOE_RUN_SLOW=1 ./test``); local iteration skips them by default
to keep the loop tight."""

import os
import shutil
import subprocess

import pytest

from .conftest import has_command


pytestmark = [
    pytest.mark.skipif(
        not has_command("cmake"),
        reason="cmake not installed — skipping native build tests",
    ),
    pytest.mark.skipif(
        not os.environ.get("MAC_TAHOE_RUN_SLOW")
        and not os.environ.get("CI"),
        reason="slow C++ build — set MAC_TAHOE_RUN_SLOW=1 (or CI=1) to opt in",
    ),
]


_APPLETS = (
    ("plasmoids/org.kde.mac.tahoe.liquid.globalmenu",
     "org.kde.mac.tahoe.liquid.globalmenu_qmllint"),
    ("plasmoids/org.kde.mac.tahoe.liquid.taskmanager",
     "org.kde.mac.tahoe.liquid.taskmanager_qmllint"),
)


@pytest.mark.parametrize("rel,qml_target", _APPLETS)
def test_applet_builds(offline, tmp_path, rel, qml_target):
    src = offline / rel
    build = tmp_path / "build"
    rc = subprocess.run(
        ["cmake", "-S", str(src), "-B", str(build),
         "-DCMAKE_BUILD_TYPE=Release"],
        check=False,
    ).returncode
    assert rc == 0, f"cmake configure failed for {src.name}"

    rc = subprocess.run(
        ["cmake", "--build", str(build)], check=False,
    ).returncode
    assert rc == 0, f"build failed for {src.name}"

    assert any(build.rglob("*.so")), f"no .so produced under {build}"

    rc = subprocess.run(
        ["cmake", "--build", str(build), "--target", qml_target],
        check=False,
    ).returncode
    assert rc == 0, f"qmllint failed for {src.name}"
