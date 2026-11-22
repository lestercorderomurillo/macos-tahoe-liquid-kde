# Matching window decorations in every application

The theme draws the title bar and the close, minimize and maximize buttons of
every window that lets KDE decorate it (server-side decorations). Some
applications draw their own title bar instead (client-side decorations): KDE
cannot replace it, so those windows keep their own buttons whatever the theme.
Most of them have a setting that hands the title bar back to KDE.

| Application | How to use the system title bar |
|---|---|
| Chrome, Chromium, Brave, Edge, Vivaldi | Right-click the empty area of the tab strip and check **Use system title bar and borders**. The same switch is in **Settings → Appearance**. |
| Firefox | **Menu → More tools → Customize toolbar…**, then check **Title bar** at the bottom left. |
| Visual Studio Code, VSCodium | Set `"window.titleBarStyle": "native"` in `settings.json` (**Settings → Window → Title Bar Style → native**) and restart. |
| Other Electron apps | Many accept `--enable-features=WaylandWindowDecorations --ozone-platform-hint=auto` on Wayland, from the launcher's command line. Apps that build a frameless window, like the Discord client, cannot be changed. |
| Qt and KDE apps | Use the system title bar already. |
| GTK 3 apps | Apps with a header bar keep it: the theme's GTK styling gives their buttons the same look. Apps without one use the system title bar. |
| GTK 4 / libadwaita apps | Always draw their own header bar. The theme's GTK 4 styling matches the buttons; the bar itself stays the app's. |
| Flatpak apps | Flatpak apps cannot read the theme's GTK files by default. Grant read access once: `flatpak override --user --filesystem=xdg-config/gtk-3.0:ro --filesystem=xdg-config/gtk-4.0:ro`. |
| Snap apps | Snaps only use the themes their snap ships or the `gtk-common-themes` snap; the theme's files are out of reach. |

Window shadows, corner radius and the button position (left or right) follow
the same rules: they apply to every window KDE decorates, and only to those.
