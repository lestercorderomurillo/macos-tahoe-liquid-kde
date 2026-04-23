import re
import shutil
import subprocess
from pathlib import Path

from installer.steps._helpers import (
    HOME, fail, info, install_tree, ok, src_dir, steps_dir, temp_dir,
)
from installer.utils import run_mirrors

CACHE = steps_dir("icons")
DEST_DIR = HOME / ".local/share/icons"
MIRROR_FILE = src_dir("mirrors/icons.json")

# Subdirs copied from the upstream repo into the default theme.
_DEFAULT_DIRS = (
    "actions", "animations", "apps", "categories", "devices", "emotes",
    "emblems", "mimes", "places", "preferences",
)
# Status sizes that exist in the default theme (24 in dark too).
_DEFAULT_STATUS_SIZES = ("16", "22", "24", "32", "symbolic")
# Subdirs that get a "@2x" symlink for HiDPI.
_AT2X_DIRS = (*_DEFAULT_DIRS, "status")


def deps():
    return ["curl", "unzip"]


def _copy_subset(repo: Path, dest: Path, subdirs) -> None:
    for sub in subdirs:
        src = repo / sub
        if src.is_dir():
            target = dest / sub.split("/", 1)[0] if "/" in sub else dest / src.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if "/" in sub:
                # nested path like "src/status/16"
                pass
            shutil.copytree(src, dest / Path(sub).name, dirs_exist_ok=True)


def _assemble(repo: Path, name: str) -> None:
    light = CACHE / name
    light.mkdir(parents=True, exist_ok=True)

    index = repo / "src/index.theme"
    if index.is_file():
        text = index.read_text().replace("MacTahoe", name)
        (light / "index.theme").write_text(text)

    src_root = repo / "src"
    for sub in _DEFAULT_DIRS:
        if (src_root / sub).is_dir():
            shutil.copytree(src_root / sub, light / sub, dirs_exist_ok=True)
    (light / "status").mkdir(exist_ok=True)
    for sz in _DEFAULT_STATUS_SIZES:
        d = src_root / "status" / sz
        if d.is_dir():
            shutil.copytree(d, light / "status" / sz, dirs_exist_ok=True)

    links_root = repo / "links"
    for sub in (*_DEFAULT_DIRS, "status"):
        if (links_root / sub).is_dir():
            shutil.copytree(links_root / sub, light / sub, dirs_exist_ok=True)

    for fn in ("user-trash-dark.svg", "user-trash-full-dark.svg"):
        try: (light / "places/scalable" / fn).unlink()
        except FileNotFoundError: pass
        except OSError: pass

    for sub in _AT2X_DIRS:
        target = light / sub
        if target.is_dir():
            link = light / f"{sub}@2x"
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(sub)

    # Dark variant.
    dark = CACHE / f"{name}-dark"
    dark.mkdir(parents=True, exist_ok=True)
    if index.is_file():
        text = index.read_text().replace("MacTahoe", f"{name}-dark")
        text = re.sub(r"^Inherits=.*",
                      f"Inherits={name},hicolor,breeze",
                      text, flags=re.MULTILINE)
        (dark / "index.theme").write_text(text)

    for sub in ("actions", "apps", "categories", "emblems", "devices",
                "mimes", "places", "status"):
        (dark / sub).mkdir(parents=True, exist_ok=True)

    shutil.copytree(src_root / "actions", dark / "actions", dirs_exist_ok=True)
    for size in ("16", "22", "32", "symbolic"):
        if (src_root / "apps" / size).is_dir():
            shutil.copytree(src_root / "apps" / size,
                            dark / "apps" / size, dirs_exist_ok=True)
    for size in ("22", "symbolic"):
        if (src_root / "categories" / size).is_dir():
            shutil.copytree(src_root / "categories" / size,
                            dark / "categories" / size, dirs_exist_ok=True)
    if (src_root / "emblems/symbolic").is_dir():
        shutil.copytree(src_root / "emblems/symbolic",
                        dark / "emblems/symbolic", dirs_exist_ok=True)
    if (src_root / "mimes/symbolic").is_dir():
        shutil.copytree(src_root / "mimes/symbolic",
                        dark / "mimes/symbolic", dirs_exist_ok=True)
    for size in ("16", "22", "24", "32", "symbolic"):
        if (src_root / "devices" / size).is_dir():
            shutil.copytree(src_root / "devices" / size,
                            dark / "devices" / size, dirs_exist_ok=True)
    for size in ("16", "22", "24", "scalable", "symbolic"):
        if (src_root / "places" / size).is_dir():
            shutil.copytree(src_root / "places" / size,
                            dark / "places" / size, dirs_exist_ok=True)
    if (src_root / "status/symbolic").is_dir():
        shutil.copytree(src_root / "status/symbolic",
                        dark / "status/symbolic", dirs_exist_ok=True)

    # Recolour symbolic SVGs from #363636 → #dedede.
    for svg in dark.rglob("*.svg"):
        try:
            text = svg.read_text(encoding="utf-8")
            if "#363636" in text:
                svg.write_text(text.replace("#363636", "#dedede"))
        except (OSError, UnicodeDecodeError):
            pass

    for old, new in (("user-trash-dark.svg", "user-trash.svg"),
                     ("user-trash-full-dark.svg", "user-trash-full.svg")):
        src_p = dark / "places/scalable" / old
        if src_p.is_file():
            shutil.move(str(src_p), str(dark / "places/scalable" / new))

    for sub in ("actions/16", "actions/22", "actions/24", "actions/32", "actions/symbolic",
                "devices/16", "devices/22", "devices/24", "devices/32", "devices/symbolic",
                "places/16", "places/22", "places/24", "places/scalable", "places/symbolic",
                "apps/16", "apps/22", "apps/32", "apps/symbolic",
                "categories/22", "categories/symbolic",
                "mimes/symbolic", "status/symbolic"):
        link_src = links_root / sub
        if link_src.is_dir():
            shutil.copytree(link_src, dark / sub, dirs_exist_ok=True)

    # @2x and cross-theme links.
    for sub, target in (
        ("animations", f"../{name}/animations"),
        ("emotes", f"../{name}/emotes"),
        ("preferences", f"../{name}/preferences"),
        ("categories/32", f"../../{name}/categories/32"),
        ("apps/scalable", f"../../{name}/apps/scalable"),
        ("devices/scalable", f"../../{name}/devices/scalable"),
    ):
        link = dark / sub
        if link.is_symlink() or link.exists():
            try: link.unlink()
            except OSError:
                shutil.rmtree(link, ignore_errors=True)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)

    for sz in ("16", "22", "24", "32"):
        link = dark / f"status/{sz}"
        if link.is_symlink() or link.exists():
            try: link.unlink()
            except OSError: shutil.rmtree(link, ignore_errors=True)
        link.symlink_to(f"../../{name}/status/{sz}")
    for sz in ("16", "22", "24"):
        link = dark / f"emblems/{sz}"
        if link.is_symlink() or link.exists():
            try: link.unlink()
            except OSError: shutil.rmtree(link, ignore_errors=True)
        link.symlink_to(f"../../{name}/emblems/{sz}")
    for sz in ("16", "22", "scalable"):
        link = dark / f"mimes/{sz}"
        if link.is_symlink() or link.exists():
            try: link.unlink()
            except OSError: shutil.rmtree(link, ignore_errors=True)
        link.symlink_to(f"../../{name}/mimes/{sz}")

    for sub in _AT2X_DIRS:
        target = dark / sub
        if target.is_dir():
            link = dark / f"{sub}@2x"
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(sub)


def download() -> None:
    for d in CACHE.glob("MacTahoeLiquidKde-Icons*"):
        shutil.rmtree(d, ignore_errors=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    with temp_dir("tahoe-icons") as tmp:
        any_ok = False

        def handle(xdir, prefix, *_referer):
            srcdir = next((p.parent for p in xdir.rglob("src") if p.is_dir()), None)
            if srcdir is None or not (srcdir / "links").is_dir():
                return False
            _assemble(srcdir, prefix)
            return True

        if run_mirrors(MIRROR_FILE, 0, tmp, handle):
            any_ok = True

        if not any_ok:
            fail("no icon themes installed — all mirrors failed")


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for theme in sorted(CACHE.glob("Mac*")):
        if not theme.is_dir():
            continue
        if not (theme / "index.theme").is_file():
            fail(f"{theme.name} (no index.theme — skipping)")
            continue
        if install_tree(theme, DEST_DIR / theme.name):
            n += 1

    dark_idx = DEST_DIR / "MacTahoeLiquidKde-Icons-dark/index.theme"
    if dark_idx.is_file():
        text = dark_idx.read_text()
        if "Inherits=MacTahoeLiquidKde-Icons," not in text:
            text = re.sub(r"^Inherits=.*",
                          "Inherits=MacTahoeLiquidKde-Icons,hicolor,breeze",
                          text, flags=re.MULTILINE)
            dark_idx.write_text(text)

    if shutil.which("gtk-update-icon-cache"):
        for theme in DEST_DIR.glob("MacTahoeLiquidKde-Icons*"):
            if theme.is_dir():
                subprocess.run(
                    ["gtk-update-icon-cache", "-f", "-t", str(theme)],
                    check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

    label = "icon theme" if n == 1 else "icon themes"
    info(f"{n} {label} installed/reinstalled")


def uninstall() -> None:
    n = 0
    for theme in DEST_DIR.glob("MacTahoeLiquidKde-Icons*"):
        if theme.is_dir():
            try:
                shutil.rmtree(theme)
                ok(theme.name); n += 1
            except OSError:
                fail(theme.name)
    info(f"{n} icon themes removed")
