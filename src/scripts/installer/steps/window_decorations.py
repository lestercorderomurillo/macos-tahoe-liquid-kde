import shutil

from installer.steps._helpers import (
    HOME, fail, info, kw_write, offline, ok, qdbus_call, reinstall, theme_mode,
)

DEST_DIR = HOME / ".local/share/aurorae/themes"
VARIANTS = ("Dark", "Light")


def install() -> None:
    src = offline("aurorae")
    if not src.is_dir():
        fail(f"Aurorae source not found at {src}")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    n_inst = n_re = 0
    for mode in VARIANTS:
        name = f"MacTahoeLiquidKde-{mode}"
        dest = DEST_DIR / name
        existed = dest.is_dir()
        dest.mkdir(parents=True, exist_ok=True)

        deco = src / name / "decoration.svg"
        if deco.is_file():
            shutil.copy2(deco, dest)
        rc = src / f"{name}rc"
        if rc.is_file():
            shutil.copy2(rc, dest / f"{name}rc")
        for icon in (src / f"icons-{mode}").glob("*.svg"):
            shutil.copy2(icon, dest)

        for fn in ("metadata.desktop", "metadata.json"):
            template = src / fn
            if template.is_file():
                (dest / fn).write_text(
                    template.read_text().replace("theme_name", name)
                )

        if existed:
            reinstall(name); n_re += 1
        else:
            ok(f"{name} (installed)"); n_inst += 1

    info(f"{n_inst + n_re} Aurorae themes — {n_inst} installed, {n_re} reinstalled")

    chosen = "MacTahoeLiquidKde-Light" if theme_mode() == "light" else "MacTahoeLiquidKde-Dark"
    for key, value in (
        ("library", "org.kde.kwin.aurorae"),
        ("theme", f"__aurorae__svg__{chosen}"),
        ("ButtonsOnLeft", "XIA"),
        ("ButtonsOnRight", ""),
    ):
        kw_write("--file", "kwinrc",
                 "--group", "org.kde.kdecoration2",
                 "--key", key, value)
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    ok(f"Window decoration set to {chosen}")


def uninstall() -> None:
    n = 0
    for mode in VARIANTS:
        d = DEST_DIR / f"MacTahoeLiquidKde-{mode}"
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            ok(f"MacTahoeLiquidKde-{mode} removed")
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
    ok("Window decoration reset to Breeze")
    info(f"{n} Aurorae themes removed")
