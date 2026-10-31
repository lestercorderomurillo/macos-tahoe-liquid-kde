# Installer testing

Tahoe **v0.61.11** is the latest verified release documented here.
The installer photographs below were captured in a disposable KDE Plasma VM
and reviewed before publication; their original hashes and provenance are retained.

Status-icon validation covers both editions, palette changes and generated
appearances: 56 focused Tahoe checks, 53 prepared Golden Gate checks,
80 wrapper checks, 32,340 native host renders and 9,240 native renders in
KDE neon (Plasma 6.8.1, Qt 6.11.1, Wayland). Recorded primary CI results:
2,013 passed and 11 conditional skips. Skipped X11, external Rounded Corners
archive and native Kvantum checks remain coverage limits; battery rendering
does not establish hardware-telemetry qualification.

See the [validation report](tests/native/status_icons_validation.md) for commands, source identities, results
and coverage limits, and [CONTRIBUTING.md](CONTRIBUTING.md) for the testing and capture workflow.

## Installation steps

Scroll horizontally through the installation steps.

<table>
<tr>
  <td align="center"><img src="src/screenshots/installer-welcome_dark_v4-b3f548b18bae.png" alt="Welcome" width="500"><br>Welcome</td>
  <td align="center"><img src="src/screenshots/installer-appearance_dark_v4-a6f5633f614d.png" alt="Appearance" width="500"><br>Appearance</td>
  <td align="center"><img src="src/screenshots/installer-icons_dark_v4-fb1bad1909be.png" alt="Icons and color" width="500"><br>Icons and color</td>
  <td align="center"><img src="src/screenshots/installer-wallpaper_dark_v4-7ee3602eddd1.png" alt="Wallpaper" width="500"><br>Wallpaper</td>
  <td align="center"><img src="src/screenshots/installer-launcher_dark_v4-28b8fff306a0.png" alt="Launcher" width="500"><br>Launcher</td>
  <td align="center"><img src="src/screenshots/installer-layout_dark_v4-609c79632293.png" alt="Top bar and Dock" width="500"><br>Top bar and Dock</td>
  <td align="center"><img src="src/screenshots/installer-effects_dark_v4-37b69a1dc300.png" alt="Effects" width="500"><br>Effects</td>
  <td align="center"><img src="src/screenshots/installer-window_controls_dark_v4-cba3352b022c.png" alt="Flat or Glassy window controls" width="500"><br>Window controls</td>
  <td align="center"><img src="src/screenshots/installer-shadows_dark_v4-aa2aed4e457f.png" alt="Window shadow comparison" width="500"><br>Window shadows</td>
  <td align="center"><img src="src/screenshots/installer-fonts_dark_v4-523d7c630b5d.png" alt="Fonts" width="500"><br>Fonts</td>
  <td align="center"><img src="src/screenshots/installer-firefox_dark_v4-71fbb08207e7.png" alt="Firefox" width="500"><br>Firefox</td>
  <td align="center"><img src="src/screenshots/installer-files_dark_v4-dfae21b14c3f.png" alt="File manager" width="500"><br>File manager</td>
  <td align="center"><img src="src/screenshots/installer-boot_dark_v4-2fb5ea08e3d6.png" alt="Boot animation" width="500"><br>Boot animation</td>
  <td align="center"><img src="src/screenshots/installer-oled_dark_v4-446f97633da9.png" alt="OLED protection" width="500"><br>OLED protection</td>
  <td align="center"><img src="src/screenshots/installer-summary_dark_v4-64bdc98e7f16.png" alt="Summary" width="500"><br>Summary</td>
</tr>
</table>
