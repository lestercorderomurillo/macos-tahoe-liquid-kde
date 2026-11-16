# Focused regression qualification: v0.72.10

The repair covers issues #128 (Btrfs startup device and zram), #130 (Control
Center physical-network summary, bounded text, battery visibility, media spacing
and reactive monitor labels), and #131 (accent selection contrast).

The accent generator discarded the chosen color's brightness. Gray therefore
became nearly white while selection text remained white. The generator now
preserves brightness and pairs selection text with the generated background in
GTK, KDE and Qt palettes. Status colors, geometry and alpha remain unchanged.

## Passing evidence

- `pytest tests/test_about_info.py -k "startup_disk or lsblk"`: 11 passed.
- `pytest tests/test_installer_wizard.py -k "accent_changes or accent_preserves"`:
  2 passed; all eight accents meet 4.5:1 for the tested selection colors.
- `pytest tests/test_gtk_upgrade.py`: four ownership/upgrade cases passed,
  including replacing project-generated overrides while preserving custom CSS.
- `pytest tests/test_localization.py`: seven passed. Updated existing Control
  Center catalogs also passed `msgfmt --check --check-format`.
- `tests/desktop_controls_probe.py` in the disposable Plasma VM: passed.
  Covers Docker bridge exclusion, Ethernet/Wi-Fi changes, battery insertion and
  absence, all three monitor labels, and existing audio/network actions.
- `tests/gtk_accent_probe.py <source> 3` and `... 4`, each on private D-Bus/Xvfb:
  passed using real GTK. One window remains alive across light/dark/light,
  eight accents and selected/hover/focus/backdrop states. Text/background
  colors resolved by GTK meet 4.5:1 in every tested case.
- Focused installer steps `gtk.install()`, `color_schemes.install()` and
  `plasmoids.install()` ran twice after the installer's normal
  `_require_root_and_drop_to_user()` setup, with gray selected and reset-layout
  disabled. Both phases completed without recorded installer errors. The
  desktop user's installed CSS contained `accent_bg_color #8e8e93`.
- The installed gray appearance was switched light/dark/light with Files kept
  open (PID 113175 throughout). Reviewed captures show readable selection in
  both modes. The Control Center preview shows separated media artwork/text
  and no battery tile on the battery-free VM.
- KWin activated Files while the installed launcher was open: the launcher
  disappeared after losing focus. No launcher code change was necessary for
  this observed case.

## Environment and limits

Disposable QEMU/KVM KDE neon Plasma 6.8.1 / Qt 6.11.1 guest, based on the
previous permission-qualified overlay; native module binaries were unchanged.
The host desktop was not used. Initial attempts using the older base VM and a
container without all required QML/PyGObject packages were environment failures,
not passing evidence; qualification used the fully provisioned disposable guest.
The first capture attempt had DPMS dimming and was rejected. Only reviewed,
subsequent frames are published. This was focused step install/reinstall
qualification, not a new complete wizard or distro qualification run.

Golden Gate stages this same shared repair; its matching immutable pin and
archive checksum are verified at publication. These preview images are Tahoe
qualification frames, not Golden Gate photographs. Existing README and installer
galleries retain their original provenance.

The reported later Breeze reset was not reproduced during these transitions;
this release does not claim a separate fix for that unobserved race. French
Control Center translations and independent icon-appearance selection are not
implemented by this repair. No automatic schedule boundary or complete new
cross-distro desktop matrix was run locally. Full CI runs after publication.
