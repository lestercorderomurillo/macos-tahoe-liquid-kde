"""Regression tests for staged icon-theme installation."""

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _existing_themes(dest: Path) -> None:
    for name in ("MacTahoeLiquidKde-Icons", "MacTahoeLiquidKde-Icons-dark"):
        theme = dest / name
        theme.mkdir(parents=True)
        (theme / "index.theme").write_text("old\n")


def test_install_stages_archive_before_replacing_active_themes(
        monkeypatch, tmp_path):
    from steps import icons

    dest = tmp_path / "installed"
    offline = tmp_path / "offline"
    dest.mkdir()
    offline.mkdir()
    _existing_themes(dest)
    (offline / "MacTahoeLiquidKde-Icons.tar.zst").touch()

    def fake_tar(args, **_kwargs):
        # The active themes must remain resolvable during the entire extraction.
        assert all((dest / name / "index.theme").is_file()
                   for name in icons._THEME_NAMES)
        staging = Path(args[args.index("-C") + 1])
        for name in icons._THEME_NAMES:
            theme = staging / name
            theme.mkdir()
            (theme / "index.theme").write_text("new\n")
        return subprocess.CompletedProcess(args, 0, "", "")

    def fake_install_tree(source, target, _label):
        assert (target / "index.theme").read_text() == "old\n"
        shutil.rmtree(target)
        shutil.copytree(source, target)
        return True

    monkeypatch.setattr(icons, "DEST_DIR", dest)
    monkeypatch.setattr(icons, "OFFLINE_DIR", offline)
    monkeypatch.setattr(icons.subprocess, "run", fake_tar)
    monkeypatch.setattr(icons, "install_tree", fake_install_tree)
    monkeypatch.setattr(icons.shutil, "which", lambda _cmd: None)

    icons.install()

    assert all((dest / name / "index.theme").read_text() == "new\n"
               for name in icons._THEME_NAMES)


def test_failed_icon_extraction_preserves_active_themes(monkeypatch, tmp_path):
    from steps import icons

    dest = tmp_path / "installed"
    offline = tmp_path / "offline"
    dest.mkdir()
    offline.mkdir()
    _existing_themes(dest)
    (offline / "MacTahoeLiquidKde-Icons.tar.zst").touch()

    monkeypatch.setattr(icons, "DEST_DIR", dest)
    monkeypatch.setattr(icons, "OFFLINE_DIR", offline)
    monkeypatch.setattr(
        icons.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args, 2, "", "corrupt archive"),
    )

    icons.install()

    assert all((dest / name / "index.theme").read_text() == "old\n"
               for name in icons._THEME_NAMES)
