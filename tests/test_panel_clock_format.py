"""Render the shipped menu-bar clock at the contributor's reference time."""
import json
import os
import subprocess

import pytest


@pytest.mark.parametrize("locale,regional,override,explicit", [
    ("fr_FR", "Dim Nov 22  15:49", 0, "Dim Nov 22  3:49\u2009PM"),
    ("en_US", "Sun Nov 22  3:49\u2009PM", 2, "Sun Nov 22  15:49"),
])
def test_localized_panel_clock(offline, tmp_path, launcher_popup_module, locale, regional, override, explicit):
    # Substitute only the time source. QML still uses the installed Qt locale data.
    clock = tmp_path / "org/kde/plasma/clock"
    clock.mkdir(parents=True)
    (clock / "qmldir").write_text("module org.kde.plasma.clock\nClock 1.0 Clock.qml\n")
    (clock / "Clock.qml").write_text("""
import QtQuick
QtObject {
    property string timeZone
    property bool trackSeconds
    readonly property bool valid: true
    readonly property date dateTime: new Date(2026, 10, 22, 15, 49)
}
""")
    ui = offline / "plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui"
    probe = tmp_path / "clock.qml"
    probe.write_text(f"""
import QtQuick
import "{ui.as_uri()}" as Panel
Item {{
    property var settings: ({{use24hFormat: 1, showSeconds: 0}})
    Panel.PanelClockText {{ id: clock }}
    Component.onCompleted: Qt.callLater(function() {{
        const regional = clock.text;
        settings = ({{use24hFormat: {override}, showSeconds: 0}});
        console.log("CLOCK_RESULT", JSON.stringify([regional, clock.text]));
        Qt.exit(0);
    }})
}}
""")
    result = subprocess.run([launcher_popup_module.parent / "dockgeometryprobe", probe],
                            env=os.environ | {"QT_FORCE_STDERR_LOGGING": "1", "LC_ALL": locale + ".UTF-8", "QT_QPA_PLATFORM": "offscreen",
                                "QML_IMPORT_PATH": os.pathsep.join(map(str, (tmp_path, launcher_popup_module)))},
                            capture_output=True, text=True, timeout=12, check=True)
    line = next((s for s in result.stderr.splitlines() if "CLOCK_RESULT " in s), None)
    assert line, result.stderr
    assert json.loads(line.split("CLOCK_RESULT ", 1)[1]) == [regional, explicit]
