import shutil

from steps._helpers import (
    HOME, fail, info, install_tree, ok, src_dir, steps_dir, temp_dir,
)
from utils import load_mirrors, run_mirrors

CACHE = steps_dir("cursors")
DEST_DIR = HOME / ".local/share/icons"


def deps():
    return ["curl", "unzip"]


def _classify(raw: str, prefix: str) -> str | None:
    lower = raw.lower()
    if "white" in lower:
        return f"{prefix}-White"
    if "dark" in lower or lower.endswith("-dark"):
        return f"{prefix}-Dark"
    if raw in ("dist", "macOS", "macos", "MacOS"):
        return prefix
    if raw.endswith(("-main", "-master")):
        return None
    return f"{prefix}-{raw}"


def download() -> None:
    mirror = src_dir("mirrors/cursors.json")
    for d in CACHE.glob("MacTahoeLiquidKde*"):
        shutil.rmtree(d, ignore_errors=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    any_ok = False
    with temp_dir("tahoe-cursors") as tmp:
        def handle(xdir, prefix, *_referer):
            installed = False
            for d in sorted(xdir.glob("**/")):
                if d == xdir:
                    continue
                if not (d / "cursors").is_dir() or not (d / "index.theme").is_file():
                    continue
                if not any((d / "cursors").iterdir()):
                    continue
                name = _classify(d.name, prefix)
                if not name:
                    continue
                target = CACHE / name
                shutil.rmtree(target, ignore_errors=True)
                try:
                    shutil.copytree(d, target)
                    installed = True
                except OSError:
                    fail(f"{name} (copy failed)")
            return installed

        for s in range(len(_sources(mirror))):
            if run_mirrors(mirror, s, tmp, handle):
                any_ok = True

    if not any_ok:
        fail("no cursor themes installed — all mirrors failed")


def _sources(mirror_file):
    import json
    return json.loads(mirror_file.read_text())["sources"]


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for theme in sorted(CACHE.glob("Mac*")):
        if not theme.is_dir():
            continue
        if not (theme / "cursors").is_dir():
            fail(f"{theme.name} (no cursors/ dir — skipping)")
            continue
        if install_tree(theme, DEST_DIR / theme.name):
            n += 1
    info(f"{n} cursor themes installed/reinstalled")


def uninstall() -> None:
    n = 0
    for theme in DEST_DIR.glob("MacTahoeLiquidKde*"):
        if not theme.is_dir() or "Icons" in theme.name:
            continue
        try:
            shutil.rmtree(theme)
            ok(theme.name)
            n += 1
        except OSError:
            fail(theme.name)
    info(f"{n} cursor themes removed")
