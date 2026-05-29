"""Acrylic Glass schema policing — REMOVED.

54 tests pinning the layout of the KWin effect's kcfg / UI / KCM
files — schema names, group ordering, key spellings. Once the
``Glass*`` → ``AcrylicGlass*`` rename landed in v0.16, this whole
file was solving a problem that does not exist any more: it was
preventing the *next* maintainer from accidentally reverting the
rename. That is policy enforcement, not behaviour testing.

The branding rule itself is documented in CLAUDE.md /
AGENTS.md / [[acrylic-glass-branding]] memory. A reviewer
catches it; a sandbox test does not need to.

What WOULD be a real test for this surface: install the effect,
``qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect
liquidglass`` returns true, ``activeEffects`` lists it. That needs
KWin. Out of scope here.
"""
