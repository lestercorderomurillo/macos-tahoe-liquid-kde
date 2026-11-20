// SPDX-License-Identifier: GPL-3.0-or-later
// macOS Tahoe style lock screen: date and large clock at the top,
// avatar, name and a glass password pill at the bottom.
import QtQuick
import QtQuick.Controls as QQC
import Qt5Compat.GraphicalEffects

Item {
    id: root
    property bool debug: false
    property string notification
    signal clearPassword()
    signal notificationRepeated()
    property bool viewVisible: false
    implicitWidth: 800
    implicitHeight: 600

    readonly property string displayFamily: "SF Pro Display"
    readonly property string textFamily: "SF Pro Text"
    property date now: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.now = new Date() }

    onClearPassword: { password.text = ""; password.forceActiveFocus(); }

    Connections {
        target: authenticator
        function onFailed(kind) {
            if (kind !== 0) return;
            password.text = "";
            message.text = i18nd("kscreenlocker_greet", "Incorrect password");
            shake.restart();
            authenticator.startAuthenticating();
        }
        function onSucceeded() { Qt.quit(); }
        function onPromptForSecretChanged() { password.forceActiveFocus(); }
    }
    Component.onCompleted: { authenticator.startAuthenticating(); password.forceActiveFocus(); }

    // Soft darkening at top and bottom so white text stays legible on any wallpaper.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.22) }
            GradientStop { position: 0.35; color: Qt.rgba(0, 0, 0, 0.0) }
            GradientStop { position: 0.7; color: Qt.rgba(0, 0, 0, 0.0) }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.28) }
        }
    }

    // macOS Tahoe glass clock: SF Pro Display Bold with slightly rounded
    // corners, a translucent white body over the wallpaper and a ~1 px bevel
    // (light top-left, softer bottom-right). All layers are full screen so the
    // masks line up exactly.
    readonly property real clockY: height * 0.07 + dateLabel.implicitHeight + 2
    Rectangle { id: whiteFill; anchors.fill: parent; color: "white"; visible: false }
    component RoundGlyphs: Item {
        property real dx: 0
        property real dy: 0
        property string label
        property real size: 110
        property real yPos: 0
        property real round: 8
        property int weight: Font.Bold
        anchors.fill: parent
        visible: false
        layer.enabled: true
        Item {
            id: raw; anchors.fill: parent; visible: false; layer.enabled: true
            Text {
                x: (parent.width - width) / 2 + dx; y: yPos + dy
                text: label
                color: "white"
                font.family: "SF Pro Display"; font.weight: weight; font.pointSize: size
                font.capitalization: Font.Capitalize
            }
        }
        FastBlur { id: soft; anchors.fill: parent; source: raw; radius: round; visible: false }
        ThresholdMask { anchors.fill: parent; source: whiteFill; maskSource: soft; threshold: 0.5; spread: 0.35 }
    }
    // One glass treatment for the clock and the date.
    component GlassText: Item {
        property string label
        property real size: 110
        property real yPos: 0
        property real round: 8
        property real shift: 0.7
        property real fillOpacity: 0.38
        property real edgeLight: 0.4
        property real edgeSoft: 0.24
        property int weight: Font.Bold
        anchors.fill: parent
        RoundGlyphs { id: g; label: parent.label; size: parent.size; yPos: parent.yPos; round: parent.round; weight: parent.weight }
        RoundGlyphs { id: gDR; label: parent.label; size: parent.size; yPos: parent.yPos; round: parent.round; weight: parent.weight; dx: parent.shift; dy: parent.shift }
        RoundGlyphs { id: gUL; label: parent.label; size: parent.size; yPos: parent.yPos; round: parent.round; weight: parent.weight; dx: -parent.shift; dy: -parent.shift }
        BrightnessContrast {
            anchors.fill: parent
            source: typeof wallpaper !== "undefined" ? wallpaper : null
            visible: source !== null
            contrast: 0.3
            layer.enabled: true
            layer.effect: OpacityMask { maskSource: g }
        }
        OpacityMask { anchors.fill: parent; source: whiteFill; maskSource: g; opacity: parent.fillOpacity }
        OpacityMask { anchors.fill: parent; source: g; maskSource: gDR; invert: true; opacity: parent.edgeLight }
        OpacityMask { anchors.fill: parent; source: g; maskSource: gUL; invert: true; opacity: parent.edgeSoft }
    }
    Text { id: dateLabel; visible: false; text: "X"; font.family: "SF Pro Display"; font.weight: Font.DemiBold; font.pointSize: 20 }
    GlassText { label: Qt.locale().toString(root.now, "dddd d MMMM"); size: 20; weight: Font.DemiBold; yPos: root.height * 0.07 + 14; round: 1.6; shift: 0.5; fillOpacity: 0.6; edgeLight: 0.14; edgeSoft: 0.08 }
    GlassText { label: Qt.locale().toString(root.now, "HH:mm"); size: 110; yPos: root.clockY }

    Column {
        id: login
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: parent.height * 0.07
        spacing: 10
        transform: Translate { id: shakeX }
        SequentialAnimation {
            id: shake
            loops: 2
            NumberAnimation { target: shakeX; property: "x"; to: -10; duration: 50 }
            NumberAnimation { target: shakeX; property: "x"; to: 10; duration: 100 }
            NumberAnimation { target: shakeX; property: "x"; to: 0; duration: 50 }
        }

        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 64; height: 64
            Image {
                id: avatar
                anchors.fill: parent
                source: kscreenlocker_userImage !== "" ? "file://" + kscreenlocker_userImage : ""
                fillMode: Image.PreserveAspectCrop
                visible: false
            }
            Rectangle { id: avatarMask; anchors.fill: parent; radius: width / 2; visible: false }
            OpacityMask { anchors.fill: parent; source: avatar; maskSource: avatarMask; visible: avatar.status === Image.Ready }
            Rectangle {
                anchors.fill: parent; radius: width / 2
                visible: avatar.status !== Image.Ready
                color: Qt.rgba(1, 1, 1, 0.3)
                Text { anchors.centerIn: parent; text: kscreenlocker_userName.charAt(0).toUpperCase(); color: "white"; font.family: root.displayFamily; font.pixelSize: 28; font.weight: Font.DemiBold }
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: kscreenlocker_userName
            font.family: root.textFamily; font.weight: Font.DemiBold; font.pixelSize: 15
            color: "white"
        }
        QQC.TextField {
            id: password
            anchors.horizontalCenter: parent.horizontalCenter
            width: 200; height: 30
            echoMode: TextInput.Password
            passwordCharacter: "●"
            horizontalAlignment: TextInput.AlignHCenter
            placeholderText: i18nd("kscreenlocker_greet", "Enter Password")
            placeholderTextColor: Qt.rgba(1, 1, 1, 0.6)
            color: "white"
            font.family: root.textFamily; font.pixelSize: 13
            focus: true
            background: Rectangle { radius: height / 2; color: Qt.rgba(1, 1, 1, 0.22); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.28) }
            onTextEdited: message.text = ""
            onAccepted: if (text.length) authenticator.respond(text)
            Keys.onEscapePressed: text = ""
        }
        Text {
            id: message
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.notification.length ? root.notification : ""
            font.family: root.textFamily; font.pixelSize: 12
            color: Qt.rgba(1, 1, 1, 0.85)
            height: 16
        }
    }
}
