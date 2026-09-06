"""English/Spanish/Simplified-Chinese localization regression guards."""

from __future__ import annotations

import gettext
import json
import re
from pathlib import Path

import localization


def test_locale_normalization_and_english_fallback():
    assert localization.normalize_language("zh-CN.UTF-8") == "zh_CN"
    assert localization.normalize_language("zh_Hans") == "zh_CN"
    assert localization.normalize_language("es_CR.UTF-8") == "es"
    assert localization.normalize_language("fr_FR.UTF-8") == "en"
    assert localization.translate("Untranslated source", "es") == "Untranslated source"


def test_system_locale_auto_detection(monkeypatch):
    for key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert localization.effective_language("auto") == "zh_CN"
    assert localization.translate("Install", "auto") == "安装"


def test_language_preference_round_trip(sandbox):
    assert localization.get_language() == "auto"
    assert localization.set_language("es")
    assert localization.get_language() == "es"
    saved = json.loads((sandbox / ".config/mac-tahoe-liquid-kde/language.json").read_text())
    assert saved == {"language": "es"}
    assert not localization.set_language("unsupported")
    assert localization.get_language() == "es"


def test_feature_labels_and_descriptions_translate():
    assert localization.feature_label("window_decorations", "es") == "Decoraciones de ventanas"
    assert localization.feature_label("wallpapers", "zh_CN") == "壁纸"
    assert localization.translate("Desktop backgrounds", "es") == "Fondos del escritorio"


def _catalog(path: Path) -> gettext.GNUTranslations:
    with path.open("rb") as stream:
        return gettext.GNUTranslations(stream)


def test_plasmoid_catalogs_ship_for_spanish_and_simplified_chinese(repo):
    widgets = {
        "org.kde.mac-tahoe-liquid-kde.launcher": ("Apps", "Aplicaciones", "应用"),
        "org.kde.mac-tahoe-liquid-kde.trashcan": ("Trash", "Papelera", "回收站"),
        "org.kde.mac.tahoe.liquid.taskmanager": (
            "Hover magnification:", "Ampliación al pasar el cursor:", "悬停放大："),
    }
    base = repo / "src/offline/plasmoids"
    for widget, (source, spanish, chinese) in widgets.items():
        domain = f"plasma_applet_{widget}.mo"
        for language, expected in (("es", spanish), ("zh_CN", chinese)):
            mo = base / widget / "contents/locale" / language / "LC_MESSAGES" / domain
            assert mo.is_file(), mo
            assert _catalog(mo).gettext(source) == expected

    globalmenu = base / "org.kde.mac.tahoe.liquid.globalmenu"
    domain = "plasma_applet_org.kde.mac.tahoe.liquid.globalmenu.mo"
    assert _catalog(globalmenu / "locale/es/LC_MESSAGES" / domain).gettext(
        "About This Computer") == "Acerca de este equipo"
    assert _catalog(globalmenu / "locale/zh_CN/LC_MESSAGES" / domain).gettext(
        "About This Computer") == "关于本机"


def test_installer_qml_has_live_language_selector(repo):
    source = (repo / "src/installer/InstallerWindow.qml").read_text()
    assert "id: languageButton" in source
    assert "id: languagePopup" in source
    assert "model: installer ? installer.languages : []" in source
    assert "installer.setLanguage(modelData.code)" in source
    # KDE's desktop-style ComboBox uses Menu.qml, whose currentIndex binding
    # loops when the model changes as a language is selected.
    assert "QQC2.ComboBox" not in source


def test_dock_reuses_complete_upstream_taskmanager_catalog(repo):
    root = (repo / "src/offline/plasmoids"
            / "org.kde.mac.tahoe.liquid.taskmanager/contents")
    source = "\n".join(path.read_text() for path in root.rglob("*.qml"))
    # Bare i18n()/i18nc() would resolve against the fork's intentionally tiny
    # custom catalog and turn the inherited configuration UI back to English.
    assert not re.search(r"\bi18n(?:c|p|cp)?\(", source)
    assert source.count('"plasma_applet_org.kde.plasma.taskmanager"') > 100
