"""Generate Golden Gate traffic-light controls for Aurorae and GTK offline."""

from pathlib import Path
import re
import shutil

from theme_switch import decoration_theme, window_control_style

EDITIONS = ("MacTahoe", "MacGoldenGate")
STATES = ("active", "inactive", "hover", "pressed", "deactivated",
          "hover-inactive", "pressed-inactive", "deactivated-inactive")
BUTTONS = ("close", "minimize", "maximize", "restore")
COLORS = {
    "close": ("#ff6f66", "#f77c74", "#f48983", "#9e2019"),
    "minimize": ("#fdb82c", "#fdc937", "#fdd341", "#ad6200"),
    "maximize": ("#60ce2f", "#81d55b", "#95d976", "#267c18"),
    "restore": ("#60ce2f", "#81d55b", "#95d976", "#267c18"),
}
GLYPHS = {
    "close": 'M5.6 5.6l4.8 4.8m0-4.8l-4.8 4.8',
    "minimize": 'M5 8h6',
    "maximize": 'M5 8V5h3M8 11h3V8',
    "restore": 'M5 8h3V5M8 11V8h3',
}


def _button(button: str, mode: str, state: str, index: int) -> str:
    top, middle, bottom, ink = COLORS[button]
    neutral = state in ("inactive", "deactivated", "deactivated-inactive")
    disabled = state.startswith("deactivated")
    dark = mode == "Dark"
    if dark and button in ("close", "minimize", "maximize", "restore"):
        top, middle, bottom = {
            "close": ("#f86055", "#f45347", "#ef6664"),
            "minimize": ("#fcb501", "#fbb200", "#fecd32"),
            "maximize": ("#3bc203", "#32b409", "#4dc13a"),
            "restore": ("#3bc203", "#32b409", "#4dc13a"),
        }[button]
    if neutral:
        top, middle, bottom = (("#515151", "#484848", "#505050") if dark
                               else ("#eeeeef", "#e0e0e3", "#ededee"))
    prefix = f"b{index}"
    # Top/bottom reflections survive loss of focus. Disabled controls are
    # deliberately fainter, unlike inactive but still actionable controls.
    shine = ".65" if dark else ".18"
    opacity = '.45' if disabled else '1'
    glyph = (f'<path d="{GLYPHS[button]}" fill="none" stroke="{ink}" '
             'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>') if state in (
                 "hover", "pressed", "hover-inactive", "pressed-inactive") else ''
    if button in ("maximize", "restore") and glyph:
        triangles = ("M4.8 4.8h4.6l-4.6 4.6z M11.2 11.2H6.6l4.6-4.6z" if button == "maximize"
                     else "M7.5 7.5H4.3l3.2-3.2z M8.5 8.5h3.2l-3.2 3.2z")
        glyph = f'<path d="{triangles}" fill="{ink}"/>'
    pressed = '<circle cx="8" cy="8" r="6.65" fill="#000" opacity=".13"/>' if state.startswith("pressed") else ''
    return f'''<defs>
  <linearGradient id="{prefix}-body" x2="0" y2="1">
    <stop stop-color="{top}"/><stop offset=".5" stop-color="{middle}"/>
    <stop offset="1" stop-color="{bottom}"/>
  </linearGradient>
  <linearGradient id="{prefix}-rim" x2="0" y2="1">
    <stop stop-color="#fff" stop-opacity="{shine}"/>
    <stop offset=".32" stop-color="#fff" stop-opacity=".03"/>
    <stop offset=".68" stop-color="#fff" stop-opacity=".03"/>
    <stop offset="1" stop-color="#fff" stop-opacity="{shine}"/>
  </linearGradient>
  <radialGradient id="{prefix}-glow" cx=".5" cy="1" r=".7">
    <stop stop-color="#fff" stop-opacity="{'.13' if dark and not neutral else '.02'}"/>
    <stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
</defs>
<g opacity="{opacity}">
  <circle cx="8" cy="8.5" r="7" fill="#000" opacity="{'.20' if dark else '.08'}"/>
  <circle cx="8" cy="8" r="6.8" fill="url(#{prefix}-body)"/>
  <circle cx="8" cy="8" r="6.8" fill="url(#{prefix}-glow)"/>
  <circle cx="8" cy="8" r="6.8" fill="none" stroke="#000" stroke-opacity=".18" stroke-width=".4"/>
  <circle cx="8" cy="8" r="6.55" fill="none" stroke="url(#{prefix}-rim)" stroke-width=".6"/>
  {pressed}{glyph}
</g>'''


def button_svg(button: str, mode: str, state: str | None = None) -> str:
    """A complete Aurorae state sheet or a single scalable GTK button."""
    if button not in BUTTONS or mode not in ("Light", "Dark") or (state is not None and state not in STATES):
        raise ValueError("Unknown window control variant")
    states = (state,) if state else STATES
    groups = []
    for index, current in enumerate(states):
        groups.append(f'<g id="{current}-center" transform="translate(0 {index * 16})">'
                      '<rect width="16" height="16" fill="none"/>'
                      + _button(button, mode, current, index) + '</g>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="16" '
            f'height="{16 * len(states)}" viewBox="0 0 16 {16 * len(states)}">\n'
            + '\n'.join(groups) + '\n</svg>\n')


def assemble_aurorae(source: Path, destination: Path, mode: str, edition: str) -> None:
    """Assemble both editions from the common frame and metadata templates."""
    if edition not in EDITIONS or mode not in ("Light", "Dark"):
        raise ValueError("Unknown decoration variant")
    destination.mkdir(parents=True, exist_ok=True)
    base = f"MacTahoeLiquidKde-{mode}"
    name = f"{edition}LiquidKde-{mode}"
    frame = source / base / "decoration.svg"
    if frame.is_file():
        shutil.copy2(frame, destination / "decoration.svg")
    rc = source / f"{base}rc"
    if rc.is_file():
        text = rc.read_text()
        if edition == "MacGoldenGate":
            text = re.sub(r"(?m)^ButtonSpacing=\d+$", "ButtonSpacing=7", text)
        (destination / f"{name}rc").write_text(text)
    for icon in (source / f"icons-{mode}").glob("*.svg"):
        shutil.copy2(icon, destination / icon.name)
    if edition == "MacGoldenGate":
        for button in BUTTONS:
            (destination / f"{button}.svg").write_text(button_svg(button, mode))
    for filename in ("metadata.desktop", "metadata.json"):
        template = source / filename
        if template.is_file():
            (destination / filename).write_text(template.read_text().replace("theme_name", name))


def apply_gtk_controls(theme: Path) -> None:
    """Apply the chosen controls to fresh staged GTK sources in either edition."""
    if window_control_style() != "glassy":
        return
    states = {'': 'active', '-hover': 'hover', '-active': 'pressed',
              '-backdrop': 'inactive', '-backdrop-hover': 'hover-inactive'}
    for version in (3, 4):
        folder = theme / f"gtk-{version}.0"
        if not folder.is_dir():
            continue
        assets = folder / "windows-assets"
        assets.mkdir(exist_ok=True)
        for mode in ("Light", "Dark"):
            for button in ("close", "minimize", "maximize", "restore"):
                for suffix, state in states.items():
                    name = f"golden-gate-{button}{suffix}-{mode.lower()}.svg"
                    (assets / name).write_text(button_svg(button, mode, state))

        def replace(match):
            button, suffix, dark = match.group(1, 2, 3)
            suffix = suffix or ""
            mode = "dark" if dark else "light"
            return f'url("windows-assets/golden-gate-{button}{suffix}-{mode}.svg")'

        pattern = (r'-gtk-scaled\(url\("windows-assets/titlebutton-'
                   r'(close|minimize|maximize|restore)(-backdrop-hover|-backdrop|-hover|-active)?'
                   r'(-dark)?\.png"\), url\("windows-assets/titlebutton-[^"\n]+@2\.png"\)\)')
        for css in folder.glob("*.css"):
            if not css.is_symlink():
                css.write_text(re.sub(pattern, replace, css.read_text()))


def apply_global_theme(theme: Path) -> None:
    """Keep System Settings' global-theme activation on the staged edition."""
    path = theme / "contents/defaults"
    if path.is_file():
        path.write_text(re.sub(
            r"(?m)^theme=__aurorae__svg__Mac(?:Tahoe|GoldenGate)LiquidKde-(Light|Dark)$",
            lambda match: f"theme=__aurorae__svg__{decoration_theme(match[1].lower())}",
            path.read_text()))
