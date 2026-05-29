"""Per-step sandbox install/uninstall — REMOVED.

The previous content ran each step's install/uninstall under
``tmp_path`` with ``$HOME`` and ``$XDG_*`` redirected. The asserts
checked that files arrived in the sandbox. This was useless: the
production install writes to ``~/.local/share/plasma/...`` and
``/usr/lib*/qt6/...`` — paths that Plasma actually walks. The
sandbox writes to ``$tmp_path/...`` which Plasma will not walk.
A green sandbox test cannot prove the real install would work.

The journal-scan crash guards from this file also moved away — the
``--since "24 hours ago"`` window made them flap on unrelated
historical events and silently pass even when this commit never
loaded the plugin. The session-cursor anchor was the right idea
but, with the install path mocked via MAC_TAHOE_SKIP_LIVE_APPLY,
there is nothing this run can compare against. A real journal
assertion needs a real plasmashell start.

Real coverage for step install/uninstall:
- ``tests/test_preflight.py::test_check_paths_passes_for_production_destinations``
  validates each step's DEST_* against the qmake6-reported allowed
  roots — catches the "lands in wrong dir" bug class.
- ``tests/containers/run_in_container.py`` runs the same
  destination check inside per-distro images so distro-specific
  libdir surprises (Fedora /usr/lib64 vs Arch /usr/lib) are
  caught.
- The maintainer running ``sudo ./install`` + ``sudo ./uninstall``
  on a real Plasma session catches the "the file went where I
  said but Plasma still ignored it" class. Not unit-testable.
"""
