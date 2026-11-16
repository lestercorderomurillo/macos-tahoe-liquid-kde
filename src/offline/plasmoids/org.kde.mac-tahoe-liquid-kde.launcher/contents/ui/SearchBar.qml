import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import org.kde.kirigami as Kirigami

RowLayout {
    id: searchFieldBar
	spacing: main.tahoeStyle ? 0 : Kirigami.Units.smallSpacing

    property alias textField: textField
    property alias showMenuButton: menuButton.visible
    readonly property bool menuOpen: menuButton.menuOpen
    readonly property color textColor: main.textColor
    readonly property color dimmedTextColor: main.goldenGateLight
        ? textColor : Qt.rgba(textColor.r, textColor.g, textColor.b, 0.85)
    function closeMenu() { menuButton.closeMenu(); }

    Kirigami.Icon {
        id: searchIcon
        scale: main.tahoeStyle ? 1.15 : 1
        layer.enabled: true
        layer.effect: GlassTextShadow {
            haloOpacity: main.goldenGateLight ? 0.65 : 0.35
            radius: main.goldenGateLight ? 3 : 2
            samples: main.goldenGateLight ? 13 : 9
        }
        Layout.leftMargin: main.tahoeStyle ? 1 : 0
        Layout.rightMargin: 0
        Layout.preferredWidth: main.detachedSearch ? Kirigami.Units.gridUnit * 2 : (main.tahoeStyle ? 38 : Kirigami.Units.iconSizes.medium)
        Layout.preferredHeight: Layout.preferredWidth
        source: main.clipboardMode ? Qt.resolvedUrl('icons/ClipboardIcon.svg') : Qt.resolvedUrl('icons/AppsIcon.svg')
        isMask: true
        color: searchFieldBar.dimmedTextColor
    }

    TextField {
        id: textField
        layer.enabled: true
        layer.effect: GlassTextShadow {
            haloOpacity: main.goldenGateLight ? 0.65 : 0.35
            radius: main.goldenGateLight ? 3 : 2
            samples: main.goldenGateLight ? 13 : 9
        }
        Layout.fillHeight: true
        Layout.fillWidth: true
        Layout.leftMargin: main.tahoeStyle ? -2 : 0
        font.family: main.tahoeStyle ? "SF Pro Display" : Kirigami.Theme.defaultFont.family
        font.pointSize: main.textSize * (main.detachedSearch ? 2 : (main.tahoeStyle ? 2 : 1))
        font.weight: Kirigami.Theme.defaultFont.weight
        font.letterSpacing: main.tahoeStyle ? -0.55 : 0
        color: searchFieldBar.textColor

        Component.onCompleted: text = main.searchText
        Connections {
            target: main
            function onSearchTextChanged() {
                if (textField.text !== main.searchText)
                    textField.text = main.searchText;
            }
        }
        placeholderText: main.clipboardMode ? i18n("Clipboard") : main.tahoeStyle ? i18n("Applications") : i18n("Apps")
        placeholderTextColor: searchFieldBar.dimmedTextColor
        background: Rectangle{
            color: "transparent"
        }
        focus: true
        onTextChanged: {
            if (main.searchBar === searchFieldBar) {
                main.searchText = text;
                textField.forceActiveFocus(Qt.ShortcutFocusReason);
            }
        }

        Keys.onPressed: event => {
            if ((event.modifiers & (Qt.ControlModifier | Qt.MetaModifier)) && event.key === Qt.Key_4) {
                main.showClipboard(true);
                event.accepted = true;
                return;
            }
            if ((event.modifiers & (Qt.ControlModifier | Qt.MetaModifier)) && event.key === Qt.Key_1) {
                main.showClipboard(false);
                event.accepted = true;
                return;
            }
            if (event.key == Qt.Key_Escape) {
                event.accepted = true;
                if (searching) {
                    clear();
                } else if (main.clipboardMode) {
                    main.showClipboard(false);
                } else {
                    root.toggle()
                }
            }

        }
    }

    ToolButton {
        visible: main.clipboardMode
        Layout.preferredWidth: 28
        Layout.preferredHeight: 28
        Accessible.name: i18n("Clipboard options")
        contentItem: Item {
            Row {
                anchors.centerIn: parent
                spacing: 2.1
                Repeater {
                    model: 3
                    Rectangle { width: 2.6; height: 2.6; radius: 1.3; color: main.dimmedTextColor }
                }
            }
        }
        background: Rectangle {
            anchors.centerIn: parent
            width: 22
            height: 22
            radius: 11
            color: parent.hovered ? main.contrastBgColor : "transparent"
            border.width: 1.25
            border.color: main.dimmedTextColor
        }
        onClicked: main.clipboardList.more(this, null)
    }

    MenuButton {
        id: menuButton
        visible: !main.clipboardMode
        foregroundColor: searchFieldBar.textColor
        Layout.alignment: Qt.AlignVCenter
        Layout.rightMargin: main.tahoeStyle ? -3.5 : 0
    }
}
