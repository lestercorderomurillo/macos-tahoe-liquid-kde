# macOS Tahoe lock screen

`LockScreen.qml` is a drop-in replacement for Plasma's lock screen UI
(`/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreen.qml`).

It is **not wired into the installer**. Plasma 6 does not let a global theme
ship its own lock screen: `kscreenlocker_greet` loads it from the desktop shell
package. Installing it means replacing that system file, which needs root and
is undone by every Plasma update.

Manual install (keeps the original):

```sh
D=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen
sudo cp -n "$D/LockScreen.qml" "$D/LockScreen.qml.orig"
sudo install -m 644 src/offline/lockscreen/LockScreen.qml "$D/LockScreen.qml"
```

Preview without installing:
`/usr/lib/x86_64-linux-gnu/libexec/kscreenlocker_greet --testing --shell <package>`
with a Plasma/Shell package whose `contents/lockscreen/LockScreen.qml` is this file.

Restore: `sudo mv "$D/LockScreen.qml.orig" "$D/LockScreen.qml"`.
