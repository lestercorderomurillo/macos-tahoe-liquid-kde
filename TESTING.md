# Installer testing

Tahoe **v0.69.0** uses original Apple glyph outlines for the system-menu symbols.
Tahoe shows an icon on every action; Golden Gate shows only About, System Settings
and App Store. The active theme selects this preset across light/dark transitions,
independently of the Launcher preset. The existing App Store drawing is retained.

The native renderer, live cached-menu preset changes and shortcut interactions
pass in an isolated Arch SDK/X11 environment. Both editions passed installation
and reinstallation in disposable KDE neon Plasma/KWin 6.8.1 Wayland VMs, with
four reviewed menu captures. The full remote matrix remains asynchronous.
See [release evidence](release-evidence.json) and the
[original-font glyph provenance](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/blob/6f515f188b86db6ee6f997eedee0c669c4c02a36/src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/systemmenusymbols.json).

[Light menu](src/screenshots/menu_v4-0343811e426d.webp) · [Dark menu](src/screenshots/menu_dark_v4-171bb0e051ff.webp) · [Capture provenance](src/screenshots/previews/system-menu-tahoe-069-provenance-9c458fcf42db.json)

The README About, Finder and top bar photographs retain their v0.67.0 source from a
disposable VM. Other desktop images and the installer gallery retain their original
reviewed provenance ([capture records](src/screenshots/release-capture.json)). The retained v0.66.2 About previews show the corrected labels
in both modes ([provenance](src/screenshots/previews/about-buttons-provenance.json)).

[Light preview](src/screenshots/previews/about-buttons-light-eaebe82caa18.png) · [Dark preview](src/screenshots/previews/about-buttons-dark-57536aa93c40.png)

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
