# Local next-update preview

This candidate is intentionally unpublished so it can be tried locally first.
VERSION and release tags remain at the last published version.

- Application About uses the computer About glass surface, draggable frameless
  window and the same shared GlassButton component. Its content remains scrollable.
- The application-name popup contains only About and Close, both with the app name.
  Window controls are in View; exported application View actions are preserved.
- The installer opens at 900 × 680, with a six-card wallpaper selection.
- During installation/removal, a fading-spoke spinner sits beside the progress
  bar and a centered localized estimate appears below. The estimate uses elapsed
  time and completed-step progress; it is approximate, not a fixed countdown.
  A glass chevron toggles the dark details console. Its system monospace font is
  captured when the wizard opens and stays fixed across desktop font changes.
- Prism supplies newly generated psychedelic light/dark artwork. macOS exposes
  the existing original Monterey light/dark bundle; the other bundled Apple
  wallpapers remain available through Plasma's wallpaper selector.

From either checkout, run `./installer` to try the candidate. Golden Gate prepares
its own edition using the adjacent Tahoe checkout, including these local changes.
Its published immutable upstream pin is intentionally unchanged until release.

For a standalone About preview without installation, run from Tahoe:

```sh
python3 tests/application_about_probe.py --preview
```

The preview uses sample Files metadata. Opening it does not replace the installed
applet; the changed menu requires installing the candidate through the wizard.
No host installation was performed automatically.

Local verification: 43 installer/About/wallpaper checks passed, followed by
three focused switcher cases for Landscape, Prism and macOS; 31 catalog checks
and 14 component-cache checks passed. The native isolated X11 suite built the
plugin and exercised the importer, popup actions and QML composition successfully.
These are local checks, not CI or VM install results. Live Plasma
installation/reinstallation and compositor qualification are still required
before a future release; offscreen captures do not prove compositor blur.

Progress-page follow-up: all 36 wizard tests passed, including both editions,
localized estimates, details toggling, status retention in the log and an actual
application-font change while output continues. Local screenshots in
`build/next-preview/progress*.png` use simulated progress; no installation ran.

Pre-install appearance: the installer now supplies its own process-local Qt
style and palette, selected in light/dark mode when it opens. Breeze or Kvantum
is not required for its glass controls, card colors or layout. The system font
and accessibility scale remain in use; no desktop configuration is changed.
All 37 wizard tests pass, including pixel comparisons starting with Breeze,
Kvantum, Windows and Fusion in both modes, and a desktop-palette change followed
by navigation. These comparisons use isolated offscreen Qt rendering.

The summary ends after the selected options; the redundant included-components
and immediate-application text block has been removed.
