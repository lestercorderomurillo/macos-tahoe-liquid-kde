from localization import tr
from steps._helpers import DATA_HOME, fail, info, ok, offline, reinstall

DEST_DIR = DATA_HOME / "color-schemes"
LEGACY = ("MacTahoeDark.colors", "MacTahoeLight.colors")


def install() -> None:
    src = offline("color-schemes")
    if not src.is_dir():
        fail(tr('Color scheme source not found at {src}', src=src))
        return
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # Pre-0.6.2 wrote the wrong internal ColorScheme= name. Plasma could
    # pick those stale files up and end up in a split state.
    for stale in LEGACY:
        (DEST_DIR / stale).unlink(missing_ok=True)

    n_inst = n_re = 0
    for cs in sorted(src.glob("*.colors")):
        dest = DEST_DIR / cs.name
        existed = dest.is_file()
        try:
            dest.write_bytes(cs.read_bytes())
            from theme_accent import apply as apply_accent
            apply_accent(dest)
        except OSError as exc:
            fail(f"{cs.stem}: {exc}")
            continue
        if existed:
            reinstall(cs.stem); n_re += 1
        else:
            ok(tr('{value1} (installed)', value1=cs.stem)); n_inst += 1
    info(tr('{value1} color schemes — {n_inst} installed, {n_re} reinstalled', value1=n_inst + n_re, n_inst=n_inst, n_re=n_re))


def uninstall() -> None:
    n = 0
    for cs in DEST_DIR.glob("MacTahoeLiquidKde*.colors"):
        try:
            cs.unlink()
            ok(tr('{value1} removed', value1=cs.stem))
            n += 1
        except OSError:
            fail(cs.stem)
    info(tr('{n} color schemes removed', n=n))
