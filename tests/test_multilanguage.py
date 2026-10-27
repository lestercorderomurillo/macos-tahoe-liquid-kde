"""Complete Portuguese/German messages and locale-independent control flow."""

import ast
import gettext
import json
import os
from pathlib import Path
import re
import string
import subprocess
import sys

import pytest

import build_translations
import cli
import localization
from localization_bundle import standalone_source
import log


LANGUAGES = ("pt_BR", "de")


@pytest.mark.parametrize(("value", "expected"), [
    ("pt-BR.UTF-8", "pt_BR"), ("pt", "pt_BR"),
    ("pt_PT.UTF-8", "en"), ("de_DE.UTF-8", "de"),
    ("de_AT@euro", "de"), ("de_CH", "de"),
    ("debug", "en"), ("esperanto", "en"),
])
def test_locale_aliases_are_exact(value, expected):
    assert localization.normalize_language(value) == expected


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_python_message_has_a_complete_catalog(repo, language):
    catalog = localization._TRANSLATIONS[language]
    assert set(localization._ES) <= catalog.keys()
    for path in [*Path(repo / "src/scripts").rglob("*.py"),
                 repo / "src/installer/installer_ui.py"]:
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            if ast.unparse(node.func) not in ("tr", "translate", "step"):
                continue
            message = node.args[0]
            assert not isinstance(message, ast.JoinedStr), (path, node.lineno)
            if isinstance(message, ast.Constant) and isinstance(message.value, str):
                assert message.value in catalog, (path, node.lineno, message.value)


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_preserves_fields_and_commands(language):
    def fields(value):
        return sorted((field, spec, conversion)
                      for _, field, spec, conversion in string.Formatter().parse(value)
                      if field is not None)

    for source, target in localization._TRANSLATIONS[language].items():
        assert target.strip(), source
        assert fields(source) == fields(target), source
        assert sorted(re.findall(r"%\d+", source)) == sorted(re.findall(r"%\d+", target)), source
    for source in (cli.INSTALL_HELP, cli.UNINSTALL_HELP):
        target = localization.translate(source, language)
        assert set(re.findall(r"--[a-z][a-z-]+", source)) == set(re.findall(r"--[a-z][a-z-]+", target))


@pytest.mark.parametrize("language", LANGUAGES)
def test_catalogs_cover_all_project_widget_and_kcm_messages(repo, language):
    catalog = localization._TRANSLATIONS[language]
    widgets = repo / "src/offline/plasmoids"
    for widget in widgets.glob("org.kde.mac*"):
        messages = build_translations.widget_messages(widget)
        if not messages:
            continue
        locale_dir = "locale" if widget.name.endswith("globalmenu") else "contents/locale"
        path = widget / locale_dir / language / "LC_MESSAGES" / f"plasma_applet_{widget.name}.mo"
        with path.open("rb") as stream:
            translations = gettext.GNUTranslations(stream)
        for (context, source), plural in messages.items():
            actual = translations.pgettext(context, source) if context else translations.gettext(source)
            assert actual == catalog[source], (widget.name, context, source)
    path = (repo / "src/offline/kwin-effects/acrylic-glass/locale" / language
            / "LC_MESSAGES/kwin_effect_liquidglass.mo")
    with path.open("rb") as stream:
        translations = gettext.GNUTranslations(stream)
    for _, source in build_translations.kcm_messages():
        assert translations.gettext(source) == catalog[source]


@pytest.mark.parametrize("language", LANGUAGES)
def test_logs_and_progress_keep_one_language_without_changing_phases(
        sandbox, monkeypatch, capsys, language):
    monkeypatch.setenv("MTTKDE_LANGUAGE", language)
    monkeypatch.setattr(log, "PROGRESS_FILE", str(sandbox / "progress"))
    log.progress_reset()
    log.step("Installing {label}", label=localization.feature_label("fonts"))
    log.reinstall(localization.tr("Fonts"))
    log.ok(localization.tr("Global Menu {language} translation installed", language="de"))
    output = capsys.readouterr().out
    assert "Step " not in output
    assert "Installing" not in output
    assert "reinstalled" not in output
    record = Path(log.PROGRESS_FILE).read_text().strip()
    assert record.split("\t")[1] in output
    log.progress_reset()
    log.step("Removing Theme Switcher")


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("script", ("theme_switch.py", "oled_care.py"))
def test_installed_helpers_translate_without_repository_or_pythonpath(
        repo, sandbox, language, script):
    source = (repo / "src/scripts" / script).read_text()
    installed = sandbox / "standalone-tool"
    installed.write_text(standalone_source(source))
    config = sandbox / ".config/mac-tahoe-liquid-kde/language.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"language": language}))
    env = {**os.environ, "HOME": str(sandbox), "XDG_CONFIG_HOME": str(sandbox / ".config")}
    env.pop("MTTKDE_LANGUAGE", None)
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-I", str(installed)], cwd=sandbox,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stderr.startswith("Uso:" if language == "pt_BR" else "Aufruf:")
    assert "Traceback" not in result.stderr


def test_launcher_categories_do_not_depend_on_translated_names(repo):
    source = (repo / "src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher"
              / "contents/ui/AllAppsList.qml").read_text()
    assert "instanceof Kicker.RecentUsageModel" in source
    assert 'i18n("Suggestions")' in source
    assert "!c.isSuggestions" in source
    assert 'indexOf("recent")' not in source


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("pkexec", (True, False))
def test_gui_selection_survives_privilege_escalation(sandbox, monkeypatch, language, pkexec):
    import installer_ui

    assert localization.set_language(language)
    # A stale inherited override must not undo a fresh GUI selection.
    monkeypatch.setenv("MTTKDE_LANGUAGE", "en")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr(installer_ui.shutil, "which",
                        lambda name: "/usr/bin/pkexec" if pkexec else None)
    command = installer_ui.escalated_command_for_action(
        "install", headless=True, progress_file="/tmp/progress", cancel_file="/tmp/cancel")
    assert f"MTTKDE_LANGUAGE={language}" in command
    assert command.startswith("pkexec env " if pkexec else "SUDO_ASKPASS=")


@pytest.mark.parametrize("language", LANGUAGES)
def test_gui_progress_hides_english_control_key(sandbox, monkeypatch, language):
    import installer_ui

    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    monkeypatch.setenv("MTTKDE_LANGUAGE", language)
    bridge = installer_ui._make_installer_bridge()
    visible = []
    bridge.logAppended.connect(visible.append)
    title = localization.tr("Removing Theme Switcher")
    bridge._handle_record(f"1\t{title}\tRemoving Theme Switcher")
    assert app is not None
    assert visible == [title]
    assert bridge._current_step == title


@pytest.mark.parametrize("language", LANGUAGES)
def test_installer_qml_messages_are_complete(repo, language):
    catalog = localization._TRANSLATIONS[language]
    for path in (repo / "src/installer").glob("*.qml"):
        for source in re.findall(r'\bt\("((?:[^"\\]|\\.)*)"\)', path.read_text()):
            assert json.loads('"' + source + '"') in catalog, (path, source)


@pytest.mark.parametrize("language", LANGUAGES)
def test_boot_password_fallback_uses_selected_language(repo, sandbox, monkeypatch, language):
    from steps import plymouth

    monkeypatch.setenv("MTTKDE_LANGUAGE", language)
    monkeypatch.setattr(plymouth, "have", lambda command: True)
    monkeypatch.setattr(plymouth, "_current_default_theme", lambda: plymouth.THEME_NAME)
    captured = []

    def inspect_staged(source, destination, label):
        captured.append((source / "MacTahoeLiquidKde.script").read_text())
        return False  # Stop before any boot configuration or initramfs operation.

    monkeypatch.setattr(plymouth, "sudo_install_tree", inspect_staged)
    original = repo / "src/offline/plymouth/MacTahoeLiquidKde/MacTahoeLiquidKde.script"
    source = original.read_text()
    plymouth.install()
    prompt = json.dumps(localization.tr("Password:"), ensure_ascii=False)
    assert captured == [source.replace('prompt = "Password:";', f'prompt = {prompt};')]
    assert f'prompt = {prompt};' in captured[0]
    assert original.read_text() == source
