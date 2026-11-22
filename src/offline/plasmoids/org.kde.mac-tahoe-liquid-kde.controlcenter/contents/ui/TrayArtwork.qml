// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.mac.tahoe.launcher as Native

Item {
    id: sample
    required property Item glyph
    property bool wallpaperTint: false
    property real artworkScale: 1
    property bool monochrome: false
    property int revision: 0
    property int retries: 0
    property var grab
    opacity: 0

    Binding {
        target: sample.glyph
        property: "scale"
        when: sample.glyph !== null
        value: sample.artworkScale
    }
    Binding {
        target: sample.glyph
        property: "isMask"
        when: sample.glyph !== null && sample.monochrome
        value: true
    }
    Binding {
        target: sample.glyph
        property: "color"
        when: sample.glyph !== null && sample.monochrome
        value: ink.foreground
    }

    Native.WallpaperInk {
        id: ink
        item: sample.glyph
        base: Kirigami.Theme.textColor
        active: sample.wallpaperTint && sample.monochrome
    }

    // Sample a separate copy so recolouring an earlier notification icon
    // cannot strip a new badge's colour before it is measured.
    Kirigami.Icon {
        id: raw
        source: sample.glyph?.source ?? ""
        width: sample.glyph?.width ?? 0
        height: sample.glyph?.height ?? 0
        onSourceChanged: sample.schedule()
        onWidthChanged: sample.schedule()
        onHeightChanged: sample.schedule()
        onValidChanged: sample.schedule()
    }
    function schedule() {
        ++revision
        retries = 0
        grab = null
        monochrome = false
        if (timer) timer.restart()
    }
    Component.onCompleted: schedule()
    Timer {
        id: timer
        interval: 100
        onTriggered: {
            if (!raw.valid || raw.width < 1 || raw.height < 1) return
            const revision = sample.revision
            raw.grabToImage(result => {
                if (sample.revision === revision) sample.grab = result
            }, Qt.size(Math.ceil(raw.width * 2), Math.ceil(raw.height * 2)))
        }
    }
    Image {
        id: pixels
        source: sample.grab?.url ?? ""
        cache: false
        onStatusChanged: if (status === Image.Ready) canvas.requestPaint()
    }
    Canvas {
        id: canvas
        width: Math.max(1, pixels.sourceSize.width)
        height: Math.max(1, pixels.sourceSize.height)
        onPaint: {
            if (!sample.grab || pixels.status !== Image.Ready) return
            const w = width, h = height
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, w, h)
            ctx.drawImage(pixels, 0, 0, w, h)
            const data = ctx.getImageData(0, 0, w, h).data
            let left = w, right = -1, top = h, bottom = -1, visible = 0, grey = 0
            for (let y = 0; y < h; ++y) {
                for (let x = 0; x < w; ++x) {
                    const i = 4 * (y * w + x)
                    if (data[i + 3] <= 64) continue
                    left = Math.min(left, x)
                    right = Math.max(right, x)
                    top = Math.min(top, y)
                    bottom = Math.max(bottom, y)
                    ++visible
                    if (Math.max(data[i], data[i+1], data[i+2]) - Math.min(data[i], data[i+1], data[i+2]) < 24) ++grey
                }
            }
            sample.grab = null
            if (!visible) {
                if (++sample.retries < 5) timer.restart()
                return
            }
            const extent = Math.max((right-left+1) * raw.width / w, (bottom-top+1) * raw.height / h)
            sample.artworkScale = Math.min(1, 16 / extent)
            sample.monochrome = grey >= visible * 0.97
        }
    }
}
