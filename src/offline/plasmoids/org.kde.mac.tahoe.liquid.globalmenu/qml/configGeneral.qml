/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    property alias cfg_compactView: compactViewRadioButton.checked
    property alias cfg_enableGenericMenu: genericMenu.checked
    property alias cfg_enableMenuSearch: menuSearch.checked
    property alias cfg_hoverOpensMenu: hoverMenus.checked
    property alias cfg_allScreens: allScreensCheckBox.checked

    Kirigami.FormLayout {
        QQC2.CheckBox {
            id: genericMenu
            text: i18n("Show common menus for applications without a menu bar")
        }
        QQC2.CheckBox {
            id: menuSearch
            text: i18n("Search application menu actions")
        }
        QQC2.CheckBox {
            id: hoverMenus
            text: i18n("Switch open menus on hover")
        }
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
