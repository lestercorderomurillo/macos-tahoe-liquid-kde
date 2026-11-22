# Desktop: no files under widgets

`desktopcontainment-keep-icons-out-of-widgets.patch` applies to Plasma's
`main.qml` and `FolderView.qml` in
`/usr/share/plasma/plasmoids/org.kde.desktopcontainment/contents/ui/`.
As on macOS, desktop icons stay out of the widgets: the whole rectangle that
encloses the desktop widgets is off limits. A drop there is refused, and icons
that end up there (new files, earlier drops) move to the first free grid cell
outside it.

It also keeps the Dock's height free at the bottom of every screen, whether
the Dock is on that screen or not. The desktop spreads its icon grid over the
available height, so without this the icons moved each time the single Dock
changed screen.

It is **not wired into the installer**: it patches a Plasma system file, which
needs root and is undone by Plasma updates. Apply manually:

```sh
D=/usr/share/plasma/plasmoids/org.kde.desktopcontainment
sudo cp -n "$D/contents/ui/main.qml" "$D/contents/ui/main.qml.orig"
sudo cp -n "$D/contents/ui/FolderView.qml" "$D/contents/ui/FolderView.qml.orig"
sudo patch -d "$D" -p1 < src/offline/plasma-desktop/desktopcontainment-keep-icons-out-of-widgets.patch
```
