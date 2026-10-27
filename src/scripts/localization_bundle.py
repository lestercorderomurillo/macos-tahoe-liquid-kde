"""Embed our translations into standalone installed Python tools."""

import json
from pathlib import Path


def standalone_source(source: str) -> str:
    root = Path(__file__).parent
    catalogs = {
        code: json.loads((root / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        for code in ("pt_BR", "de")
    }
    runtime = (root / "localization.py").read_text(encoding="utf-8")
    embedded = (
        "# Bundled localization: this executable is independent of the checkout.\n"
        f"_translation_namespace = {{'_BUNDLED_CATALOGS': {catalogs!r}}}\n"
        f"exec(compile({runtime!r}, '<bundled localization>', 'exec'), _translation_namespace)\n"
        "tr = _translation_namespace['tr']\n"
    )
    return source.replace("from localization import tr\n", embedded, 1)
