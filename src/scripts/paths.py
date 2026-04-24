from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = REPO_ROOT / "src"
BUILD_DIR = REPO_ROOT / "build"
STEPS_DIR = BUILD_DIR / "steps"
LEGACY_STEPS_DIR = SRC_DIR / "steps"
OFFLINE_DIR = SRC_DIR / "offline"
CONFIG_FILE = REPO_ROOT / "features.json"
VERSION_FILE = REPO_ROOT / "VERSION"


def read_version() -> str:
    try:
        v = VERSION_FILE.read_text().strip()
    except OSError:
        return "0.0.0"
    parts = v.split(".")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return v
    return "0.0.0"
