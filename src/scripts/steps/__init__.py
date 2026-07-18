"""Per-feature install/uninstall step modules. Each exports a subset of
deps() / build() / install() / uninstall(); failures report via log.fail().
Fully offline — assets are bundled, there is no download() phase.
"""
