"""Per-feature install/uninstall modules.

Each step is a module exporting some subset of:
    deps()     -> Iterable[str | tuple[str, str]]
    download() -> None     (writes to STEPS_DIR / <feature>)
    build()    -> None
    install()  -> None
    uninstall()-> None

Failures are reported via installer.log.fail() and rolled into ``errors``.
"""
