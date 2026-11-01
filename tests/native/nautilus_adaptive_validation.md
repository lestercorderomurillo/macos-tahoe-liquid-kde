# Installed Nautilus toolbar validation — v0.61.21

## Cause and scope

The v0.61.17 toolbar correction updated only each theme's primary `gtk.css`.
The installed theme switcher copies `gtk-Light.css` and `gtk-Dark.css` from
the selected theme into `~/.config/gtk-4.0/`; the adaptive user stylesheet
imports those copies. They still contained only the pre-Nautilus-50 widget-ID
selectors, so updating the primary sheet did not repair the running application.

Source `a1a3775a09910ed2f0771266b2d219cff9688a4a` adds the existing class-based
selectors to all six remaining GTK4 sheets across both theme directories,
including the lowercase dark fallback. The declarations, colors, geometry,
GTK3 sheets, controls, shadows and edition defaults are preserved. Both editions
share this source. No installer or theme-switch runtime code changed.

## Focused checks

Environment: CachyOS, system Python 3.14 and pytest. Tests isolate desktop writes.

```sh
python -m pytest tests/test_nautilus_styles.py tests/test_static.py tests/test_gtk_upgrade.py tests/test_gtk_window_geometry.py tests/test_nautilus_step.py tests/test_theme_switch.py -q
python -m pytest tests/test_window_controls.py tests/test_window_shadows.py -q
```

Results: **192** and **23** passed. The toolbar regression now checks all eight
GTK4 sheets with GTK 4.14, 4.16 and 4.22 compatibility paths. Running those same
24 cases against the parent commit's assets produces **18 failures and 6
passes**: every formerly missed adaptive/fallback sheet fails, while the primary
sheets pass. The fixed source passes all 24 cases. The README badge records
2,158 collected cases, not a claim that all executed locally.

Golden Gate's explicit local-source `./install --prepare` selected `MacGoldenGate`
and launcher preset 2. Its wrapper suite passed **95** checks. The staged
`test_nautilus_styles.py`, `test_gtk_upgrade.py`, `test_gtk_window_geometry.py`
and `test_nautilus_step.py` selection passed **42** checks.

## Native rendering and release captures

A disposable KDE neon guest used the checksum-pinned `neon-base-v2.qcow2`
image (`2a09de13ad568da01a8e16dd93e6aec120e63375bfc0ec24b4e804b43ecb4f8c`),
GTK 4.14.5, libadwaita 1.5.0 and Nautilus 46.4. The native
`tests/nautilus_toolbar_probe.py --theme-variant light` and `dark` runs passed
**120 comparisons each (240 total)** between the legacy widget-ID and modern
widget-class layouts. Both text directions and light/dark rendering cover
normal, hover, active, checked, backdrop, disabled, backdrop-hover,
backdrop-checked, checked-hover and disabled-checked states. Loading the parent's
stale adaptive sheets first fails the same native comparison as expected.

The installed host's actual Nautilus 50.2.2 also ran in a private Xvfb/X11,
D-Bus and KWin session with copies of its repaired installed styles, isolated
XDG directories and three disposable folders. Eight full-window captures were
reviewed: light/dark × focused/backdrop × all files selected/no files selected.
Focus was asserted through X11 window IDs. The toolbar retained its continuous
rounded ends and rounded ellipsis backing, without a geometry jump when focus
or file selection changed. These private local QA captures are not publication
assets; this check does not qualify every Wayland compositor or GPU.

Fresh full installations for Tahoe and Golden Gate in disposable guests
produced **90 reviewed 4K release frames**, covering both appearance modes,
Files, About, launcher, menus, Dock, all wizard pages and Plymouth. README and
TESTING galleries are staged with content hashes and version-bound provenance.
The capture source is the implementation commit above; subsequent test/report
edits preserve its visual inputs.

## Coverage and publication

The reporting host uses Nautilus 50.2.2, GTK 4.22.4 and libadwaita 1.9.3.
Its active adaptive sheets were verified to lack the class selectors before
the repair. A backed-up selector-only repair preserves the installed controls,
shadows and accent; Nautilus was restarted with its open location
restored. Host configuration checks are not a claim of exhaustive native
Nautilus 50 qualification on every distro or GPU.

Publication requires the complete `test.yml` push workflows to succeed on
`main` and `dev` at each repository's exact release commit. The guarded release
workflows then publish Tahoe first and Golden Gate with the immutable Tahoe
commit and verified archive SHA-256. Consult the v0.61.21 release commits'
Actions runs for exact-SHA CI evidence. Focused local results do not replace
those gates; no skipped, failed or cancelled gate is accepted.
