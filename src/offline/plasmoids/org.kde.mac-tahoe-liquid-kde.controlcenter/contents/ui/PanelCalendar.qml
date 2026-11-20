// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import "ControlStyle.js" as Style

Item {
    id: calendar
    required property Item clock

    readonly property Item clockTip: {
        for (let item = clock?.compactRepresentationItem; item; item = item.parent) {
            if (item instanceof PlasmaCore.ToolTipArea) return item
        }
        return null
    }
    Binding {
        target: calendar.clockTip
        property: "active"
        when: calendar.clockTip !== null && popup.visible
        value: false
    }

    MouseArea {
        parent: calendar.clock
        anchors.fill: parent
        z: 10
        activeFocusOnTab: true
        Accessible.name: calendar.clock?.toolTipMainText ?? ""
        Accessible.role: Accessible.Button
        Accessible.onPressAction: popup.visible = !popup.visible
        Keys.onSpacePressed: popup.visible = !popup.visible
        Keys.onReturnPressed: popup.visible = !popup.visible
        acceptedButtons: Qt.LeftButton
        onClicked: popup.visible = !popup.visible
    }

    ControlDialog {
        id: popup
        title: "mttkde-calendar"
        visualParent: calendar.clock
        location: calendar.clock?.plasmoid.location ?? PlasmaCore.Types.TopEdge
        surfaces: [{x: 0, y: 0, width: card.width, height: card.height, radius: card.cornerRadius}]
        onVisibleChanged: if (visible) {
            calendar.clockTip?.hideToolTip()
            card.refresh()
            card.offset = 0
            requestActivate()
            card.forceActiveFocus()
        }

        mainItem: NotificationSurface {
            id: card
            property date today: new Date()
            property int offset: 0
            readonly property date first: new Date(today.getFullYear(), today.getMonth() + offset, 1, 12)
            readonly property int leading: first.getDay()
            readonly property int count: new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate()
            readonly property int weeks: Math.ceil((leading + count) / 7)
            readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5

            readonly property color red: dark ? "#ff494e" : "#ff383e"
            width: 328
            height: 328
            cornerRadius: 36
            padding: 0
            leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0
            Accessible.role: Accessible.Grouping
            Accessible.name: first.toLocaleDateString(Qt.locale(), "MMMM yyyy")

            function refresh() { today = new Date() }
            function openAgenda() {
                popup.visible = false
                if (calendar.clock) calendar.clock.expanded = true
            }
            Timer { interval: 30000; repeat: true; running: popup.visible; onTriggered: card.refresh() }
            Keys.onLeftPressed: offset--
            Keys.onRightPressed: offset++
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Home) { offset = 0; event.accepted = true }
            }
            Keys.onEscapePressed: popup.visible = false
            Keys.onReturnPressed: openAgenda()
            WheelHandler {
                onWheel: event => {
                    if (event.angleDelta.y !== 0) card.offset += event.angleDelta.y > 0 ? -1 : 1
                }
            }

            Text {
                x: 36
                y: 36
                text: Qt.locale().standaloneMonthName(card.first.getMonth(), Locale.LongFormat).toLocaleUpperCase()
                color: card.red
                font.family: Style.family
                font.weight: Font.DemiBold
                font.pixelSize: 20
                TapHandler { onTapped: card.openAgenda() }
            }
            Grid {
                x: 26
                y: 64
                columns: 7
                spacing: 0
                Repeater {
                    model: 7 + card.weeks * 7
                    delegate: Item {
                        required property int index
                        readonly property bool heading: index < 7
                        readonly property int weekday: index % 7
                        readonly property int day: index - 6 - card.leading
                        readonly property bool valid: !heading && day > 0 && day <= card.count
                        readonly property bool current: valid && card.offset === 0 && day === card.today.getDate()
                        width: 39.2
                        height: heading ? 40 : Math.min(38.4, 198 / card.weeks)
                        Rectangle {
                            anchors.centerIn: parent
                            width: Math.min(36, parent.height)
                            height: width
                            radius: width / 2
                            color: card.red
                            visible: parent.current
                        }
                        Text {
                            id: dayLabel
                            anchors.centerIn: parent
                            text: parent.heading ? Qt.locale().standaloneDayName(parent.weekday, Locale.NarrowFormat)
                                : parent.valid ? Number(parent.day).toLocaleString(Qt.locale(), 'f', 0) : ""
                            color: parent.current ? "white" : popup.foregroundFor(dayLabel, Kirigami.Theme.textColor)
                            style: parent.current ? Text.Normal : Text.Raised
                            styleColor: color.hslLightness < 0.5 ? "#70ffffff" : "#70000000"
                            opacity: !parent.current && (parent.weekday === 0 || parent.weekday === 6) ? 0.8 : 1
                            font.family: Style.family
                            font.pixelSize: 20
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }
        }
    }
}
