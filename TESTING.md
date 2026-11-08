# Installer testing

Tahoe **v0.63.1** fixes Dock spacing at a 56 px center pitch on the default
68 px panel, preserving 42 px visible icons. The spacing selector is removed;
legacy saved values no longer affect geometry. Both editions share the change.

Focused KDE neon VM checks passed: 20 Dock regressions across orientations,
compression and display scales, plus 7 task-manager/install regressions.
Golden Gate light/dark/light captures preserve icon size and spacing. See
[validation evidence](tests/dock_spacing_validation.json) for commands and limits.
Release publication additionally requires exact-commit CI on main and dev.

## Installation steps

Scroll horizontally through the installation steps.

<table>
<tr>
  <td align="center"><img src="src/screenshots/installer-welcome_dark_v4-e33ae2074e37.png" alt="Welcome" width="500"><br>Welcome</td>
  <td align="center"><img src="src/screenshots/installer-appearance_dark_v4-cbd81ab8fef4.png" alt="Appearance" width="500"><br>Appearance</td>
  <td align="center"><img src="src/screenshots/installer-icons_dark_v4-7ea49971f78c.png" alt="Icons and color" width="500"><br>Icons and color</td>
  <td align="center"><img src="src/screenshots/installer-wallpaper_dark_v4-b23218dae540.png" alt="Wallpaper" width="500"><br>Wallpaper</td>
  <td align="center"><img src="src/screenshots/installer-launcher_dark_v4-cd7bdad8b465.png" alt="Launcher" width="500"><br>Launcher</td>
  <td align="center"><img src="src/screenshots/installer-layout_dark_v4-1194dbf959c2.png" alt="Top bar and Dock" width="500"><br>Top bar and Dock</td>
  <td align="center"><img src="src/screenshots/installer-effects_dark_v4-07283b0bf444.png" alt="Effects" width="500"><br>Effects</td>
  <td align="center"><img src="src/screenshots/installer-window_controls_dark_v4-858098db4ed3.png" alt="Flat or Glassy window controls" width="500"><br>Window controls</td>
  <td align="center"><img src="src/screenshots/installer-shadows_dark_v4-f7d360aabf64.png" alt="Window shadow comparison" width="500"><br>Window shadows</td>
  <td align="center"><img src="src/screenshots/installer-fonts_dark_v4-daaeba3d059b.png" alt="Fonts" width="500"><br>Fonts</td>
  <td align="center"><img src="src/screenshots/installer-firefox_dark_v4-a4e5ebe3254b.png" alt="Firefox" width="500"><br>Firefox</td>
  <td align="center"><img src="src/screenshots/installer-files_dark_v4-e16ea88dd70e.png" alt="File manager" width="500"><br>File manager</td>
  <td align="center"><img src="src/screenshots/installer-glass_style_dark_v4-f913bca520d1.png" alt="Window glass" width="500"><br>Window glass</td>
  <td align="center"><img src="src/screenshots/installer-boot_dark_v4-de543c2dfb97.png" alt="Boot animation" width="500"><br>Boot animation</td>
  <td align="center"><img src="src/screenshots/installer-oled_dark_v4-c8e66978f276.png" alt="OLED protection" width="500"><br>OLED protection</td>
  <td align="center"><img src="src/screenshots/installer-summary_dark_v4-09c9cde4ba61.png" alt="Summary" width="500"><br>Summary</td>
</tr>
</table>
