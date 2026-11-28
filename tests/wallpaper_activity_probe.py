"""Exercise real Plasma containments on two virtual outputs and a private session bus."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/scripts"))
from desktop_widget_settings import stage_configuration_route

CALENDAR = "com.jaxparrow07.macoswidgets.calendar"
ICON = "org.example.wallpaper-contrast-probe"
PLASMA = ["org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript"]
ACTIVITY = ["org.kde.ActivityManager", "/ActivityManager/Activities"]


def wait(read, description):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        value = read()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError(description)


def dbus(service, *args):
    return subprocess.check_output(["qdbus6", *service, *args], text=True, timeout=10).strip()


def stage():
    packages = Path(os.environ["XDG_DATA_HOME"]) / "plasma/plasmoids"
    ui = packages / ICON / "contents/ui"
    ui.mkdir(parents=True)
    (packages / ICON / "metadata.json").write_text(json.dumps({
        "KPlugin": {"Id": ICON, "Name": "Contrast probe"},
        "KPackageStructure": "Plasma/Applet", "X-Plasma-API-Minimum-Version": "6.0"}))
    controls = ROOT / "src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui"
    (packages / controls.parents[1].name).symlink_to(controls.parents[1], target_is_directory=True)
    shutil.copy(controls / "TrayArtwork.qml", ui)
    (ui / "main.qml").write_text("""
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.kirigami as Kirigami
PlasmoidItem {
    preferredRepresentation: fullRepresentation
    fullRepresentation: Item {
        implicitWidth: 28; implicitHeight: 28
        Kirigami.Icon { id: glyph; width: 22; height: 22; source: "audio-volume-high-symbolic" }
        TrayArtwork { id: art; glyph: glyph; wallpaperTint: true }
        Timer { interval: 150; running: true; repeat: true
            onTriggered: if (art.monochrome && glyph.isMask) console.info("CONTRAST_ICON", Plasmoid.containment.screen, glyph.color.toString())
        }
    }
}
""")
    archive = ROOT / "src/offline/desktop-widgets/liquidglass-kde-widgets.tar.zst"
    subprocess.run(["tar", "--zstd", "-xf", archive, "-C", packages, "./" + CALENDAR], check=True)
    stage_configuration_route(packages / CALENDAR)
    # Observe one production weekday label with the bundled Follow System default.
    main = packages / CALENDAR / "contents/ui/main.qml"
    label = "sourceText: root.weekdayShort[index]"
    source = main.read_text()
    assert source.count(label) == 1
    main.write_text(source.replace(label, label + """
                                Timer { interval: 150; repeat: true; running: index === 1 && parent.visible
                                    onTriggered: console.info("CONTRAST_WIDGET", Plasmoid.containment.screen, parent.color.toString(), plasmoid.configuration.appearance)
                                }"""))


def exercise(log):
    wait(lambda: "org.kde.plasmashell" in dbus([]).split(), "Plasma did not start")
    def ready():
        return dbus(PLASMA, 'print(screenCount === 2 && desktops().length >= 2)')
    wait(lambda: ready() == "true", "Two desktop views did not start")
    a = dbus(ACTIVITY, "CurrentActivity")
    b = dbus(ACTIVITY, "AddActivity", "Opposite wallpapers")

    def setup(first, panels):
        dbus(PLASMA, """
        for (let i = 0; i < 2; ++i) {
            const d = desktopForScreen(i);
            d.wallpaperPlugin = 'org.kde.color';
            d.currentConfigGroup = ['Wallpaper', 'org.kde.color', 'General'];
            d.writeConfig('Color', i === 0 ? '%s' : '%s');
            d.addWidget('%s');
            %s
        }""" % (first, "#ffffff" if first == "#000000" else "#000000", CALENDAR,
                f"const p = new Panel(); p.screen = i; p.location = 'top'; p.addWidget('{ICON}');" if panels else ""))

    def switch(activity):
        assert dbus(ACTIVITY, "SetCurrentActivity", activity) == "true"
        script = f"""const ids = desktopsForActivity('{activity}').map(d => d.id);
                     print([0, 1].every(i => ids.includes(desktopForScreen(i).id)))"""
        wait(lambda: dbus(PLASMA, script) == "true", "Activity switch")

    def settle(condition, reason):
        # Require fresh reports from both consumers on both outputs twice, so
        # a transient color during creation or a stale Activity cannot pass.
        latest = {}
        with log.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            def sample():
                for raw in stream.readlines():
                    match = re.search(rb"CONTRAST_(ICON|WIDGET) ([01]) (#[0-9a-f]{6})(?: (\d+))?$", raw.rstrip())
                    if match:
                        kind, screen, color, appearance = match.groups()
                        if kind == b"WIDGET":
                            assert appearance == b"2", raw
                        latest[kind.decode(), int(screen)] = int(color[1:3], 16)
                if len(latest) == 4 and condition(latest):
                    return latest.copy()
            wait(sample, reason)
            latest.clear()
            return wait(sample, reason)

    setup("#000000", True)
    original = settle(lambda c: all(c[k, 0] > c[k, 1] for k in ("ICON", "WIDGET")), "Per-output contrast")
    switch(b)
    setup("#ffffff", False)
    settle(lambda c: all(c[k, 0] == original[k, 1] and c[k, 1] == original[k, 0]
                         for k in ("ICON", "WIDGET")), "Reversed wallpapers")
    switch(a)
    settle(lambda c: c == original, "Return to the first Activity")


def main():
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    stage()
    env = dict(os.environ, WAYLAND_DISPLAY="test-contrast", QT_QPA_PLATFORM="wayland")
    log = runtime / "plasmashell.log"
    with ExitStack() as stack:
        def launch(command, dest, environment):
            stream = stack.enter_context(dest.open("w"))
            proc = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, env=environment)
            def stop():
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            stack.callback(stop)
        launch(["kwin_wayland", "--virtual", "--output-count", "2", "--width", "960",
                "--height", "640", "--socket", "test-contrast"], runtime / "kwin.log", os.environ)
        wait(lambda: (runtime / "test-contrast").exists(), "Virtual compositor socket")
        dbus(ACTIVITY, "CurrentActivity")
        launch(["plasmashell", "--no-respawn"], log, env)
        exercise(log)


if __name__ == "__main__":
    main()
