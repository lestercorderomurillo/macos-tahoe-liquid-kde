# Matching window decorations in KDE Plasma

When KWin draws a window's frame (server-side decorations), it uses the
selected KDE decoration for the title bar, buttons and button placement. Apps
that draw their own title bar (client-side decorations) control its layout.
KDE has no global switch to make every app use its window decoration.

| Application | How to match the title bar or buttons |
|---|---|
| Chrome, Chromium, Brave, Edge, Vivaldi | If available, right-click an empty area of the tab strip and enable **Use system title bar and borders**. Some builds also expose this under **Settings → Appearance**. |
| Firefox | Open **Menu → More tools → Customize toolbar…** and check **Title Bar** at the bottom. If the checkbox is missing, exit full screen and check again. |
| Visual Studio Code, VSCodium | Set `"window.titleBarStyle": "native"` in `settings.json` and fully restart the app. |
| Other Electron apps | Look for a native title bar or system frame setting. Electron 38 and later use native Wayland by default in a Wayland session. Older builds with Wayland support may need `--ozone-platform=wayland` to select that backend. The app still controls whether it uses a native frame. Frameless apps keep their own controls. |
| Qt and KDE apps | Standard windows with a native frame already use the KDE decoration. Apps with custom frames control their own title bar. |
| GTK 3 apps | Apps with a GTK header bar keep that layout. The theme can style its buttons when the app uses the installed GTK theme. |
| GTK 4 / libadwaita apps | Apps with a GTK header bar keep that layout. The theme's GTK 4 stylesheet can style compatible header-bar buttons. |

## Flatpak and Snap

The app's native title bar setting still applies in a sandbox if the app
offers one. For app-drawn controls, the GTK theme must also be available
inside the sandbox. Flatpak can use a matching GTK theme extension or a
runtime-specific GTK configuration. Snap applications use the themes shipped
with the app or provided by connected content snaps.

- [Electron's Wayland defaults](https://www.electronjs.org/docs/latest/breaking-changes#breaking-api-changes-380)
- [Flatpak theme integration](https://docs.flatpak.org/en/latest/desktop-integration.html#theming)
