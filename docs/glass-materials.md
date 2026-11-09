# Glass materials

Open **System Settings → Desktop Effects → Acrylic Glass → Configure**.
Choose a preset and press **Apply**. See the [light/dark preset gallery](../GLASS_PRESETS.md).

| Preset | Appearance |
| --- | --- |
| Tahoe (Clear) | Blur 5, refraction 0.02, no gradient. Tahoe default. |
| Tahoe (Frosted) | The same optics with blur 12. |
| Golden Gate (Official) | Blur 4, refraction 0.032, three-stop light/dark tint. Golden Gate default. |

The preset name “Official” is a material label in this independent project;
it does not imply Apple or KDE endorsement.

**Surface** controls the overall material. Blur softens the backdrop;
refraction bends it near the edges (0–0.2), with stronger values producing
more displacement. Brightness, contrast and saturation adjust the sampled
background while keeping application text independent.

**Fine tuning** controls the details: grain adds texture, color separation
splits edge colors, refraction width sets the band where bending happens,
and highlight width and strength control the reflective rim.

**Background gradient** provides the tint. Top, center and bottom each have
clearly labeled light-mode and dark-mode colors plus a shared tint strength.
Center position runs from 0 (top) to 1 (bottom). Colors follow each window's
palette. The retired uniform background and opacity controls are gone.
Disable the gradient for untinted glass.

The Dock keeps its v0.62.0 optics independently of these controls: blur 5,
RGB separation 12 with the existing 24% Dock attenuation, refraction 0.1,
refraction width 18, highlight width 3.5 and strength 0.1, brightness 1,
contrast 1, saturation 1.33 and 98% center coverage. It stays free of gradients.
Corner settings and rendering fixes continue to apply.

Selecting a preset replaces its surface, fine tuning and gradient values.
**Restore this preset** reapplies them; **Cancel** discards pending changes.
Saved adjustments survive reopening settings. Reinstalling reapplies the
edition's preset; corners and window rules are preserved.

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
