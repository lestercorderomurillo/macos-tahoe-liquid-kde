"""Opt-in Liquid Glass desktop widgets (#143)."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/scripts"))


def test_bundle_holds_the_widget_set_and_photos():
    archive = ROOT / "src/offline/desktop-widgets/liquidglass-kde-widgets.tar.zst"
    listing = subprocess.run(["tar", "--zstd", "-tf", str(archive)], capture_output=True, text=True, check=True).stdout
    ids = {line.split("/")[1] for line in listing.splitlines() if line.count("/") >= 2 and line.endswith("/metadata.json")}
    for name in ("calendar", "weather", "music", "timer", "clock-analog", "photos"):
        assert "com.jaxparrow07.macoswidgets." + name in ids
    assert not any(".test-" in i or i.endswith(".test-glass") for i in ids)
    assert (archive.parent / "LICENSE").read_text().startswith("                    GNU GENERAL PUBLIC LICENSE")


@pytest.fixture
def widgets(tmp_path, monkeypatch):
    from steps import plasmoids
    archive_root = tmp_path / "src"
    for name in ("com.jaxparrow07.macoswidgets.one", "com.jaxparrow07.macoswidgets.two"):
        (archive_root / name).mkdir(parents=True)
        (archive_root / name / "metadata.json").write_text("{}")
    archive = tmp_path / "widgets.tar.zst"
    subprocess.run(["tar", "--zstd", "-cf", str(archive), "-C", str(archive_root), "."], check=True)
    dest = tmp_path / "plasmoids"
    monkeypatch.setattr(plasmoids, "WIDGETS_ARCHIVE", archive)
    monkeypatch.setattr(plasmoids, "DEST_DIR", dest)
    monkeypatch.setattr(plasmoids, "WIDGETS_STATE", tmp_path / "state/desktop-widgets.list")

    def copy(src, dst, label):
        import shutil
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return True

    def remove(path, label=None):
        import shutil
        shutil.rmtree(path, ignore_errors=True)
        return True

    monkeypatch.setattr(plasmoids, "install_tree", copy)
    monkeypatch.setattr(plasmoids, "remove_tree", remove)
    return plasmoids, dest


def test_opting_in_installs_and_opting_out_removes_only_ours(widgets):
    plasmoids, dest = widgets
    (dest / "com.user.own").mkdir(parents=True)
    plasmoids.install_desktop_widgets(True)
    assert {p.name for p in dest.iterdir()} == {"com.jaxparrow07.macoswidgets.one", "com.jaxparrow07.macoswidgets.two", "com.user.own"}
    assert plasmoids._installed_widgets() == {"com.jaxparrow07.macoswidgets.one", "com.jaxparrow07.macoswidgets.two"}
    plasmoids.install_desktop_widgets(False)
    assert {p.name for p in dest.iterdir()} == {"com.user.own"}
    assert not plasmoids.WIDGETS_STATE.exists()


def test_existing_user_widget_survives_opt_in_and_out(widgets):
    plasmoids, dest = widgets
    user_widget = dest / "com.jaxparrow07.macoswidgets.one"
    user_widget.mkdir(parents=True)
    personal = user_widget / "metadata.json"
    personal.write_text('{"user": true}')
    plasmoids.install_desktop_widgets(False)
    plasmoids.install_desktop_widgets(True)
    assert "com.jaxparrow07.macoswidgets.one" not in plasmoids._installed_widgets()
    plasmoids.install_desktop_widgets(False)
    assert personal.read_text() == '{"user": true}'
    assert {p.name for p in dest.iterdir()} == {user_widget.name}


def test_state_entries_that_are_paths_are_ignored(widgets):
    plasmoids, dest = widgets
    unrelated = dest / "org.kde.other"
    unrelated.mkdir(parents=True)
    outside = dest.parent / "outside"
    outside.mkdir()
    plasmoids.WIDGETS_STATE.parent.mkdir(parents=True)
    plasmoids.WIDGETS_STATE.write_text("../outside\norg.kde.other\n")
    plasmoids._remove_desktop_widgets()
    assert outside.is_dir() and unrelated.is_dir()


def test_desktop_widgets_are_selected_by_default():
    from installer_choices import defaults
    assert defaults()["desktop_widgets"] is True
