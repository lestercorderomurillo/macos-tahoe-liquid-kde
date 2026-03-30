import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: configPage

    property alias cfg_emptyIcon: emptyField.text
    property alias cfg_fullIcon: fullField.text

    Kirigami.FormLayout {

        // ── empty icon ──────────────────────────────────────────
        ColumnLayout {
            Kirigami.FormData.label: "Empty trash icon:"
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Icon {
                    source: emptyField.text || "user-trash"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                }

                QQC2.TextField {
                    id: emptyField
                    Layout.fillWidth: true
                    placeholderText: "user-trash"
                }
            }
        }

        // ── full icon ───────────────────────────────────────────
        ColumnLayout {
            Kirigami.FormData.label: "Full trash icon:"
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Icon {
                    source: fullField.text || "user-trash-full"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                    Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                }

                QQC2.TextField {
                    id: fullField
                    Layout.fillWidth: true
                    placeholderText: "user-trash-full"
                }
            }
        }

        Kirigami.Separator {
            Kirigami.FormData.isSection: true
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Enter any icon name from your current icon theme."
        }

        QQC2.Button {
            icon.name: "configure"
            text: "Trash Settings\u2026"
            onClicked: KCM.KCMLauncher.open("kcm_trash")
        }
    }
}
