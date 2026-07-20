"""Semantic corner metrics shared by generated theme configuration.

The radii are deliberately grouped by surface role.  Static QML, CSS, and SVG
assets cannot import Python, so the regression suite checks their geometry
against these values without flattening compact controls or pills into the
window radius.
"""

WINDOW_CORNER_RADIUS = 22
DOCK_CORNER_RADIUS = 22
DIALOG_CORNER_RADIUS = 14
TOOLTIP_CORNER_RADIUS = 14
POPUP_CORNER_RADIUS = 6
MENU_CORNER_RADIUS = 0


def config_value(radius: int) -> str:
    """Return the integer text format expected by KConfig writers."""
    return str(radius)
