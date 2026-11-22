// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.clock as PlasmaClock
import org.kde.mac.tahoe.launcher as Native

Text {
    id: clockText
    readonly property bool clockValid: localClock.valid
    readonly property bool withSeconds: parent.settings.showSeconds === 2
    readonly property bool twelveHour: parent.settings.use24hFormat === Qt.Unchecked
        || (parent.settings.use24hFormat === Qt.PartiallyChecked && /ap/i.test(Qt.locale().timeFormat(Locale.ShortFormat)))
    readonly property string hours: twelveHour ? "h:mm" : "HH:mm"
    PlasmaClock.Clock {
        id: localClock
        timeZone: "Local"
        trackSeconds: clockText.withSeconds
    }
    text: Qt.locale().toString(localClock.dateTime, "ddd MMM d  " + hours
                               + (withSeconds ? ":ss" : "") + (twelveHour ? "\u2009AP" : ""))
    Accessible.ignored: true
    textFormat: Text.PlainText
    font.family: "SF Pro Text"
    font.pixelSize: 13
    font.weight: Font.Medium
    font.letterSpacing: -0.33
    color: ink.foreground
    Native.WallpaperInk {
        id: ink
        item: clockText
        base: Kirigami.Theme.textColor
        active: clockText.parent?.wallpaperTint ?? false
    }
}
