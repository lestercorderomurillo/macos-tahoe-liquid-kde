"""SVG transparency / opacity tests — REMOVED.

The previous content opened the wallpaper / panel SVGs and asserted
that specific ``fill-opacity`` attributes had specific numeric
values. Those values were chosen visually in an SVG editor, not by
any runtime contract; pinning them in pytest meant every wallpaper
tweak required updating a test that did not predict the visual
outcome anyway.

Visual correctness on a live Plasma session is what actually
matters here, and the suite cannot exercise that. Lock the screen
to a clean Plasma session, install the theme, eyeball the
wallpaper — that is the only honest check for "transparency looks
right".
"""
