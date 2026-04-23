# Nautilus overrides

This directory holds optional Nautilus-specific overrides picked up by
`installer/steps/nautilus.py` on install.

Accepted files:

| File         | Destination                         | Purpose                               |
|--------------|-------------------------------------|---------------------------------------|
| `gtk.css`    | `~/.config/nautilus/gtk.css`        | Nautilus-only CSS overrides (opt-in)  |
| `bookmarks`  | `~/.config/gtk-3.0/bookmarks`       | Default sidebar bookmarks             |

The bulk of the macOS-style theming (sidebar, path bar, header buttons,
window chrome) is delivered by the **GTK theme** at `src/offline/gtk/`,
which already contains 1.5k+ Nautilus-specific selectors. This directory
is only for per-machine or per-version tweaks that don't belong in the
shared theme.

Leave the directory otherwise empty — the step handles installation,
default-filemanager wiring, a few macOS-like gsettings defaults, and the
GTK/GNOME headerbar button layout (`close,minimize,maximize:`).
