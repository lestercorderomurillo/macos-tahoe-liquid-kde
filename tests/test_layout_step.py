"""Layout-step appletsrc regex tests — REMOVED.

The previous content drove the layout step, read the resulting
plasma-org.kde.plasma.desktop-appletsrc, and asserted specific
regex substrings were present. That confirms the JS layout script
wrote what we expected — it does NOT confirm plasmashell can
render the resulting panel. The interesting failure is "addWidget
referenced a plugin Plasma cannot resolve", and that one is
covered by:

- ``tests/test_preflight.py::test_layout_js_references_real_plasmoid_ids``
  — every addWidget("org.kde.mac.…") call in the layout JS must
  match a plasmoid that actually exists on disk with that
  metadata.Id.

That preflight check catches the real bug shape (layout JS
references a plasmoid that does not exist) without depending on
appletsrc text we never controlled directly.
"""
