// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.clock as PlasmaClock
import org.kde.mac.tahoe.launcher as Native

Text {
    id: clockText
    readonly property var clockLocale: Qt.locale()
    readonly property bool clockValid: localClock.valid
    readonly property bool withSeconds: parent.settings.showSeconds === 2
    readonly property bool twelveHour: parent.settings.use24hFormat === Qt.Unchecked
        || (parent.settings.use24hFormat === Qt.PartiallyChecked && /ap/i.test(clockLocale.timeFormat(Locale.ShortFormat)))
    readonly property string hours: twelveHour ? "h:mm" : "HH:mm"
    PlasmaClock.Clock {
        id: localClock
        timeZone: "Local"
        trackSeconds: clockText.withSeconds
    }
    // macOS writes the date as "Sun Nov 22" ("Dim Nov 22" in French): short
    // day and month names with a capital and no abbreviation dot, then the
    // day of the month. Qt's French short names are "dim." and "nov.".
    function shortName(name) {
        const bare = name.replace(/\.$/, "");
        return bare.charAt(0).toLocaleUpperCase(clockLocale.name) + bare.slice(1);
    }
    readonly property date now: localClock.dateTime
    text: shortName(clockLocale.dayName(now.getDay(), Locale.ShortFormat)) + " "
        + shortName(clockLocale.monthName(now.getMonth(), Locale.ShortFormat)) + " "
        + clockLocale.toString(now, "d") + "  "
        + clockLocale.toString(now, hours + (withSeconds ? ":ss" : "") + (twelveHour ? "\u2009AP" : ""))
    Accessible.ignored: true
    textFormat: Text.PlainText
    font.family: "SF Pro Text"
    font.pixelSize: 13
    font.weight: Font.Medium
    font.letterSpacing: -0.33
    color: ink.foreground
    Native.WallpaperInk {
        profileId: "panel.clock"
        id: ink
        item: clockText
        base: Kirigami.Theme.textColor
        active: clockText.parent?.wallpaperTint ?? false
    }
}
