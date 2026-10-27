"""Exercise edition replacement through staging, layout scripts and ownership."""
import json
import shutil
import subprocess

import pytest

import launcher_defaults as defaults
import theme_switch
from steps import layout, plasmoids


@pytest.fixture
def transition(repo, sandbox, monkeypatch):
    config = sandbox / "defaults.json"
    monkeypatch.setattr(defaults, "DEFAULTS_FILE", config)
    monkeypatch.setattr(layout, "HOME", sandbox)
    monkeypatch.setattr(plasmoids, "HOME", sandbox)
    data = sandbox / ".local/share"
    monkeypatch.setattr(layout, "DATA_HOME", data)
    monkeypatch.setattr(plasmoids, "DEST_DIR", data / "plasma/plasmoids")
    monkeypatch.setattr(layout, "_ensure_panel_colorizer", lambda: None)
    monkeypatch.setattr(layout, "_patch_plasmashellrc", lambda: None)
    monkeypatch.setattr(layout, "_discover_is_installed", lambda: False)
    monkeypatch.setattr(layout, "_wait_for_layout_install", lambda: True)
    monkeypatch.setattr(layout.time, "sleep", lambda _: None)
    monkeypatch.setattr(plasmoids, "install_tree", lambda src, dst, label:
                        bool(shutil.copytree(src, dst, dirs_exist_ok=True)))
    widget = repo / "src/offline/plasmoids" / defaults.LAUNCHER_ID
    installed = plasmoids.DEST_DIR / widget.name

    def select(preset):
        config.write_text(json.dumps({"wallpaper": "MacGoldenGate" if preset == 2 else "MacTahoe",
                                      "launcher_preset": preset}))

    return select, widget, installed


def execute_layout(script, presets):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for Plasma layout script execution")
    harness = '''
const screenCount = 2;
const created = [];
function makeWidget(type, preset) {
    return { type, config: {launcherPreset: preset},
        readConfig(key, fallback) { return this.config[key] ?? fallback; },
        writeConfig(key, value) { this.config[key] = value; } };
}
const previous = PRESETS.map((preset, screen) => ({screen, widgetIds: [1],
    widgetById() { return makeWidget('org.kde.mac-tahoe-liquid-kde.launcher', preset); },
    remove() {} }));
function panels() { return created.length ? created : previous; }
function Panel() {
    this.items = [];
    this.widgetIds = [];
    this.addWidget = type => {
        this.widgetIds.push(this.items.length);
        const item = makeWidget(type); this.items.push(item); return item;
    };
    this.widgetById = id => this.items[id];
    created.push(this);
}
'''.replace("PRESETS", json.dumps(presets))
    output = '''
console.log(JSON.stringify(created.filter(p => p.location === 'bottom').map(p => ({
    preset: p.items.find(w => w.type === 'org.kde.mac-tahoe-liquid-kde.launcher').config.launcherPreset,
    pins: p.items.find(w => w.type === 'org.kde.mac.tahoe.liquid.icontasks').config.launchers
}))));
'''
    result = subprocess.run([node, "-e", harness + script + output],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("first", [1, 2])
def test_installer_round_trip_replaces_other_edition_and_preserves_same_edition(
        transition, sandbox, monkeypatch, first):
    select, widget, installed = transition
    select(first)
    # Legacy install: its staged package is the only evidence of its edition.
    shutil.copytree(widget, installed)
    defaults.apply_launcher_default(installed)
    pins = ["applications:browser.desktop", "applications:files.desktop"]
    monkeypatch.setattr(layout, "_capture_pinned_launchers", lambda: pins)
    saved = [1, 2]  # Explicit choices on two screens must yield to a new edition.
    results = []

    def evaluate(script):
        results[:] = execute_layout(script, saved)
        return True
    monkeypatch.setattr(layout, "_evaluate_layout_script", evaluate)

    for target in (3 - first, first):
        outgoing = "MacGoldenGate" if target == 1 else "MacTahoe"
        select(target)
        assert plasmoids._install_launcher_package(widget)
        assert defaults.applied_edition(sandbox) == outgoing
        # Staging again (--no-apply-theme or retry) must retain the old edition.
        assert plasmoids._install_launcher_package(widget)
        assert defaults.applied_edition(sandbox) == outgoing
        monkeypatch.setattr(layout, "_wait_for_layout_install", lambda: False)
        layout.install()
        assert defaults.applied_edition(sandbox) == outgoing
        monkeypatch.setattr(layout, "_wait_for_layout_install", lambda: True)
        layout.install()
        assert [result["preset"] for result in results] == [target, target]
        assert all(result["pins"] == ",".join(pins) for result in results)
        assert defaults.applied_edition(sandbox) == defaults.edition_name()
        # Reinstalling the same edition preserves subsequent explicit choices.
        assert plasmoids._install_launcher_package(widget)
        layout.install()
        assert [result["preset"] for result in results] == saved


@pytest.mark.parametrize("first", ["MacTahoe", "MacGoldenGate"])
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_wallpaper_round_trip_updates_managed_screen_only(repo, sandbox, monkeypatch, first, mode):
    monkeypatch.setattr(theme_switch, "__file__", str(sandbox / "theme_switch.py"))
    monkeypatch.setenv("XDG_DATA_HOME", str(repo / "src/offline"))
    monkeypatch.setenv("FEAT_WALLPAPERS", "true")
    monkeypatch.setenv("MTTKDE_EXISTING_INSTALL", "true")
    monkeypatch.delenv("MTTKDE_RESET_WALLPAPERS", raising=False)
    wallpaper = lambda edition: (repo / "src/offline/wallpapers" / edition).as_uri()
    current = [{"screen": 0, "image": wallpaper(first)},
               {"screen": 1, "image": "file:///pictures/my-background.jpg"}]
    state = theme_switch._empty_wallpaper_state()
    state.update(initialized=True, enabled=True, last_applied=current, user_screens=[1])
    theme_switch._save_wallpaper_state(state)
    snapshots = []
    monkeypatch.setattr(theme_switch, "_apply_wallpaper_snapshot", lambda value:
                        snapshots.append(value) or True)
    other = "MacGoldenGate" if first == "MacTahoe" else "MacTahoe"
    for target in (other, first):
        (sandbox / "defaults.json").write_text(json.dumps({"wallpaper": target}))
        assert theme_switch._apply_wallpaper(mode, context="install", current_snapshot=current)
        assert snapshots[-1] == [{"screen": 0, "image": wallpaper(target)}, current[1]]
        current = snapshots[-1]
        assert theme_switch._load_wallpaper_state()["user_screens"] == [1]


def test_invalid_edition_state_stops_before_replacing_package(transition, sandbox):
    select, widget, installed = transition
    select(1)
    shutil.copytree(widget, installed)
    path = defaults.edition_state_file(sandbox)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("damaged")
    before = (installed / "contents/ui/MainView.qml").read_bytes()
    select(2)
    with pytest.raises(ValueError, match="Invalid launcher edition state"):
        plasmoids._install_launcher_package(widget)
    assert (installed / "contents/ui/MainView.qml").read_bytes() == before


def test_failed_package_copy_keeps_outgoing_edition_for_retry(transition, sandbox, monkeypatch):
    select, widget, installed = transition
    select(1)
    shutil.copytree(widget, installed)
    defaults.apply_launcher_default(installed)
    select(2)
    monkeypatch.setattr(plasmoids, "install_tree", lambda *args: False)
    assert not plasmoids._install_launcher_package(widget)
    assert defaults.applied_edition(sandbox) == "MacTahoe"


def test_uninstall_clears_edition_only_after_layout_removal(transition, sandbox, monkeypatch):
    defaults.record_applied_edition(sandbox, "MacGoldenGate")
    monkeypatch.setattr(layout, "_layout_has_any_theme_widget", lambda: True)
    monkeypatch.setattr(layout, "_reset_plasmashellrc", lambda: False)
    monkeypatch.setattr(layout, "_layout_looks_reset", lambda: False)
    monkeypatch.setattr(layout, "_capture_pinned_launchers", lambda: [])
    monkeypatch.setattr(layout, "_reset_with_pins", lambda pins: False)
    layout.uninstall()
    assert defaults.applied_edition(sandbox) == "MacGoldenGate"
    monkeypatch.setattr(layout, "_reset_with_pins", lambda pins: True)
    layout.uninstall()
    assert defaults.applied_edition(sandbox) is None


@pytest.mark.parametrize("target", [1, 2])
def test_install_without_legacy_edition_evidence_selects_new_defaults(
        transition, sandbox, monkeypatch, target):
    select, widget, installed = transition
    shutil.copytree(widget, installed)
    old_view = installed / "contents/ui/MainView.qml"
    old_view.write_text("// An old launcher without edition support\n")
    select(target)
    assert plasmoids._install_launcher_package(widget)
    assert defaults.applied_edition(sandbox) == "unknown"
    scripts = []
    monkeypatch.setattr(layout, "_capture_pinned_launchers", lambda: [])
    monkeypatch.setattr(layout, "_evaluate_layout_script", lambda script: scripts.append(script) or True)
    layout.install()
    assert [item["preset"] for item in execute_layout(scripts[-1], [3 - target, 3 - target])] == [target, target]
    assert defaults.applied_edition(sandbox) == defaults.edition_name()


@pytest.mark.parametrize("marker", ["missing", "stale"])
@pytest.mark.parametrize("target", [1, 2])
def test_older_release_replacing_package_invalidates_edition_record(
        transition, sandbox, monkeypatch, target, marker):
    select, widget, installed = transition
    # A record from this edition, then a release that predates edition tracking
    # installs the other edition's package without updating that record.
    select(target)
    defaults.record_applied_edition(sandbox, defaults.edition_name())
    select(3 - target)
    shutil.copytree(widget, installed)
    defaults.apply_launcher_default(installed)
    if marker == "missing":
        (installed / defaults.EDITION_MARKER).unlink()
    else:
        (installed / defaults.EDITION_MARKER).write_text(
            ("MacGoldenGate" if target == 2 else "MacTahoe") + "\n")
    select(target)
    assert plasmoids._install_launcher_package(widget)
    assert defaults.applied_edition(sandbox) == "unknown"
    scripts = []
    monkeypatch.setattr(layout, "_capture_pinned_launchers", lambda: [])
    monkeypatch.setattr(layout, "_evaluate_layout_script", lambda script: scripts.append(script) or True)
    layout.install()
    assert [item["preset"] for item in execute_layout(scripts[-1], [3 - target, 3 - target])] == [target, target]
    assert defaults.applied_edition(sandbox) == defaults.edition_name()
