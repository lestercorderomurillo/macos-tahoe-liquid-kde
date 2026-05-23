/*
    Standalone preview harness for AboutWindow.qml.

    Used by ``src/scripts/screenshots`` to render the About panel
    outside plasmashell (where the screenshot tool can target a
    well-known window title). The mock-data helper supplies canned
    values so captured PNGs never include the maintainer's real MAC
    address / serial / hardware.

    Run directly with:
        qml6 -I src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml \
             src/scripts/preview_about.qml

    SPDX-License-Identifier: GPL-2.0-or-later
*/
import QtQuick
import QtQuick.Window

import "../offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml"

AboutWindow {
    id: about
    // Visible from the first paint — the harness has no system menu
    // to trigger ``aboutRequested`` from.
    visible: true
    title: "About This Computer (preview)"
    // Point the data source at the mock-emitter. Same about_info
    // helper, just with ``--mock`` so the JSON it emits is the canned
    // _MOCK_DATA dict instead of live hardware probing.
    fetcherCommand: "sh -c 'MAC_TAHOE_ABOUT_MOCK=1 ~/.local/bin/mac-tahoe-about-info'"
    useSystemFont: true
}
