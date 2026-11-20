# Identity decisions

## Evidence order

Use the current user request and project policy, then the matching edition's
actual macOS reference and the user's reviewed project counterpart. Inspect the
current implementation and capture provenance before trusting an older prose
summary. Resolve conflicting numbers or screenshots explicitly; a historical
capture is neither a fresh preview nor proof that HEAD renders identically.

Apple's [macOS guidance](https://developer.apple.com/design/human-interface-guidelines/designing-for-macos),
[menus](https://developer.apple.com/design/human-interface-guidelines/menus) and
[context menus](https://developer.apple.com/design/human-interface-guidelines/context-menus)
provide interaction principles. They do not supply the project's measured pixel
geometry or authorize using one macOS edition's photograph for the other.

## Repository map

`components.json` routes menus, notifications, launcher, controls, glass, icons,
window controls, installer, edition staging, Dock, Files, About and boot surfaces
to their implementation and existing references. Golden Gate contains wrapper,
defaults, pin and its own photographs; desktop implementation remains in Tahoe.
Qt/QML, native Qt/KWin, GTK, installer and boot surfaces have distinct rendering
paths. Consult only the affected branch of this map after the initial inventory.

## Reuse decision

A default toolkit control is acceptable when the project adapter already gives
it the reviewed appearance. When it introduces Breeze/native defaults that
conflict with an existing project counterpart, reuse that counterpart's renderer
and retain the new component's actions and semantics. Do not merely copy a few
colors into a second implementation.

For a shared primitive, inspect every direct consumer and the installation
fingerprints. A change to its content must invalidate each dependent payload;
unrelated payloads retain independent hashes. Keep a narrow executable behavior
regression for action routing, hidden/disabled items, dynamic models and focus
when those paths change.

## Render review

Compare the actual surface geometry, text baselines, label contrast, row rhythm,
selection inset, outer contour and layering at the same scale. Check content
with long/localized labels and the affected input states. Material transparency
is a surface fill, not whole-window opacity; text and controls stay legible.
Separate desktop behavior from documentation photography. Capture only the
changed component, preserve original provenance and wait for explicit approval
before promoting a visual candidate. Do not claim pixel identity from source
constants or a cropped image without the recorded environment.
