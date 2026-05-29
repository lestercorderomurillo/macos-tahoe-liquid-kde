"""Icons-step tmp-dir copy test — REMOVED.

The previous content copied icons into a tmp_path and asserted the
files arrived. It never verified that ``XDG_DATA_DIRS`` resolution
or ``gtk-update-icon-cache`` ran successfully on a real desktop;
the assertion was filesystem-level, the real failure mode is
runtime resolution.

If we want a real test here: install the theme, query
``gtk-launch foo`` with a known icon name, assert the icon was
located. That needs a live session.
"""
