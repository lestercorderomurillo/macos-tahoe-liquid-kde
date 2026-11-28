import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import org.kde.kirigami as Kirigami

RowLayout {
    id: searchFieldBar
	spacing: !searchFieldBar.detachedWindow ? 0 : Kirigami.Units.smallSpacing

    property alias textField: textField
    readonly property bool menuOpen: menuButton.menuOpen
    property bool detachedWindow: false
    readonly property bool goldenGateCapsule: main.goldenGateEdition && main.detachedSearch
    readonly property color textColor: main.labelColor(textField,
        textField.leftPadding + Math.min(Math.max(0, textField.width - textField.leftPadding - textField.rightPadding),
            textField.text.length ? Math.max(1, textField.contentWidth) : placeholderMetrics.advanceWidth) / 2,
        "transparent", detachedWindow,
        goldenGateCapsule ? "white" : main.textColor,
        textField.text.length ? textField.contentWidth : placeholderMetrics.advanceWidth, searchFieldBar)
    TextMetrics {
        id: placeholderMetrics
        font: textField.font
        text: textField.placeholderText
    }
    readonly property color dimmedTextColor: (main.goldenGateLight || goldenGateCapsule)
        ? textColor : Qt.rgba(textColor.r, textColor.g, textColor.b, 0.85)
    function closeMenu() { menuButton.closeMenu(); }

    Kirigami.Icon {
        id: searchIcon
        opacity: main.clipboardMode ? 0.68 : 1
        scale: !searchFieldBar.detachedWindow && !main.clipboardMode ? 1.15 : 1
        Layout.leftMargin: !searchFieldBar.detachedWindow ? 1 : 0
        Layout.rightMargin: 0
        Layout.preferredWidth: searchFieldBar.detachedWindow ? Kirigami.Units.gridUnit * 2 : 38
        Layout.preferredHeight: Layout.preferredWidth
        source: main.clipboardMode ? Qt.resolvedUrl('icons/ClipboardIcon.svg') : Qt.resolvedUrl('icons/AppsIcon.svg')
        isMask: true
        color: searchFieldBar.dimmedTextColor
    }

    TextField {
        id: textField
        Layout.fillHeight: true
        Layout.fillWidth: true
        Layout.leftMargin: !searchFieldBar.detachedWindow ? -2 : 0
        font.family: !searchFieldBar.detachedWindow ? "SF Pro Display" : Kirigami.Theme.defaultFont.family
        font.pointSize: main.textSize * (2)
        font.weight: Kirigami.Theme.defaultFont.weight
        font.letterSpacing: !searchFieldBar.detachedWindow ? -0.55 : 0
        color: searchFieldBar.textColor

        Component {
            id: glowingCursor
            SearchCursor { field: textField }
        }
        Binding {
            target: textField
            property: "cursorDelegate"
            when: searchFieldBar.goldenGateCapsule && !Kirigami.Settings.tabletMode
            value: glowingCursor
        }
        Component.onCompleted: text = main.searchText
        Connections {
            target: main
            function onSearchTextChanged() {
                if (textField.text !== main.searchText)
                    textField.text = main.searchText;
            }
        }
        placeholderText: main.clipboardMode ? i18n("Clipboard") : !searchFieldBar.detachedWindow ? i18n("Applications") : i18n("Apps")
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

    MenuButton {
        id: menuButton
        foregroundColor: searchFieldBar.textColor
        Layout.alignment: Qt.AlignVCenter
        Layout.rightMargin: !searchFieldBar.detachedWindow ? -3.5 : 0
    }
}
