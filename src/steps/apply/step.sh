#!/usr/bin/env bash
# MacTahoe Liquid KDE — apply step (final config writes, cache flush, restart)

install() {
  # ── KDE config ─────────────────────────────────────────────
  if command -v kwriteconfig6 &>/dev/null; then
    if [[ "${FEAT_FONTS:-true}" == "true" ]]; then
      kw_write --file kdeglobals --group General --key font                 "SF Pro Text,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key menuFont             "SF Pro Text,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key toolBarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key taskbarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key smallestReadableFont "SF Pro Text,8,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key fixed                "SF Mono,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group WM      --key activeFont           "SF Pro Display,11,-1,5,63,0,0,0,0,0"
      ok "Fonts installed"
    fi
  fi

  # ── wallpaper ──────────────────────────────────────────────
  if [[ "${FEAT_WALLPAPERS:-true}" == "true" ]]; then
    local wp_base="$HOME/.local/share/wallpapers"
    local wp_path=""
    case "${THEME_MODE:-auto}" in
      light) wp_path="$wp_base/MacTahoe-Light" ;;
      dark)  wp_path="$wp_base/MacTahoe-Dark" ;;
      *)
        # auto: pick based on time of day (light 6–18, dark otherwise)
        local hour; hour=$(date +%H)
        if (( 10#$hour >= 6 && 10#$hour < 18 )); then
          wp_path="$wp_base/MacTahoe-Light"
        else
          wp_path="$wp_base/MacTahoe-Dark"
        fi
        ;;
    esac
    if [[ -d "$wp_path" ]] && command -v plasma-apply-wallpaperimage &>/dev/null; then
      plasma-apply-wallpaperimage "$wp_path" &>/dev/null || true
      ok "Wallpaper applied ($(basename "$wp_path"))"
    fi
  fi

  # ── flush caches ───────────────────────────────────────────
  rm -rf "$HOME/.cache/icon-cache.kcache" 2>/dev/null || true
  rm -rf "$HOME/.cache/kiconthemes" 2>/dev/null || true
  rm -rf "$HOME/.cache/ksvg-elements" 2>/dev/null || true
  rm -rf "$HOME/.cache/plasma-svgelements-"* 2>/dev/null || true
  rm -rf "$HOME/.cache/plasma_theme_"* 2>/dev/null || true
  rm -rf "$HOME/.cache/plasmashell"* 2>/dev/null || true
  find "$HOME/.cache" -maxdepth 1 -name "ksycoca6*" -delete 2>/dev/null || true
  rm -rf "$HOME/.cache/gtk-3.0/" 2>/dev/null || true
  rm -rf "$HOME/.cache/gtk-4.0/" 2>/dev/null || true
  kbuildsycoca6 --noincremental 2>/dev/null || true
  ok "Caches flushed"

  # ── apply theme ────────────────────────────────────────────
  local switch="$HOME/.local/bin/mac-tahoe-theme-switch"
  if [[ -x "$switch" ]]; then
    # "install" context skips plasma-apply-lookandfeel and refreshCurrentShell
    # which crash plasmashell (QML teardown race). The plasma restart at the
    # end of install loads the correct theme from config. Kvantum/GTK are
    # applied immediately so already-open Qt/GTK windows pick up the change.
    "$switch" "$THEME_MODE" install &>/dev/null
    ok "Theme applied ($THEME_MODE)"
  fi

  command -v nautilus &>/dev/null && { nautilus -q 2>/dev/null || true; ok "Nautilus restarted"; }

  # ── restart KWin ───────────────────────────────────────────
  echo -ne "  …  Restarting KWin"
  local q
  q=$(qdbus_cmd) && {
    if [[ "${FEAT_ACRYLIC_GLASS:-true}" == "true" ]]; then
      "$q" org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect liquidglass &>/dev/null || true
      sleep 1
    fi
    "$q" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true
    sleep 3
  }
  echo -e "\r  ${GREEN}✓${RESET}  KWin restarted "

}

# restart plasma — called by orchestrator AFTER layout is applied
restart_plasma() {
  echo -ne "  …  Restarting Plasma"
  # let panels created by layout script fully initialise and flush config
  sleep 6
  # SIGKILL skips the QML engine teardown race (SIGABRT/SIGSEGV in
  # org.kde.panel.so → Applet::~Applet → deleteChildren cascade).
  # kquitapp6/SIGTERM trigger a graceful quit that always crashes.
  # Config is already on disk — layout JS + plasmashellrc patching ran above.
  systemctl --user kill --signal=KILL plasma-plasmashell 2>/dev/null \
    || kill -KILL "$(pgrep -x plasmashell)" 2>/dev/null || true
  sleep 1
  # systemd Restart=on-failure (100ms) handles restart; explicit start as fallback
  systemctl --user start plasma-plasmashell 2>/dev/null || kstart plasmashell 2>/dev/null &
  for _i in $(seq 1 15); do pgrep -x plasmashell &>/dev/null && break; sleep 1; done
  sleep 4
  echo -e "\r  ${GREEN}✓${RESET}  Plasma restarted   "
}

uninstall() {
  # ── reset to Breeze defaults ───────────────────────────────
  if command -v kwriteconfig6 &>/dev/null; then
    if [[ "${FEAT_FONTS:-true}" == "true" ]]; then
      kw_write --file kdeglobals --group General --key font                 "Noto Sans,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key menuFont             "Noto Sans,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key toolBarFont          "Noto Sans,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key taskbarFont          "Noto Sans,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key smallestReadableFont "Noto Sans,8,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group General --key fixed                "Hack,10,-1,5,50,0,0,0,0,0"
      kw_write --file kdeglobals --group WM      --key activeFont           "Noto Sans,10,-1,5,50,0,0,0,0,0"
      ok "Fonts reset"
    fi
    if [[ "${FEAT_CURSORS:-true}" == "true" ]]; then
      kw_write --file kcminputrc --group Mouse --key cursorTheme "breeze_cursors"
      plasma-apply-cursortheme "breeze_cursors" &>/dev/null || true
      ok "Cursor reset"
    fi
    if [[ "${FEAT_ICONS:-true}" == "true" ]]; then
      kw_write --file kdeglobals --group Icons --key Theme "breeze"
      dbus-send --session --type=signal /KIconLoader org.kde.KIconLoader.iconChanged int32:0 2>/dev/null || true
      ok "Icons reset"
    fi
    if [[ "${FEAT_WALLPAPERS:-true}" == "true" ]]; then
      for p in /usr/share/wallpapers/Next /usr/share/wallpapers/Breeze /usr/share/wallpapers/Flow; do
        [[ -d "$p" ]] && { plasma-apply-wallpaperimage "$p" &>/dev/null || true; ok "Wallpaper reset"; break; }
      done
    fi
    plasma-apply-colorscheme BreezeLight &>/dev/null || true
    ok "Color scheme reset"
  fi

  # ── flush caches ───────────────────────────────────────────
  rm -rf "$HOME/.cache/icon-cache.kcache" 2>/dev/null || true
  rm -rf "$HOME/.cache/kiconthemes" 2>/dev/null || true
  rm -rf "$HOME/.cache/ksvg-elements" 2>/dev/null || true
  rm -rf "$HOME/.cache/plasma-svgelements-"* 2>/dev/null || true
  rm -rf "$HOME/.cache/plasma_theme_"* 2>/dev/null || true
  rm -rf "$HOME/.cache/plasmashell"* 2>/dev/null || true
  find "$HOME/.cache" -maxdepth 1 -name "ksycoca6*" -delete 2>/dev/null || true
  rm -rf "$HOME/.cache/gtk-3.0/" 2>/dev/null || true
  rm -rf "$HOME/.cache/gtk-4.0/" 2>/dev/null || true
  kbuildsycoca6 --noincremental 2>/dev/null || true
  ok "Caches flushed"

  # ── reconfigure KWin (no plasma restart — caller handles that) ──
  kwin_reconfigure
  sleep 2
  ok "KWin reconfigured"
}
