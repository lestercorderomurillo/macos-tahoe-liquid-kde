# Glass materials

Open **System Settings → Desktop Effects → Acrylic Glass → Configure**.
Choose a preset, adjust its controls if desired, and press **Apply**.

| Preset | Appearance |
| --- | --- |
| Tahoe | Strongly blurred glass with a narrow refracted edge. Default in Tahoe. |
| Golden Gate | Tahoe's optical values with an 85% black tint that fades out at 55% of menu height. The lower 45% and Dock stay untinted. Default in Golden Gate. |

Each preset replaces the complete material: blur, opacity, refraction, color
separation, highlights, grain, brightness, contrast, saturation and gradient.
There is one smooth blur implementation. **Fine tuning** exposes the detailed
controls without requiring a choice of blur algorithm.
Both presets use a blur strength of 5 on the 0–20 scale, grain 1,
RGB separation 12, magnification 0.1, and saturation 1.33. The refracted
edge is 18 wide, with highlight width 3.5 and strength 0.1. Brightness,
contrast and material opacity remain 1. The gradient stays specific to
each preset.

**Glass opacity** controls how much of the blurred material covers the original
background. Keep it at 1 for full material coverage; lower it to reveal more
of the sharp background. The Dock uses a clearer centre while preserving the
refracted rim; applet popups retain full blur coverage. Text and icons retain
their own opacity. Gradient
colors and strengths are independent of this coverage, so a lighter bottom
does not lose its blur. Disable **Enable gradient** for an untinted material.

Selecting another preset replaces your material adjustments. **Restore this
preset** reapplies the selected preset, including its gradient colors.
**Cancel** discards pending changes. Saved adjustments survive reopening the
settings. Installing or reinstalling Acrylic Glass reapplies the complete
preset of the repository being run: **Tahoe** from Tahoe, **Golden Gate** from
Golden Gate. This replaces previous material selections and optical adjustments,
including the gradient toggle and colors. Corners and window rules remain
independent and are preserved.

Tahoe Plasma applet popups, tooltips, Qt menus and the detached search capsule
use a 55% white fill in light mode and a slightly clearer 48% black fill in dark
mode. Golden Gate installs a nearly clear 1% white fill in both modes, letting
the upper gradient supply the dark tint while the lower part stays clear.
Golden Gate light native Qt menus use a 60% white translucent surface so their
dark system text remains readable above that gradient. This exception affects
only the light Golden Gate Kvantum menu assets; dark menus, Tahoe, dialogs,
tooltips and Plasma surfaces keep their existing fills.
Text follows the system window foreground throughout. The Dock
uses identical assets in both modes and retains its thin transparent fill.
Contours use a 0.75 logical-pixel dark outer line and a 0.75 logical-pixel
light inner line, following each surface's native rounded mask. The Dock uses
24% opacity on the outer line and 30% on the inner line for a visible thin edge. The gradient
only tints the blurred backdrop; it does not change text, blur coverage,
contours or the Dock. Both editions share surface geometry with edition-specific
fills; there is no separate reduced-transparency mode.
GTK client-side popups keep their own readable fills; KWin cannot blur those
surfaces in the same way as Plasma popups and Qt menus.

## Visual references

Acrylic Glass builds separate Wayland and X11 modules against each backend's
KWin SDK. The installer requests the SDK for the current desktop session and
also builds the other backend when its SDK is already installed. Their plugin
and settings paths stay separate. X11 support preserves the existing material
presets, shaders and light/dark surface fills.

The X11 regression probe starts its own Xvfb display and D-Bus session, checks
the compositor PID, and verifies the exact built module is loaded and active.
It does not install the module or interact with the running desktop.

These are independently tuned KDE materials, inspired by Apple's published
screenshots and design guidance; they do not reproduce Apple's renderer.

- [macOS Tahoe 26 introduction](https://www.apple.com/newsroom/2025/06/macos-tahoe-26-makes-the-mac-more-capable-productive-and-intelligent-than-ever/): translucent Dock and controls that reflect the surrounding desktop.
- [macOS Golden Gate](https://www.apple.com/os/macos/): more uniform refraction and improved contrast.
- [Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/): blur and tint preserve legibility, with clearer and more substantial materials for different surfaces.

The Golden Gate preset adds a black upper gradient to menus in both appearance
modes. It starts at 85% opacity and reaches zero at 55% of the surface height.
The lower 45% retains untinted blurred glass. Launcher text has a soft, low-opacity
halo: white behind dark text and black behind light text. The halo is centered
and diffused rather than drawn as a hard outline. In light mode, category pills
use a translucent white backing to separate dark labels from the upper gradient.
The Dock and panels use a clearer surface without the gradient: a smooth blur, less grain and 98% centre
coverage, with a mild angled refraction and a thin bright edge. Its compact
Dual Kawase pyramid uses up to three levels, followed by a dense Gaussian
finish. The finish samples adjacent texels instead of separating image copies.
The Dock uses more blur and less refraction and color separation
to soften the backdrop without stretching it into a wide band.
The Dock's blur taps and centre coverage soften backdrop detail without
making the glass opaque. The lens bends the backdrop inward at an angle near
the rim, with its strength independent of the Dock's length.
These adjustments follow the selected material and its
controls without changing saved settings; contextual menus keep their full blur.
Applet popups retain the selected blur with full centre coverage. Golden Gate
and Tahoe share every optical value; only the gradient differs. These numerical
settings are project tuning, not values supplied by Apple. The black gradient
darkens lighter backdrops and leaves a fully black backdrop black.
