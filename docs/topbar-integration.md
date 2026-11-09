# Unified top bar integration

Development candidate, not release evidence.

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

The menu plasmoid becomes an embedded Plasma containment hosting the native
system tray and digital clock. Their popups and settings remain native. New
managed layouts enable `Appearance.integratedBar`; existing menu-only instances
retain their layout unless the user enables integration or resets the layout.
No separate QuickBar plugin or runtime download is introduced.

Validation must cover native search and popup lifetimes, real QML composition,
layout/install/reinstall/uninstall paths, both staged editions, and supported
Plasma SDKs. Native compilation alone does not establish visual correctness.
Component-scoped disposable-VM checks are recorded below; exact-commit
CI/release gates in both repositories remain required.

## Focused development evidence

Candidate based on Tahoe `b34984642b44702588fea0dd94837870bcff065e`.
Global Menu source-tree digest before catalogue additions (sorted relative paths and file bytes,
each NUL-delimited): `fa69bd2dada886ac6b6e52ab7a52d1d922726667a960e08a5777b79cf612d1d0`.

- Qt 6.11.2 local SDK: native model and popup binaries built successfully.
  Private Xvfb/private D-Bus runs passed after the importer fix, including
  generic/native transitions, an initially empty export becoming populated,
  target deletion, and dynamic popup reopening. The standalone model runner
  did not enable the real X11 TasksModel scenario; that remains separate coverage.
- `python -m pytest -q tests/test_globalmenu_step.py tests/test_distro_packages.py tests/test_nix.py`:
  426 passed for dependency mappings, installer component paths and Nix contracts.
- `python -m pytest -q tests/test_globalmenu_model.py`: passed with the final
  importer and menu-width changes, including production plugin compilation and
  private model/popup/composition runs (40.98 seconds). After restoring the
  previous clock font defaults, the affected production plugin and composition
  test were rebuilt; composition passed all three cases.
- Disposable KDE neon 6.8.1 / Qt 6.11.1, Wayland, 3840×2160 scale 2:
  source archive `e6c459670f62ccb8958de5204272d2089222bce907094e3aa8e927e54fb91297`,
  installed plugin SHA-256 `183750ea1b9e48301a2faca8c5080ec202fcf5f3b7b1b78a6d56fda7c189883d`.
  GTK4 TextView fixture: actual bar clicks on Edit → Select All selected the
  two-line document; Edit → Copy returned that text through the guest Klipper.
  Nautilus: with its file grid focused, the same clicks selected 25 items and
  copied their 25 file URIs. With its sidebar focused, those shortcuts did not
  select files; fallback actions retain the application's normal focus semantics.
  Kate: the bar switched to the real exported File/Edit/Selection/View/etc.
  menu, and Selection → Select All selected the document. Native Selection
  and generic Edit popups were reviewed in dark mode as well as light mode.
  The integrated-bar mode also dispatched Select All to the GTK4 fixture.
- Actual shortcut delivery plus cancellation on target switch/deletion passed
  in the private Xvfb model test (11 passing cases, one real-X11-task scenario
  skipped by the standalone runner). The composition test now covers menu width
  with an active application and confirms initial tray/clock settings are loaded.
- The guest overlay is preserved under Tahoe's ignored
  `build/topbar-application-vm/disk.qcow2`; its post-move `qemu-img check` passed.
  The development guest was stopped after edition validation.
  No host desktop input or theme change was used.

Golden Gate staging: wrapper checks passed 41 cases. The prepared source passed
80 affected installer/layout/Nix/surface/edition regressions. Its component-only
VM installation succeeded; Edit → Select All selected the GTK4 document, and
light/dark menu rendering was inspected. The installed archive was
`a0b671640fd50bc263bb0e3d5912dbdebc026d11e193009881fc75262e3f6118`;
installed plugin SHA-256
`893f89d2f58a784b45cdc4c30f3ab8509f317242f7e9c053f9d9ec23b0bf1dee`.
This precedes the clock-font-default correction, covered by the later composition run.

Coverage limits: rapid focus switching was exercised in the private X11 test,
not end-to-end on Wayland; alternate keyboard layouts were not qualified.
Supported SDK/backend CI and exact-commit branch/release gates remain required.
This evidence is not a release approval or a replacement for those checks.

Initialization follow-up (development candidate): the native composition test
reproduced a stale QML property map (`customDateFormat` remained `ddd d` while
the stored value was correct). Publishing the loaded values to that map fixes
first creation. Legacy `Configuration/Appearance` values migrate to the
containment root, preserving any newer root values. The test covers both.
The enclosing panel's form factor and location are propagated to the embedded
containment so tray indicators do not initialize as desktop widgets.
`python -m pytest -q tests/test_globalmenu_model.py` passed in 29.15 seconds
before the form-factor follow-up; the affected composition test was then rebuilt
and passed four cases. The resumed neon VM rebuilt the component and created
a new bar: tray and clock were visible immediately, with no unsolicited popup.
The clock matched a standalone native clock with the same settings. Reviewed
frame SHA-256: `5a2527c093effc15196ed0d2cdfc3d6c08c22c94e93fc73d42ce1915069681d0`.
The first four v0.66 menu captures were rejected (102 previous approvals retained)
because the integrated accessories were absent; none were staged or published.
