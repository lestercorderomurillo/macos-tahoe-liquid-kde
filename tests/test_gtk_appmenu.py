"""GTK startup integration must retain modules without editing live settings."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import distro
from steps import globalmenu


@pytest.fixture
def gtk_environment(sandbox, monkeypatch):
    module = sandbox / "lib/gtk-3.0/modules/libappmenu-gtk-module.so"
    module.parent.mkdir(parents=True)
    module.touch()
    monkeypatch.setattr(globalmenu, "HOME", sandbox)
    monkeypatch.setattr(globalmenu, "gtk3_appmenu_module", lambda: module)

    def install_file(source, destination, label, *, user_owned=False):
        assert user_owned
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return True

    def remove_file(destination, label):
        destination.unlink()
        return True

    monkeypatch.setattr(globalmenu, "sudo_install_file", install_file)
    monkeypatch.setattr(globalmenu, "sudo_remove", remove_file)
    return module


def _source_twice(script, modules):
    environment = dict(os.environ)
    if modules is None:
        environment.pop("GTK3_MODULES", None)
    else:
        environment["GTK3_MODULES"] = modules
    result = subprocess.run(
        ["sh", "-c", '. "$1"; . "$1"; exec "$2" -c "$3"', "gtk-hook-test",
         str(script), sys.executable,
         'import json, os; print(json.dumps([os.environ.get("GTK3_MODULES"), '
         'os.environ.get("GTK_MODULES")]))'],
        env=environment, capture_output=True, text=True, check=True, timeout=10,
    )
    versioned, generic = json.loads(result.stdout)
    assert generic == environment.get("GTK_MODULES")
    return versioned


@pytest.mark.parametrize("before,after", [
    (None, "appmenu-gtk-module"),
    ("", "appmenu-gtk-module"),
    ("colorreload-gtk-module:window-decorations-gtk-module",
     "colorreload-gtk-module:window-decorations-gtk-module:appmenu-gtk-module"),
    ("appmenu-gtk-module", "appmenu-gtk-module"),
    ("appmenu-gtk-module:other", "appmenu-gtk-module:other"),
    ("my-appmenu-gtk-module", "my-appmenu-gtk-module:appmenu-gtk-module"),
    ("first::last:", "first::last::appmenu-gtk-module"),
])
def test_login_hook_preserves_existing_modules_and_is_idempotent(
        gtk_environment, before, after):
    globalmenu._install_gtk_appmenu_environment()
    assert _source_twice(globalmenu.gtk_appmenu_env_path(), before) == after


def test_login_hook_quotes_paths_and_never_evaluates_module_values(
        gtk_environment, monkeypatch, sandbox):
    module = sandbox / "module's $(touch unsafe-path).so"
    module.touch()
    monkeypatch.setattr(globalmenu, "gtk3_appmenu_module", lambda: module)
    globalmenu._install_gtk_appmenu_environment()
    before = f"$(touch {sandbox / 'unsafe-value'}):other"
    assert _source_twice(globalmenu.gtk_appmenu_env_path(), before) == (
        before + ":appmenu-gtk-module")
    assert not (sandbox / "unsafe-value").exists()
    assert not (Path.cwd() / "unsafe-path").exists()


@pytest.mark.parametrize("before", [None, "", "other-module"])
def test_login_hook_skips_module_removed_after_install(gtk_environment, before):
    globalmenu._install_gtk_appmenu_environment()
    gtk_environment.unlink()
    assert _source_twice(globalmenu.gtk_appmenu_env_path(), before) == before


def test_install_and_uninstall_only_manage_the_owned_login_hook(
        gtk_environment, sandbox):
    settings = sandbox / ".config/gtk-3.0/settings.ini"
    settings.parent.mkdir()
    original = "[Settings]\ngtk-modules=appmenu-gtk-module:keep-me\n"
    settings.write_text(original)
    other = globalmenu.gtk_appmenu_env_path().with_name("user.sh")
    other.parent.mkdir(parents=True)
    other.write_text("export USER_SETTING=keep\n")

    globalmenu._install_gtk_appmenu_environment()
    installed = globalmenu.gtk_appmenu_env_path().read_bytes()
    globalmenu._install_gtk_appmenu_environment()
    assert globalmenu.gtk_appmenu_env_path().read_bytes() == installed
    globalmenu._remove_gtk_appmenu_environment()
    globalmenu._remove_gtk_appmenu_environment()

    assert not globalmenu.gtk_appmenu_env_path().exists()
    assert settings.read_text() == original
    assert other.read_text() == "export USER_SETTING=keep\n"


@pytest.mark.parametrize("symlink", [False, True])
def test_custom_environment_file_is_never_overwritten_or_removed(
        gtk_environment, sandbox, symlink):
    destination = globalmenu.gtk_appmenu_env_path()
    destination.parent.mkdir(parents=True)
    content = "# My startup preferences\nexport GTK3_MODULES=custom\n"
    if symlink:
        other = sandbox / "external.sh"
        other.write_text(globalmenu.GTK_ENV_MARKER + content)
        destination.symlink_to(other)
    else:
        destination.write_text(content)
    original = destination.read_bytes()
    globalmenu._install_gtk_appmenu_environment()
    globalmenu._remove_gtk_appmenu_environment()
    assert destination.read_bytes() == original
    assert destination.is_symlink() == symlink


def test_missing_runtime_module_does_not_create_a_login_hook(
        gtk_environment, monkeypatch):
    monkeypatch.setattr(globalmenu, "gtk3_appmenu_module", lambda: None)
    globalmenu._install_gtk_appmenu_environment()
    assert not globalmenu.gtk_appmenu_env_path().exists()


def test_login_hook_uses_custom_xdg_config_home(gtk_environment, monkeypatch, sandbox):
    config = sandbox / "custom-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    globalmenu._install_gtk_appmenu_environment()
    assert (config / "plasma-workspace/env/mac-tahoe-gtk-appmenu.sh").is_file()
    assert not (sandbox / ".config/plasma-workspace").exists()


@pytest.mark.parametrize("reported,qt_lib,multiarch,expected", [
    ("/opt/gtk/lib", "/opt/qt/lib", "x86_64-linux-gnu",
     "/opt/gtk/lib/gtk-3.0/modules/libappmenu-gtk-module.so"),
    (None, "/opt/qt/lib", "x86_64-linux-gnu",
     "/usr/lib/x86_64-linux-gnu/gtk-3.0/modules/libappmenu-gtk-module.so"),
    (None, "/usr/lib64", None,
     "/usr/lib64/gtk-3.0/3.0.0/modules/libappmenu-gtk-module.so"),
    (None, "/usr/lib", None,
     "/usr/lib/gtk-3.0/modules/libappmenu-gtk-module.so"),
    ("relative/path", "/opt/qt/lib", "aarch64-linux-gnu",
     "/usr/lib/aarch64-linux-gnu/gtk-3.0/modules/libappmenu-gtk-module.so"),
])
def test_module_discovery_handles_runtime_only_multiarch_and_custom_prefixes(
        monkeypatch, reported, qt_lib, multiarch, expected):
    monkeypatch.setattr(distro, "_run_query", lambda command: reported)
    monkeypatch.setattr(distro, "system_lib_dir", lambda: Path(qt_lib))
    monkeypatch.setattr(distro.sysconfig, "get_config_var", lambda key: multiarch)
    monkeypatch.setattr(Path, "is_file", lambda path: str(path) == expected)
    assert distro.gtk3_appmenu_module() == Path(expected)


def test_module_discovery_returns_none_without_a_real_module(monkeypatch):
    monkeypatch.setattr(distro, "_run_query", lambda command: None)

    def missing_qt():
        raise distro.Qt6PathsMissing("test")

    monkeypatch.setattr(distro, "system_lib_dir", missing_qt)
    monkeypatch.setattr(Path, "is_file", lambda path: False)
    assert distro.gtk3_appmenu_module() is None
