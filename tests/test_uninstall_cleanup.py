"""Uninstall cleanup text-content tests — REMOVED.

The previous content read kdedefaults / plasmarc / kwinrc after a
sandboxed uninstall and asserted specific text was present or
absent. That confirms the file-write path but not the resulting
Plasma session state — kwriteconfig6 might write the keys
correctly while plasmashell still reads stale cached values.

A real uninstall test: ``sudo ./install`` → ``sudo ./uninstall`` on
a live session, then assert plasmashell shows Breeze defaults
again. Needs a live session — out of scope.
"""
