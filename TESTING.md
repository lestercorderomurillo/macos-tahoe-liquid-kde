# Installer testing

Tahoe **v0.73.4** corrects the icon lifecycle regression test to expect restoration of a backed-up user edit; installed behavior is unchanged from v0.73.3. All 13 focused icon lifecycle and asset ownership checks passed in isolated temporary directories. Prior selected VM lifecycle qualification is retained in the [safety evidence](docs/evidence/uninstall-safety-0733.json); current checks and coverage limits are in [release evidence](release-evidence.json). Full remote CI runs asynchronously; existing photographs retain their original provenance.

Approved installer previews: [Light](src/screenshots/previews/installer-tahoe-light-icons-805970eab6b7.png) · [Dark](src/screenshots/previews/installer-tahoe-dark-icons-dbc66adc81c4.png). The gallery below is historical and predates these installer changes; its original [provenance](src/screenshots/release-capture.json) is retained.

## Installation steps

Scroll horizontally through the installation steps.

<table>
<tr>
  <td align="center"><img src="src/screenshots/installer-welcome_dark_v4-07e3ace23ecd.webp" alt="Welcome" width="500"><br>Welcome</td>
  <td align="center"><img src="src/screenshots/installer-appearance_dark_v4-cb3010a655df.webp" alt="Appearance" width="500"><br>Appearance</td>
  <td align="center"><img src="src/screenshots/installer-icons_dark_v4-6da196043656.webp" alt="Icons and color" width="500"><br>Icons and color</td>
  <td align="center"><img src="src/screenshots/installer-wallpaper_dark_v4-71c1437b72f2.webp" alt="Wallpaper" width="500"><br>Wallpaper</td>
  <td align="center"><img src="src/screenshots/installer-launcher_dark_v4-4c649664ccd0.webp" alt="Launcher" width="500"><br>Launcher</td>
  <td align="center"><img src="src/screenshots/installer-layout_dark_v4-e3a848e2a47a.webp" alt="Top bar and Dock" width="500"><br>Top bar and Dock</td>
  <td align="center"><img src="src/screenshots/installer-effects_dark_v4-2417cbbd36cd.webp" alt="Effects" width="500"><br>Effects</td>
  <td align="center"><img src="src/screenshots/installer-window_controls_dark_v4-eedd4ce4d0b4.webp" alt="Flat or Glassy window controls" width="500"><br>Window controls</td>
  <td align="center"><img src="src/screenshots/previews/button-position-tahoe-dark-wizard-281c04c32309.webp" alt="Window buttons" width="500"><br>Window buttons</td>
  <td align="center"><img src="src/screenshots/installer-shadows_dark_v4-d78803a9bf02.webp" alt="Window shadow comparison" width="500"><br>Window shadows</td>
  <td align="center"><img src="src/screenshots/installer-fonts_dark_v4-5ed134810b67.webp" alt="Fonts" width="500"><br>Fonts</td>
  <td align="center"><img src="src/screenshots/installer-firefox_dark_v4-f373877df3a2.webp" alt="Firefox" width="500"><br>Firefox</td>
  <td align="center"><img src="src/screenshots/installer-files_dark_v4-d603c0bd4a8b.webp" alt="File manager" width="500"><br>File manager</td>
  <td align="center"><img src="src/screenshots/installer-glass_style_dark_v4-b3a8a7506ab6.webp" alt="Window glass" width="500"><br>Window glass</td>
  <td align="center"><img src="src/screenshots/installer-boot_dark_v4-872ac7febe6d.webp" alt="Boot animation" width="500"><br>Boot animation</td>
  <td align="center"><img src="src/screenshots/installer-oled_dark_v4-fb72373e426a.webp" alt="OLED protection" width="500"><br>OLED protection</td>
  <td align="center"><img src="src/screenshots/installer-summary_dark_v4-e5a7bfc57e13.webp" alt="Summary" width="500"><br>Summary</td>
</tr>
</table>

Window buttons, captured in a disposable VM: [Light wizard](src/screenshots/previews/button-position-tahoe-light-wizard-9af66fd52939.webp) · [Light comparison](src/screenshots/previews/button-position-tahoe-light-comparison-f3ceb4999d5f.png) · [Dark wizard](src/screenshots/previews/button-position-tahoe-dark-wizard-281c04c32309.webp) · [Dark comparison](src/screenshots/previews/button-position-tahoe-dark-comparison-4b56fedd6db6.png) · [Provenance](src/screenshots/previews/button-position-tahoe-provenance-4002854e5c29.json)
