from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
STEPS_DIR = SRC_DIR / "steps"
OFFLINE_DIR = SRC_DIR / "offline"
BUILD_DIR = REPO_ROOT / "build"
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
