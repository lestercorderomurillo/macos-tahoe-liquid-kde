// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import QtQuick.Window

// Share the space actually available in one panel, including when it is
// shorter than the preferred Dock length. Desktop widgets do not participate.
QtObject {
    id: root
    required property Item applet
    property bool active: true
    property bool vertical: false
    property bool taskManager: false
    property int count: 1
    property real spacing: 0
    property real size: vertical ? applet.width : applet.height
    readonly property var panelWindow: applet.Window.window
    onActiveChanged: DockMetrics.schedule()
    onVerticalChanged: DockMetrics.schedule()
    onCountChanged: DockMetrics.schedule()
    onSpacingChanged: DockMetrics.schedule()
    onPanelWindowChanged: DockMetrics.schedule()
    property Connections geometry: Connections {
        target: root.applet
        function onWidthChanged() { DockMetrics.schedule(); }
        function onHeightChanged() { DockMetrics.schedule(); }
        function onVisibleChanged() { DockMetrics.schedule(); }
    }
    Component.onCompleted: DockMetrics.add(root)
    Component.onDestruction: DockMetrics.remove(root)
}
