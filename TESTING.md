# Installer testing

Tahoe **v0.63.0** provides Tahoe (Clear), Tahoe (Frosted) and Golden Gate
(Official) glass presets, with separate light/dark colors in a three-stop
gradient. The Dock retains fixed v0.62.0 blur, refraction, highlights and color
tuning independently of window settings. The existing Nautilus blur, scene
damage and competing-effect fixes remain included.

Release validation runs the general suite once in two disjoint shards, plus
all eleven distro SDK/dependency/native checks and Nix. Main promotion verifies
the successful dev run for the exact commit. The focused CI selection and gate
checks passed **35 tests**. VM qualification and capture tooling remain intact.
Reviewed rc2 photographs retain their original capture version and provenance;
this workflow-only release does not recapture the desktop.
See [release performance](docs/release-performance.md) for coverage and timing.
See the [preset gallery](GLASS_PRESETS.md) for every surface and fine-tuning
value, with light/dark photographs. Release captures use the pinned Plasma
6.8.1 VM; they do not establish new live qualification on other Plasma versions.
The [v0.62 rendering report](tests/native/acrylic_glass_062.md) retains its
original version-specific Wayland/X11 evidence.

The photographs below use the pinned disposable VM capture recipe and retain
reviewed, content-hashed provenance. Exact release commits require passing
push CI on both main and dev in both repositories.

## Installation steps

Scroll horizontally through the installation steps.

<table>
<tr>
  <td align="center"><img src="src/screenshots/installer-welcome_dark_v4-e67bcd41b245.png" alt="Welcome" width="500"><br>Welcome</td>
  <td align="center"><img src="src/screenshots/installer-appearance_dark_v4-cbd81ab8fef4.png" alt="Appearance" width="500"><br>Appearance</td>
  <td align="center"><img src="src/screenshots/installer-icons_dark_v4-7ea49971f78c.png" alt="Icons and color" width="500"><br>Icons and color</td>
  <td align="center"><img src="src/screenshots/installer-wallpaper_dark_v4-b23218dae540.png" alt="Wallpaper" width="500"><br>Wallpaper</td>
  <td align="center"><img src="src/screenshots/installer-launcher_dark_v4-cd7bdad8b465.png" alt="Launcher" width="500"><br>Launcher</td>
  <td align="center"><img src="src/screenshots/installer-layout_dark_v4-1194dbf959c2.png" alt="Top bar and Dock" width="500"><br>Top bar and Dock</td>
  <td align="center"><img src="src/screenshots/installer-effects_dark_v4-07353b0bf444.png" alt="Effects" width="500"><br>Effects</td>
  <td align="center"><img src="src/screenshots/installer-window_controls_dark_v4-858098db4ed3.png" alt="Flat or Glassy window controls" width="500"><br>Window controls</td>
  <td align="center"><img src="src/screenshots/installer-shadows_dark_v4-f7d360aabf64.png" alt="Window shadow comparison" width="500"><br>Window shadows</td>
  <td align="center"><img src="src/screenshots/installer-fonts_dark_v4-daaeba3d059b.png" alt="Fonts" width="500"><br>Fonts</td>
  <td align="center"><img src="src/screenshots/installer-firefox_dark_v4-a4e5ebe3254b.png" alt="Firefox" width="500"><br>Firefox</td>
  <td align="center"><img src="src/screenshots/installer-files_dark_v4-e16ea88dd70e.png" alt="File manager" width="500"><br>File manager</td>
  <td align="center"><img src="src/screenshots/installer-glass_style_dark_v4-f913bca520d1.png" alt="Window glass" width="500"><br>Window glass</td>
  <td align="center"><img src="src/screenshots/installer-boot_dark_v4-de543c2dfb97.png" alt="Boot animation" width="500"><br>Boot animation</td>
  <td align="center"><img src="src/screenshots/installer-oled_dark_v4-c8e66978f276.png" alt="OLED protection" width="500"><br>OLED protection</td>
  <td align="center"><img src="src/screenshots/installer-summary_dark_v4-766f23e5d67e.png" alt="Summary" width="500"><br>Summary</td>
</tr>
</table>
