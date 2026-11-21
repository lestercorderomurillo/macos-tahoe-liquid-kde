# Desktop: no files under widgets

`desktopcontainment-no-drop-on-widgets.patch` applies to Plasma's
`/usr/share/plasma/plasmoids/org.kde.desktopcontainment/contents/ui/main.qml`.
A file or folder dropped on a desktop widget is refused and goes back, as on
macOS, instead of landing under the widget.

It is **not wired into the installer**: it patches a Plasma system file, which
needs root and is undone by Plasma updates. Apply manually:

```sh
D=/usr/share/plasma/plasmoids/org.kde.desktopcontainment
sudo cp -n "$D/contents/ui/main.qml" "$D/contents/ui/main.qml.orig"
sudo patch -d "$D" -p1 < src/offline/plasma-desktop/desktopcontainment-no-drop-on-widgets.patch
```
