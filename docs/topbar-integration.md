# Global menu applet

Release v0.66.0. Scope: the existing global menu applet only.

The existing Tahoe plasmoid is the base. It already provides the system menu,
application actions, dynamic D-Bus menu refresh, persistent Wayland popup grabs,
and the reviewed Tahoe/Golden Gate appearance. Replacing it wholesale would
lose those behaviors. Golden Gate continues staging this implementation.

Reviewed QuickBar source: [213a583adfd257ed420c77ef2cf1443a709a3425](https://github.com/kevinbudz/quickbar/tree/213a583adfd257ed420c77ef2cf1443a709a3425).
Its menu traversal and mnemonic handling are adapted in `quickbarmenuhelpers.h`;
its owned-popup/borrowed-menu distinction informs the popup lifecycle repair.
Search is selectable on both backends, and open-menu hover switching is optional.
Existing system-font, capsule and popup styling remains project-owned behavior.
The original notices and QuickBar's root MIT notice accompany the adaptations.

QuickBar's fallback-menu approach is adapted into the existing model: real
exported menus take priority; windows without an export receive common File,
Edit and View actions. This is a generated menu, not extraction of a GTK4 or
Steam internal menu. The setting can be disabled independently of menu search.
Window actions use the captured task. Edit actions use standard application
shortcuts, so their meaning and availability inside the document remain owned
by the application. No process is terminated to implement Close Window.

Shortcut dispatch waits for the popup to release its grab and verifies the
originating persistent task before sending. A window change, deletion or newer
action cancels the pending command. The X11 backend uses XTest; the Plasma
Wayland backend uses KWin's version 6 shell input protocol with keysyms. An
unavailable backend disables Edit actions. QuickBar's wtype invocation and
private Qt menu geometry mutations are not imported.

The vendored protocol is unmodified KDE plasma-wayland-protocols
[`1db07441870d54157e937674b99380a7dcc0fb32`](https://github.com/KDE/plasma-wayland-protocols/blob/1db07441870d54157e937674b99380a7dcc0fb32/src/protocols/fake-input.xml),
LGPL-2.1-or-later, SHA-256 `89f4ada4a1f09168a4528f47c0495e3f89dc2a25e8b23f4539ed3f5110eff708`.
It is a desktop-shell implementation detail; supported compositor versions
must be exercised, and protocol advertisement alone does not prove dispatch.

The applet remains a Plasma Applet with its original QML layout, Apple menu,
fonts and popup styling. The abandoned embedded containment, tray/clock loaders,
accessory settings and panel-layout changes have been removed. Existing panel
widgets and user desktop configuration are not migrated or modified.

## Focused validation

Source: Tahoe base `b34984642b44702588fea0dd94837870bcff065e` plus this
menu-only working diff. Local Qt 6.11.2 SDK, private Xvfb and private D-Bus;
no host desktop changes. Applet content SHA-256 (sorted relative file names,
NUL, file bytes, NUL):
`a196755913227bb26cea7c7023d7cf57f4eccfedb1ef369bf496b7bce18522bd`.

- `python -m pytest -q tests/test_globalmenu_model.py`: passed. Builds the
  production plugin and exercises native D-Bus model updates, generic/native
  transitions, disabled fallback on an empty export, shortcut delivery and
  cancellation, popup lifetime/search, and menu-only QML composition.
- `python -m pytest -q tests/test_globalmenu_step.py`: 6 passed.
- `python -m pytest -q tests/test_distro_packages.py -k
  'declared_dependencies_have_one_arch_fallback_each or
  every_declared_package_token_is_mapped_for_supported_non_arch_distros'`:
  2 passed, 415 unrelated cases deselected.
- Golden Gate `./install --prepare`, with `GOLDEN_GATE_TAHOE_SOURCE` pointing
  at the local Tahoe checkout and updates disabled: all 39 applet files match
  the tested source byte-for-byte; defaults remain MacGoldenGate/preset 2.
- `git diff --check`: passed.

The first sandboxed native run compiled successfully but could not start Xvfb.
The successful run used permission to create the isolated display and bus.
The initial implementation CI completed all distro jobs and Nix successfully:
[run 42564969879](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/42564969879).
Its general-suite failure identified missing shared German/Portuguese menu
catalog entries; those entries were restored, and both affected catalog checks
passed. This earlier run does not replace the final exact-commit release gate.

The capture dependency audit binds exact before/after Git objects for this menu
change. It requires four fresh menu frames and retains the other 102 with their
original source commits, hashes and review records. Any later menu implementation
edit or unrelated runtime change fails closed. The scope-composition regression
passed; no global capture profile or unrelated widget was changed.

No new end-to-end Steam or alternate-keyboard-layout validation was performed. SDKs without the X11 TasksModel backend skip that backend-specific
case; the model fixture and actual XTest delivery still run. Previous full-bar captures are not evidence for this revision. Final CI and
publication are enforced by the release workflows, including the matching
Golden Gate immutable source pin.

The four replacement menu frames were captured from
`f5bffcc36d81b4be504910711d87393135d050d1` with the pinned KDE neon VM
(`412e7933f10add20b921b92c02709e7eea56acd14dc14cf654f58fba4ea3cc9d`),
Plasma/KWin 6.8.1, Qt 6.11.1, Wayland. Visual review confirms the existing Apple
popup and the File/Edit/View fallback beside Files in both editions and modes.
The full frame hashes, environment and retained origins are recorded in
`src/screenshots/release-capture.json`; only the menu crops are republished.
Missing Plymouth/About log messages come from optional collection after this
menu-only capture; those components were not exercised or recaptured.
