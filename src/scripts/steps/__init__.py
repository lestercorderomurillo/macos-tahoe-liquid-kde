"""Per-feature install/uninstall step modules. Each exports a subset of
deps() / build() / install() / uninstall(); failures report via log.fail().
Fully offline since v0.18.0 — assets are bundled, there is no download() phase.
"""
