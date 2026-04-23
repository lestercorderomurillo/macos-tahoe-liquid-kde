from installer.steps._helpers import HOME, fail, info, ok, offline, reinstall

DEST_DIR = HOME / ".local/share/color-schemes"
LEGACY = ("MacTahoeDark.colors", "MacTahoeLight.colors")


def install() -> None:
    src = offline("color-schemes")
    if not src.is_dir():
        fail(f"Color scheme source not found at {src}")
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
        except OSError as exc:
            fail(f"{cs.stem}: {exc}")
            continue
        if existed:
            reinstall(cs.stem); n_re += 1
        else:
            ok(f"{cs.stem} (installed)"); n_inst += 1
    info(f"{n_inst + n_re} color schemes — {n_inst} installed, {n_re} reinstalled")


def uninstall() -> None:
    n = 0
    for cs in DEST_DIR.glob("MacTahoeLiquidKde*.colors"):
        try:
            cs.unlink()
            ok(f"{cs.stem} removed")
            n += 1
        except OSError:
            fail(cs.stem)
    info(f"{n} color schemes removed")
