# Focused regression qualification: v0.72.11

This patch completes the inherited-theme repair from issue #130. Installation
and reinstallation no longer run the destructive kdedefaults scrub: that helper
changed the recorded package to Breeze and deleted the active inherited color
scheme and icons. Explicit uninstallation still performs the cleanup.

- `pytest tests/test_kconf_update.py`: 12 passed, including light/dark inherited
  defaults, repeated installation and explicit uninstall cleanup.
- The normal installer privilege setup plus `kconf_update.install()` ran twice
  in the disposable Plasma VM. `kdedefaults/package`, `kdeglobals` and
  `plasmarc` remained byte-identical to the active Tahoe values, then
  `plasma-plasmashell.service` restarted successfully.
- French Control Center and satellite applet catalogs now translate the reported
  English controls. `msgfmt --check --check-format` passed; the new gettext
  resolution case passed for all four applet domains. This adds French controls,
  not a claim that the entire installer is translated into French.
- `pytest tests/test_multilanguage.py -k catalogs_cover`: two passed after
  regenerating every importing satellite's German/Portuguese catalog. Spanish
  and Chinese shared catalogs were refreshed too.
- The real X11 Control Center render/lifecycle probe passed in the VM. Its gap
  assertion now measures the gap between rendered controls, preserving input
  mask and compositor blur-region checks when the absent battery changes width.
- GTK selection tests report an unavailable GTK introspection version as skipped
  in minimal SDKs. The primary CI explicitly requires GTK 4; real GTK 3 and 4
  selection/state coverage from v0.72.10 remains valid. No distro leg or test
  scenario was removed.

The v0.72.10 post-publication matrix exposed missing satellite translations,
the obsolete fixed gap coordinate and the missing-GTK-4 condition on Fedora/
Nobara. These were corrected here; that failed matrix is not passing evidence.
The [full v0.72.11 matrix](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43912624471) passed all 16 jobs. Arch initially stalled in GitHub checkout before testing; only that job was retried, retaining the other 15 passing results. The [Golden Gate wrapper CI](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/actions/runs/43913154331) also passed.

The [v0.72.10 qualification](REGRESSIONS-0.72.10.md) remains the evidence for
unchanged accent, disk and layout repairs. Its reviewed captures retain commit
`6ef284ccba1f6c57e86e0460ff55ca33408e5cad` as their source. No new gallery was
captured. The reported launcher focus loss was exercised on real KWin and closed
correctly; existing preset/menu interaction regressions also passed in the
v0.72.10 primary job. Independent icon appearance remains a feature request.
