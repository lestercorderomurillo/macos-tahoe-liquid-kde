"""Set background transparency across Kvantum, Plasma SVGs, and GTK CSS.

This is a dev/tuning helper, not part of the install flow. Touches only
opacity / alpha; never buttons, text, shadows, or highlight colours.
"""

import gzip
import re
import shutil
import subprocess
import sys
from pathlib import Path

from installer import OFFLINE_DIR, REPO_ROOT


KVANTUM_DIR = OFFLINE_DIR / "kvantum/mac-tahoe-liquid-kde"
PLASMA_DIR = OFFLINE_DIR / "plasma-theme"
GTK_DIR = OFFLINE_DIR / "gtk"
VARIANTS = ("MacTahoeLiquidKde-Dark", "MacTahoeLiquidKde-Light")

DEFAULT_DOCK_PCT = 12

USAGE = """\
Usage: src/scripts/set-transparency <percent> [--dock <percent>] [--apply]
       python3 -m installer transparency <percent> [...]

  <percent>          Background opacity 0–100 (e.g. 60 = 60% opaque)
  --dock <percent>   Separate opacity for the dock panel (default: 12)
  --apply            Install to live system and restart plasmashell

Examples:
  src/scripts/set-transparency 60                # everything at 60%
  src/scripts/set-transparency 75 --dock 15      # 75% general, 15% dock
  src/scripts/set-transparency 75 --apply        # same + install live, dock stays at 12%
"""


def _to_svg(p: int) -> str:
    if p == 100:
        return "1"
    if p < 10:
        return f"0.0{p}"
    return f"0.{p:02d}"


# Kvantum colour keys whose alpha byte we rewrite.
_KVANTUM_KEYS = (
    "window.color", "inactive.window.color",
    "base.color", "inactive.base.color",
    "alt.base.color", "inactive.alt.base.color",
    "tooltip.base.color",
)
# Match opacity values our themes actually use; ignore unrelated 0.95+.
_SVG_OPACITY_RE = re.compile(
    r"opacity:(0\.585|0\.(0[5-9]|[1-8][0-9]|9[0-5]));fill"
)


def _update_kvconfig(cfg: Path, alpha_hex: str, menu_reduce: int) -> None:
    text = cfg.read_text()
    text = re.sub(r"^reduce_menu_opacity=.*",
                  f"reduce_menu_opacity={menu_reduce}",
                  text, flags=re.MULTILINE)
    for key in _KVANTUM_KEYS:
        text = re.sub(
            rf"({re.escape(key)}=#[0-9a-fA-F]{{6}})[0-9a-fA-F]{{2}}",
            rf"\g<1>{alpha_hex}",
            text,
        )
    cfg.write_text(text)
    print(f"  ✓ {cfg.name}")


def _update_svgz(file: Path, opacity: str) -> None:
    if not file.is_file():
        return
    data = gzip.decompress(file.read_bytes()).decode("utf-8")
    data = _SVG_OPACITY_RE.sub(f"opacity:{opacity};fill", data)
    file.write_bytes(gzip.compress(data.encode("utf-8")))


def _update_gtk4(css: Path, pct: int) -> None:
    if not css.is_file():
        return
    text = css.read_text()
    text = re.sub(r"@window_bg_color [0-9]+%",
                  f"@window_bg_color {pct}%", text)
    css.write_text(text)
    variant = css.parent.parent.name
    print(f"  ✓ {variant}/gtk-4.0/{css.name} → {pct}%")


# Restrict to .background.csd / dialog.background.csd blocks so we only
# touch the window/dialog alpha — buttons and overlays keep their values.
_GTK3_BG_RE = re.compile(
    r"(\.background\.csd[\s\S]*?\})",
)
_GTK3_DIALOG_RE = re.compile(
    r"(dialog\.background\.csd[\s\S]*?\})",
)
_RGBA_ALPHA_RE = re.compile(
    r"(background-color: rgba\([0-9]+, [0-9]+, [0-9]+, )0\.[0-9]+",
)
_HEX_ALPHA_RE = re.compile(r"(alpha\(#[0-9a-fA-F]+,)0\.[0-9]+")


def _update_gtk3(css: Path, opacity_dec: str) -> None:
    if not css.is_file():
        return
    text = css.read_text()
    text = _GTK3_BG_RE.sub(
        lambda m: _RGBA_ALPHA_RE.sub(rf"\g<1>{opacity_dec}", m.group(0)),
        text,
    )
    text = _GTK3_DIALOG_RE.sub(
        lambda m: _HEX_ALPHA_RE.sub(rf"\g<1>{opacity_dec}", m.group(0)),
        text,
    )
    css.write_text(text)
    variant = css.parent.parent.name
    print(f"  ✓ {variant}/gtk-3.0/gtk.css → {opacity_dec}")


def _apply_to_live_system() -> None:
    print()
    print("Applying to live system...")
    home = Path.home()
    kvantum_dest = home / ".config/Kvantum/mac-tahoe-liquid-kde"
    kvantum_dest.mkdir(parents=True, exist_ok=True)
    for f in KVANTUM_DIR.iterdir():
        shutil.copy2(f, kvantum_dest / f.name)
    desktop_dest = home / ".local/share/plasma/desktoptheme"
    desktop_dest.mkdir(parents=True, exist_ok=True)
    for v in VARIANTS:
        src = PLASMA_DIR / v
        if src.is_dir():
            shutil.copytree(src, desktop_dest / v, dirs_exist_ok=True)
    themes_dest = home / ".themes"
    themes_dest.mkdir(parents=True, exist_ok=True)
    for v in VARIANTS:
        src = GTK_DIR / v
        if src.is_dir():
            shutil.copytree(src, themes_dest / v, dirs_exist_ok=True)
    print("  ✓ Files copied")
    print("  Restarting plasmashell...")
    subprocess.Popen(
        ["plasmashell", "--replace"],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print("  ✓ Done")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 1

    pct_str, *rest = argv
    dock_pct = DEFAULT_DOCK_PCT
    apply_live = False

    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--dock" and i + 1 < len(rest):
            dock_pct = int(rest[i + 1])
            i += 2
        elif a == "--apply":
            apply_live = True
            i += 1
        else:
            i += 1

    try:
        pct = int(pct_str)
    except ValueError:
        print(f"Error: percent must be 0–100 (got '{pct_str}')", file=sys.stderr)
        return 1
    for v in (pct, dock_pct):
        if not 0 <= v <= 100:
            print(f"Error: percent must be 0–100 (got '{v}')", file=sys.stderr)
            return 1

    menu_reduce = 100 - pct
    alpha_hex = f"{pct * 255 // 100:02X}"
    svg_opacity = _to_svg(pct)
    dock_opacity = _to_svg(dock_pct)
    opacity_dec = "1" if pct == 100 else f"0.{pct:02d}"

    print("Setting transparency")
    print(f"  General:  {pct}%  (SVG {svg_opacity}, alpha 0x{alpha_hex})")
    print(f"  Dock:     {dock_pct}%  (SVG {dock_opacity})")
    print(f"  Menu:     reduce_menu_opacity={menu_reduce}")
    print()

    for cfg in (KVANTUM_DIR / "mac-tahoe-liquid-kde.kvconfig",
                KVANTUM_DIR / "mac-tahoe-liquid-kdeDark.kvconfig"):
        if cfg.is_file():
            _update_kvconfig(cfg, alpha_hex, menu_reduce)

    for variant in VARIANTS:
        for svg in ("widgets/translucentbackground", "widgets/tooltip",
                    "dialogs/background"):
            _update_svgz(PLASMA_DIR / variant / f"{svg}.svgz", svg_opacity)
            print(f"  ✓ {variant}/{svg} → {svg_opacity}")
        _update_svgz(PLASMA_DIR / variant / "widgets/panel-background.svgz",
                     dock_opacity)
        print(f"  ✓ {variant}/widgets/panel-background → {dock_opacity} (dock)")

    for variant in VARIANTS:
        for css in (GTK_DIR / variant / "gtk-4.0/gtk.css",
                    GTK_DIR / variant / "gtk-4.0/gtk-Light.css",
                    GTK_DIR / variant / "gtk-4.0/gtk-Dark.css"):
            _update_gtk4(css, pct)
        _update_gtk3(GTK_DIR / variant / "gtk-3.0/gtk.css", opacity_dec)

    print()
    print("Done.")

    if apply_live:
        _apply_to_live_system()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
