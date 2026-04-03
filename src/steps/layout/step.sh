#!/usr/bin/env bash
# MacTahoe Liquid KDE — layout step

LAYOUT_SCRIPT="$OFFLINE/layouts/mac-tahoe.js"

deps() {
  echo "qdbus6:qt6-tools"
}

install() {
  # panel colorizer check
  local colorizer_dir="$HOME/.local/share/plasma/plasmoids/luisbocanegra.panel.colorizer"
  if [[ -d "$colorizer_dir" ]]; then
    ok "Panel Colorizer"
  else
    warn "Panel Colorizer not found — installing..."
    if command -v kpackagetool6 &>/dev/null; then
      kpackagetool6 -i "https://store.kde.org/p/2130967" -t Plasma/Applet &>/dev/null \
        || kpackagetool6 --install "luisbocanegra.panel.colorizer" -t Plasma/Applet &>/dev/null \
        || true
    fi
    if [[ ! -d "$colorizer_dir" ]]; then
      if command -v paru &>/dev/null; then
        paru -S --noconfirm plasma6-applets-panel-colorizer 2>/dev/null || true
      elif command -v yay &>/dev/null; then
        yay -S --noconfirm plasma6-applets-panel-colorizer 2>/dev/null || true
      fi
    fi
    [[ -d "$colorizer_dir" ]] && ok "Panel Colorizer (installed)" \
      || warn "Panel Colorizer not installed — top bar won't be transparent. Install manually from KDE Store."
  fi

  [[ -f "$LAYOUT_SCRIPT" ]] || { warn "Layout script not found — skipping"; return 0; }

  local q
  q=$(qdbus_cmd) || { warn "qdbus not found — layout not installed"; return 0; }

  "$q" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$LAYOUT_SCRIPT")" &>/dev/null \
    && ok "Layout installed" \
    || warn "layout failed — set layout manually"
  sleep 3

  # patch plasmashellrc: JS scripting API doesn't expose panelOpacity or floatingApplets
  local prc="$HOME/.config/plasmashellrc"
  if [[ -f "$prc" ]]; then
    python3 -c "
import re, sys
text = open('$prc').read()
def fix(m):
    section = m.group(0)
    if 'floating=1' in section:
        if 'panelOpacity=' in section:
            section = re.sub(r'panelOpacity=\d+', 'panelOpacity=2', section)
        else:
            section = section.rstrip() + '\npanelOpacity=2\n'
    if 'floating=0' in section:
        if 'floatingApplets=' in section:
            section = re.sub(r'floatingApplets=\d+', 'floatingApplets=1', section)
        else:
            section = section.rstrip() + '\nfloatingApplets=1\n'
    return section
result = re.sub(r'(\[PlasmaViews\]\[Panel \d+\]\n(?:[^\[]*\n)*)', fix, text)
open('$prc', 'w').write(result)
" 2>/dev/null && ok "Dock installed" || true
  fi
}

uninstall() {
  local layout="$OFFLINE/layouts/default.js"
  if [[ -f "$layout" ]]; then
    local q
    q=$(qdbus_cmd) && {
      "$q" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$layout")" &>/dev/null \
        && ok "Layout reset" || warn "layout reset failed"
    }
  fi
}
