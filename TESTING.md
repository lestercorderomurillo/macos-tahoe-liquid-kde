# Installer testing

Tahoe **v0.62.0** fixes missing Nautilus blur, updates KWin scene damage
registration and prevents competing blur effects from remaining active during
installation. Glass opacity is retired. Actual pixel captures passed on
Wayland KWin 6.6.4, 6.7.4 and 6.8.2, and native X11 6.6.5 and 6.7.4;
94 release frames were individually reviewed across both editions and modes.
See the [Acrylic validation report](tests/native/acrylic_glass_062.md) for
upstream review, regression results and coverage limits.

The photographs below use the pinned disposable VM capture recipe and retain
reviewed, content-hashed provenance. Exact release commits require passing
push CI on both main and dev in both repositories.

## Installation steps

Scroll horizontally through the installation steps.

<table>
<tr>
  <td align="center"><img src="src/screenshots/installer-welcome_dark_v4-1fe4b7c74cbb.png" alt="Welcome" width="500"><br>Welcome</td>
  <td align="center"><img src="src/screenshots/installer-appearance_dark_v4-1214c385dfdc.png" alt="Appearance" width="500"><br>Appearance</td>
  <td align="center"><img src="src/screenshots/installer-icons_dark_v4-8508d749411f.png" alt="Icons and color" width="500"><br>Icons and color</td>
  <td align="center"><img src="src/screenshots/installer-wallpaper_dark_v4-3c1e40529ed4.png" alt="Wallpaper" width="500"><br>Wallpaper</td>
  <td align="center"><img src="src/screenshots/installer-launcher_dark_v4-8b8abcc096eb.png" alt="Launcher" width="500"><br>Launcher</td>
  <td align="center"><img src="src/screenshots/installer-layout_dark_v4-df6497d20d14.png" alt="Top bar and Dock" width="500"><br>Top bar and Dock</td>
  <td align="center"><img src="src/screenshots/installer-effects_dark_v4-2f6c6603d512.png" alt="Effects" width="500"><br>Effects</td>
  <td align="center"><img src="src/screenshots/installer-window_controls_dark_v4-f872a924b4fb.png" alt="Flat or Glassy window controls" width="500"><br>Window controls</td>
  <td align="center"><img src="src/screenshots/installer-shadows_dark_v4-e28b972c6240.png" alt="Window shadow comparison" width="500"><br>Window shadows</td>
  <td align="center"><img src="src/screenshots/installer-fonts_dark_v4-8bc4bc262204.png" alt="Fonts" width="500"><br>Fonts</td>
  <td align="center"><img src="src/screenshots/installer-firefox_dark_v4-6645e10732f6.png" alt="Firefox" width="500"><br>Firefox</td>
  <td align="center"><img src="src/screenshots/installer-files_dark_v4-0d8907c6d63d.png" alt="File manager" width="500"><br>File manager</td>
  <td align="center"><img src="src/screenshots/installer-glass_style_dark_v4-e3760f8ed53f.png" alt="Window glass" width="500"><br>Window glass</td>
  <td align="center"><img src="src/screenshots/installer-boot_dark_v4-d61550ec47cb.png" alt="Boot animation" width="500"><br>Boot animation</td>
  <td align="center"><img src="src/screenshots/installer-oled_dark_v4-f515499d8369.png" alt="OLED protection" width="500"><br>OLED protection</td>
  <td align="center"><img src="src/screenshots/installer-summary_dark_v4-7cdf54ccb595.png" alt="Summary" width="500"><br>Summary</td>
</tr>
</table>
