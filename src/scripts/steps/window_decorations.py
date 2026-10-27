from localization import tr

from window_controls import EDITIONS, assemble_aurorae
from theme_switch import decoration_theme

from steps._helpers import (
    DATA_HOME, fail, info, kw_write, offline, ok, qdbus_call, reinstall, remove_tree, theme_mode,
    warn,
)

DEST_DIR = DATA_HOME / "aurorae/themes"
VARIANTS = ("Dark", "Light")


def install() -> None:
    src = offline("aurorae")
    if not src.is_dir():
        fail(tr('Aurorae source not found at {src}', src=src))
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    n_inst = n_re = 0
    for edition in EDITIONS:
        for mode in VARIANTS:
            name = f"{edition}LiquidKde-{mode}"
            dest = DEST_DIR / name
            existed = dest.is_dir()
            assemble_aurorae(src, dest, mode, edition)
            if (dest / "decoration.svg").is_file():
                from window_shadows import apply_aurorae
                apply_aurorae(dest / "decoration.svg")
            if existed:
                reinstall(name); n_re += 1
            else:
                ok(tr('{name} (installed)', name=name)); n_inst += 1

    chosen = decoration_theme(theme_mode())
    write_failures = 0
    for key, value in (
        ("library", "org.kde.kwin.aurorae"),
        ("theme", f"__aurorae__svg__{chosen}"),
        ("ButtonsOnLeft", "XIA"),
        ("ButtonsOnRight", ""),
    ):
        if not kw_write("--file", "kwinrc",
                        "--group", "org.kde.kdecoration2",
                        "--key", key, value):
            write_failures += 1
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    if write_failures == 0:
        ok(tr('Window decoration set to {chosen}', chosen=chosen))
    else:
        warn(tr("Window decoration files installed but {write_failures} kwinrc key(s) could not be written — kwriteconfig6 unavailable. Install plasma-workspace or your distro's equivalent to apply the decoration on next login.", write_failures=write_failures))

    info(tr('{value1} Aurorae themes — {n_inst} installed, {n_re} reinstalled', value1=n_inst + n_re, n_inst=n_inst, n_re=n_re))


def uninstall() -> None:
    n = 0
    for edition in EDITIONS:
        for mode in VARIANTS:
            name = f"{edition}LiquidKde-{mode}"
            d = DEST_DIR / name
            if remove_tree(d, name):
                n += 1
    for key, value in (
        ("library", "org.kde.breeze"),
        ("theme", "Breeze"),
        ("ButtonsOnLeft", "M"),
        ("ButtonsOnRight", "IAX"),
    ):
        kw_write("--file", "kwinrc",
                 "--group", "org.kde.kdecoration2",
                 "--key", key, value)
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    ok(tr('Window decoration reset to Breeze'))
    info(tr('{n} Aurorae themes removed', n=n))
