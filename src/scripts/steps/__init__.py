"""Per-feature install/uninstall modules.

Each step is a module exporting some subset of:
    deps()     -> Iterable[str | tuple[str, str]]
    build()    -> None     (compile native artefacts, if any)
    install()  -> None
    uninstall()-> None

There is no ``download()`` phase any more — every asset the install
needs is bundled under ``src/offline/`` in the repo. Since v0.18.0
the installer is fully offline.

Failures are reported via log.fail() and rolled into ``errors``.
"""
