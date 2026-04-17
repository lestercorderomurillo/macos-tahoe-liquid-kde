#!/usr/bin/env bash
# MacTahoe Liquid KDE — Nautilus step
# Installs Nautilus as the default file manager on KDE Plasma so users
# get the macOS-style Finder look.  The visual theming comes from the
# GTK step (sidebar, path bar, header, buttons); this step just makes
# sure Nautilus is present, is the default handler for folders, and
# loads any Nautilus-specific overrides from src/offline/nautilus/.

SRC_DIR="$OFFLINE/nautilus"
NAUTILUS_DESKTOP="org.gnome.Nautilus.desktop"
DOLPHIN_DESKTOP="org.kde.dolphin.desktop"
MIME_FOLDER="inode/directory"
MIME_SEARCH="application/x-gnome-saved-search"

deps() {
  # Nautilus itself (gnome filemanager package provides the `nautilus` binary)
  echo "nautilus"
}

_is_kde() {
  [[ "$XDG_CURRENT_DESKTOP" == *KDE* ]] \
    || [[ "$XDG_SESSION_DESKTOP" == *plasma* ]] \
    || [[ -n "$KDE_FULL_SESSION" ]] \
    || [[ -n "$KDE_SESSION_VERSION" ]]
}

_apply_overrides() {
  # Copy any Nautilus-specific config dropped in src/offline/nautilus/
  # (e.g. future gtk.css overrides or bookmarks).  Directory can be empty.
  [[ -d "$SRC_DIR" ]] || return 0
  shopt -s nullglob dotglob
  local copied=0
  for item in "$SRC_DIR"/*; do
    local base; base=$(basename "$item")
    # Skip docs
    [[ "$base" == README* ]] && continue
    case "$base" in
      bookmarks)    cp -f "$item" "$HOME/.config/gtk-3.0/bookmarks"      2>/dev/null && copied=$((copied+1)) ;;
      gtk.css)      mkdir -p "$HOME/.config/nautilus" && cp -f "$item" "$HOME/.config/nautilus/gtk.css" 2>/dev/null && copied=$((copied+1)) ;;
    esac
  done
  shopt -u nullglob dotglob
  [[ $copied -gt 0 ]] && ok "Applied $copied Nautilus override(s)"
}

_apply_gsettings() {
  # Match macOS Finder defaults where sensible
  command -v gsettings &>/dev/null || return 0
  gsettings set org.gnome.nautilus.preferences default-folder-viewer         'icon-view'     2>/dev/null || true
  gsettings set org.gnome.nautilus.preferences show-hidden-files             false           2>/dev/null || true
  gsettings set org.gnome.nautilus.preferences default-sort-order            'name'          2>/dev/null || true
  gsettings set org.gnome.nautilus.preferences show-create-link              true            2>/dev/null || true
  gsettings set org.gnome.nautilus.preferences click-policy                  'double'        2>/dev/null || true
  gsettings set org.gnome.nautilus.icon-view default-zoom-level              'small'         2>/dev/null || true
}

install() {
  if ! _is_kde; then
    warn "Not running under KDE Plasma — skipping Nautilus setup"
    return 0
  fi

  if ! command -v nautilus &>/dev/null; then
    fail "Nautilus not installed (expected deps to have provided it)"
    return 1
  fi

  # 1) Make Nautilus the default file manager for folders & saved searches
  if command -v xdg-mime &>/dev/null; then
    xdg-mime default "$NAUTILUS_DESKTOP" "$MIME_FOLDER" 2>/dev/null \
      && ok "Nautilus set as default for folders"
    xdg-mime default "$NAUTILUS_DESKTOP" "$MIME_SEARCH" 2>/dev/null || true
  else
    warn "xdg-mime not found — default file manager not changed"
  fi

  # 2) Apply optional overrides from offline/nautilus/
  _apply_overrides

  # 3) macOS-like Finder gsettings defaults
  _apply_gsettings

  # 4) Restart Nautilus so the GTK theme takes effect immediately
  nautilus -q &>/dev/null || true
  ok "Nautilus configured"
}

uninstall() {
  if ! _is_kde; then
    return 0
  fi

  # Restore Dolphin as default file manager (only if it's installed)
  if command -v dolphin &>/dev/null && command -v xdg-mime &>/dev/null; then
    xdg-mime default "$DOLPHIN_DESKTOP" "$MIME_FOLDER" 2>/dev/null \
      && ok "Dolphin restored as default for folders"
    xdg-mime default "$DOLPHIN_DESKTOP" "$MIME_SEARCH" 2>/dev/null || true
  fi

  # Remove Nautilus-specific override file if we wrote one
  rm -f "$HOME/.config/nautilus/gtk.css" 2>/dev/null || true
}
