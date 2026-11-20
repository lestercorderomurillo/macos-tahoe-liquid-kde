---
name: macos-visual-identity
description: Preserve the reviewed macOS identity of Tahoe and Golden Gate when creating, changing or reviewing visible desktop UI, including menus, typography, glass, icons and controls. Use the matching approved component and edition instead of inventing a new style.
---

# macOS visual identity

Before implementing a visible change, identify its component and intended macOS
edition. Use the active `AGENTS.md` and the user's chosen reference. Discover the
current source and recorded reference with this read-only command:

```bash
python3 <skill-directory>/scripts/describe_identity.py --tahoe <tahoe-checkout> --component <component>
```

Run with `--help` for component names. The report contains current source paths
and hashes, not copied design tokens. It does not certify appearance or approval.
Read [identity decisions](references/identity-decisions.md) for the review method.

Start from the closest approved counterpart: notification options and launcher
options use `MacOptionsMenu.qml`; native Qt menus use their existing style
adapter. Match that family's type, spacing, corner contour, selection, borders,
material, focus and interaction before adding visual overrides. Prefer a shared
primitive when surfaces have the same role. Preserve deliberate differences
between families, platforms and editions; consistency does not mean styling
every control as a menu.

Keep edition identity independent of a saved launcher layout preset. Read the
live material and effective appearance; preserve saved optics, explicit choices,
wallpapers and unrelated preferences. Use original bundled artwork and existing
font/glyph generators, with their provenance, for symbols. Do not substitute a
new drawing, icon theme, generic card, halo or decorative treatment to approximate
an already reviewed asset.

Before calling a visible fix complete, inspect actual rendered states at the
same logical scale as its reference, including the affected light/dark modes,
hover/selection and keyboard behavior. Use an isolated VM and show the focused
preview to the user under the repository's approval gate. A compile, token match
or this skill's source report cannot establish that the result looks correct.
Scope corrections to the requested component and its direct shared dependencies;
record other identity inconsistencies without expanding the task into a redesign.
