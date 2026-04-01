/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property alias cfg_compactView: compactViewRadioButton.checked
    property alias cfg_allScreens: allScreensCheckBox.checked

    Kirigami.FormLayout {
        QQC2.RadioButton {
            id: compactViewRadioButton
            text: i18n("Use single button for application menu")
        }
        QQC2.RadioButton {
            id: fullViewRadioButton
            checked: !compactViewRadioButton.checked
            text: i18n("Show full application menu")
        }
        QQC2.CheckBox {
            id: allScreensCheckBox
            text: i18n("Show menus for apps on different screens")
        }
    }
}
