"""MacTahoe icon themes: extracts the pre-built
MacTahoeLiquidKde-Icons.tar.zst into ~/.local/share/icons. The tarball is
rebuilt offline via _assemble() (maintainer refresh workflow, see below)."""

import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from steps._helpers import (
    HOME, fail, info, install_tree, offline, ok,
)
from utils import remove_path, run_user

OFFLINE_DIR = offline("icons")
DEST_DIR = HOME / ".local/share/icons"

# Subdirs _assemble() cherry-picks from upstream into the default theme.
_DEFAULT_DIRS = (
    "actions", "animations", "apps", "categories", "devices", "emotes",
    "emblems", "mimes", "places", "preferences",
)
_DEFAULT_STATUS_SIZES = ("16", "22", "24", "32", "symbolic")
_AT2X_DIRS = (*_DEFAULT_DIRS, "status")


def deps():
    return ["zstd"]


def install() -> None:
    """Extract the pre-built MacTahoeLiquidKde-Icons tarball into
    ~/.local/share/icons, then rebuild GTK icon caches."""
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    tarball = OFFLINE_DIR / "MacTahoeLiquidKde-Icons.tar.zst"
    if not tarball.is_file():
        fail(f"offline tarball missing: {tarball}")
        return

    # Wipe our own stale theme dirs (crashed-run leftovers); never touch
    # the user's other themes (Breeze, Adwaita, etc.).
    for old in DEST_DIR.glob("MacTahoeLiquidKde-Icons*"):
        if old.is_dir():
            shutil.rmtree(old, ignore_errors=True)

    # tar --zstd over Python tarfile: the zstandard module isn't in every
    # distro's default Python.
    res = subprocess.run(
        ["tar", "--zstd", "-xf", str(tarball), "-C", str(DEST_DIR)],
        check=False, capture_output=True, text=True,
    )
    if res.returncode != 0:
        fail(f"tar --zstd failed ({res.returncode}): {res.stderr.strip()}")
        return

    n = 0
    for theme in sorted(DEST_DIR.glob("MacTahoeLiquidKde-Icons*")):
        if theme.is_dir() and (theme / "index.theme").is_file():
            ok(f"{theme.name} (installed)")
            n += 1

    if shutil.which("gtk-update-icon-cache"):
        for theme in DEST_DIR.glob("MacTahoeLiquidKde-Icons*"):
            if theme.is_dir():
                run_user(
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


# ─────────────────────────────────────────────────────────────────────
# REFRESH WORKFLOW — maintainer-only: rebuilds the bundled tarball after
# an upstream theme update. Not called at install time.
# ─────────────────────────────────────────────────────────────────────


def _overlay_links(src: Path, dest: Path) -> None:
    for entry in src.iterdir():
        target = dest / entry.name
        if entry.is_symlink():
            remove_path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(entry.readlink())
            continue
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            _overlay_links(entry, target)
            continue
        remove_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target)


def _assemble(repo: Path, name: str) -> None:
    """Build ``CACHE/<name>`` + ``CACHE/<name>-dark`` from an upstream
    vinceliuice/MacTahoe-icon-theme clone; override CACHE, then tar --zstd
    the result into src/offline/icons/. Never runs at install time."""
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
            _overlay_links(links_root / sub, light / sub)

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

    # Dark variant
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
            _overlay_links(link_src, dark / sub)

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


# Only _assemble() uses this; the maintainer refresh script overrides it.
CACHE = Path("/tmp/mttkde-icons-build")
