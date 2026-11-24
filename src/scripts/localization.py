"""Small, dependency-free localization layer for the installer surfaces.

Plasma widgets use KDE's native ``i18n()`` catalog machinery.  The Python
installer cannot rely on gettext catalogs being installed yet, so the GUI and
the curses wizard share this module instead.  English source strings are the
stable message ids and remain the fallback for incomplete translations.
"""

from __future__ import annotations

import json
import locale
import os
import tempfile
from pathlib import Path


LANGUAGES = (
    {"code": "auto", "label": "System default"},
    {"code": "en", "label": "English"},
    {"code": "es", "label": "Español"},
    {"code": "zh_CN", "label": "简体中文"},
    {"code": "pt_BR", "label": "Português (Brasil)"},
    {"code": "de", "label": "Deutsch"},
    {"code": "fr", "label": "Français"},
    {"code": "it", "label": "Italiano"},
    {"code": "ja", "label": "日本語"},
    {"code": "ko", "label": "한국어"},
    {"code": "ar", "label": "العربية"},
    {"code": "hi", "label": "हिन्दी"},
    {"code": "nl", "label": "Nederlands"},
    {"code": "pl", "label": "Polski"},
    {"code": "tr", "label": "Türkçe"},
    {"code": "ru", "label": "Русский"},
)
LANGUAGE_CODES = tuple(item["code"] for item in LANGUAGES)
CATALOG_CODES = tuple(code for code in LANGUAGE_CODES if code not in ("auto", "en"))


_FEATURE_LABELS = {
    "fonts": "Fonts", "color_schemes": "Color Schemes",
    "plasma_theme": "Plasma Theme", "window_decorations": "Window Decorations",
    "kvantum": "Kvantum Theme", "icons": "Icons", "cursors": "Cursors",
    "wallpapers": "Wallpapers", "global_theme": "Global Theme",
    "layout": "Layout", "plasmoids": "Plasmoids", "globalmenu": "Global Menu",
    "acrylic_glass": "Acrylic Glass", "rounded_corners": "Rounded Corners",
    "sounds": "Sounds", "gtk": "GTK Theme", "firefox": "Firefox Theme",
    "sddm": "SDDM Login", "plymouth": "Plymouth", "apps": "Apps",
    "nautilus": "Nautilus", "nautilus_bookmarks": "Nautilus Bookmarks",
    "portals": "Portals", "oled_care": "OLED Care",
    "apply_theme": "Apply Theme", "kconf_update": "Config Migrations",
}


def _load_catalog(code: str) -> dict[str, str]:
    bundled = globals().get("_BUNDLED_CATALOGS")
    if bundled is not None:
        return bundled[code]
    path = Path(__file__).with_name("locales") / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8"))


_TRANSLATIONS = {code: _load_catalog(code) for code in CATALOG_CODES}


def normalize_language(value: str | None) -> str:
    """Map locale spellings (``zh-CN.UTF-8``, ``es_CR``) to our codes."""
    text = (value or "").strip().replace("-", "_").split(".", 1)[0]
    low = text.lower().split("@", 1)[0]
    if low in ("zh", "zh_cn", "zh_hans") or low.startswith("zh_hans_"):
        return "zh_CN"
    if low == "pt" or low == "pt_br":
        return "pt_BR"
    base = low.split("_", 1)[0]
    return base if base in CATALOG_CODES else "en"


def system_language() -> str:
    for key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(key)
        if value:
            return normalize_language(value.split(":", 1)[0])
    try:
        value = locale.getlocale(locale.LC_MESSAGES)[0]
    except (AttributeError, ValueError):
        value = None
    return normalize_language(value)


def _config_path() -> Path:
    home = Path(os.environ.get("HOME") or Path.home())
    root = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return root / "mac-tahoe-liquid-kde/language.json"


def get_language() -> str:
    """Return the saved preference (``auto`` is intentionally preserved)."""
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return "auto"
    code = data.get("language") if isinstance(data, dict) else None
    return code if code in LANGUAGE_CODES else "auto"


def effective_language(preference: str | None = None) -> str:
    inherited = os.environ.get("MTTKDE_LANGUAGE")
    code = preference if preference in LANGUAGE_CODES else (
        inherited if inherited in LANGUAGE_CODES else get_language())
    return system_language() if code == "auto" else code


def set_language(code: str) -> bool:
    if code not in LANGUAGE_CODES:
        return False
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="language-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"language": code}, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except OSError:
        return False
    return True


def translate(message: str, language: str | None = None, **values: object) -> str:
    code = effective_language(language)
    result = _TRANSLATIONS.get(code, {}).get(message, message)
    return result.format(**values) if values else result


def feature_label(key: str, language: str | None = None) -> str:
    source = _FEATURE_LABELS.get(key, key.replace("_", " ").title())
    return translate(source, language)


def tr(message: str, /, **values: object) -> str:
    """Translate a complete message before interpolating runtime values."""
    result = _TRANSLATIONS.get(effective_language(), {}).get(message, message)
    return result.format(**values) if values else result


def language_options(language: str | None = None) -> list[dict[str, str]]:
    """Native labels stay recognizable even after changing languages."""
    options = [dict(item) for item in LANGUAGES]
    options[0]["label"] = translate("System default", language)
    return options
