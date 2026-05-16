#!/usr/bin/env bash
# Run plymouth in debug mode on THIS machine. Standard plymouth dev
# workflow per freedesktop.org/wiki/Software/Plymouth/Themes/:
#
#   1. copy theme into /usr/share/plymouth/themes/
#   2. plymouthd --no-daemon --debug --mode=X
#   3. plymouth show-splash
#   4. screenshot, plymouth --quit, remove the theme copy
#
# No Docker. No VM. No initramfs rebuild. Plymouth's splash will
# briefly appear on your screen (~3s per mode) because the X11
# renderer draws to your actual XWayland display.

# NOTE: set -u + pipefail but NOT -e. We want each mode to run even
# if the previous one's screenshot failed, and we want the cleanup
# trap to fire on a botched run.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_ui.sh
source "$HERE/_ui.sh"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SRC="$REPO_ROOT/src/offline/plymouth/MacTahoeLiquidKde"
DEST="/usr/share/plymouth/themes/MacTahoeLiquidKde"
OUT="$HERE/output"

ui_section "Plymouth render test (host, debug mode)"

# ── must run as root ────────────────────────────────────────────────────
# plymouthd refuses to run unless uid==0, and we copy into
# /usr/share/plymouth/themes/. Mirror the ./uninstall convention:
# require sudo upfront from the OUTER shell (where the password
# prompt actually works), don't try to prompt from inside the script
# — pam_faillock-cascade nightmares on terminals where sudo can't
# read the password.

if [[ $EUID -ne 0 ]]; then
    ui_fail "test --vm requires root — plymouthd does not run as user"
    echo
    ui_info "Re-run as:  sudo ./test --vm"
    exit 1
fi

# DISPLAY is needed for plymouth's X11 renderer + the screenshot.
# When invoked via sudo, DISPLAY is usually preserved on Arch, but
# fall back to :0 (the only sane default for a single-seat box).
: "${DISPLAY:=:0}"
export DISPLAY

# Same for XAUTHORITY — sudo passes it on Arch by default, but make
# sure xwininfo / import can connect when called via sudo.
if [[ -z "${XAUTHORITY:-}" && -n "${SUDO_USER:-}" ]]; then
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [[ -f "$USER_HOME/.Xauthority" ]]; then
        export XAUTHORITY="$USER_HOME/.Xauthority"
    fi
fi

needed=()
command -v plymouthd >/dev/null || needed+=(plymouth)
command -v spectacle >/dev/null || needed+=(spectacle)
command -v xwininfo  >/dev/null || needed+=(xorg-xwininfo)
command -v xdotool   >/dev/null || needed+=(xdotool)
if [[ ${#needed[@]} -gt 0 ]]; then
    ui_step "installing missing packages: ${needed[*]}"
    pacman -S --noconfirm "${needed[@]}" || {
        ui_fail "pacman install failed"
        exit 1
    }
    ui_ok "deps installed"
fi

if [[ -e "$DEST" ]]; then
    ui_fail "$DEST already exists — run ./uninstall first, or remove it manually"
    exit 1
fi

# The screenshot has to run as the invoking user (Wayland compositors
# refuse screenshot requests from root — and on KDE Wayland the only
# tool that can actually capture the composited screen is spectacle,
# which needs the user's session DBus / WAYLAND_DISPLAY / XDG_RUNTIME_DIR.
# Resolve those once so the per-mode loop just calls a helper.
if [[ -z "${SUDO_USER:-}" ]]; then
    ui_fail "couldn't determine the invoking user (no SUDO_USER)"
    exit 1
fi
USER_UID=$(id -u "$SUDO_USER")
USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)

# Helper: take a Wayland screenshot of plymouth's window AS the
# invoking user. --activewindow captures only the focused window
# (plymouth maps a fullscreen X11 window that takes focus, so this
# gets just plymouth even on multi-monitor setups). --fullscreen
# would grab ALL outputs and show your secondary desktop alongside.
# Env reconstruction is needed because sudo strips session vars.
screenshot_as_user() {
    local out="$1"
    runuser -u "$SUDO_USER" -- env \
        HOME="$USER_HOME" \
        XDG_RUNTIME_DIR="/run/user/$USER_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_UID/bus" \
        WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
        DISPLAY=":0" \
        spectacle --background --nonotify --activewindow --output "$out"
}

# ── stage theme + register cleanup that chowns the output back ─────────

cleanup() {
    set +u
    plymouth --quit >/dev/null 2>&1
    [[ -d "$DEST" ]] && rm -rf "$DEST"
    # We're root, the output dir was created by us → chown back to
    # whoever invoked sudo so they can `xdg-open` / `cat` the files
    # without another sudo.
    if [[ -d "$OUT" && -n "${SUDO_USER:-}" ]]; then
        chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$OUT" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

ui_step "copying theme into /usr/share/plymouth/themes/"
cp -r "$SRC" "$DEST"

# ── render boot + shutdown ──────────────────────────────────────────────

mkdir -p "$OUT"
rm -f "$OUT"/*.png "$OUT"/*.log "$OUT"/*.err

# Chown OUT to the invoking user UPFRONT so spectacle (running as
# that user) can write the PNGs. The trap cleanup chowns it again at
# the end (catches plymouthd logs written as root mid-run).
chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$OUT" 2>/dev/null

for MODE in boot shutdown; do
    ui_step "rendering mode=$MODE (your screen will flash briefly)"

    plymouth --quit >/dev/null 2>&1
    sleep 0.3

    plymouthd \
        --no-daemon \
        --debug \
        --mode="$MODE" \
        --kernel-command-line="splash plymouth.theme=MacTahoeLiquidKde" \
        --debug-file="$OUT/plymouthd-$MODE.log" &
    PD_PID=$!
    sleep 1

    plymouth show-splash
    sleep 2

    # Plymouth's window doesn't always retain focus by the time we
    # screenshot — especially on shutdown mode, where VSCode / other
    # apps reclaim focus. Force-activate plymouth's X window so
    # spectacle --activewindow grabs the right thing.
    WID="$(xwininfo -tree -root 2>/dev/null \
            | awk '/plymouthd/ {print $1; exit}')"
    if [[ -n "$WID" ]]; then
        ui_info "plymouthd X window: $WID — forcing focus"
        runuser -u "$SUDO_USER" -- env DISPLAY=":0" \
            xdotool windowactivate "$WID" 2>/dev/null
        sleep 1
    fi

    # Hold a bit more so plymouth's GTK draw loop settles after focus.
    sleep 3

    SHOT="$OUT/plymouth-$MODE-splash.png"

    # Wayland security: X11 tools (scrot, xwd, import) under XWayland
    # only see XWayland's internal framebuffer, NOT the composited
    # display — so they capture black even when plymouth is visibly
    # on screen. spectacle talks to KWin's org.kde.KWin.ScreenShot2
    # DBus interface, which IS the compositor.
    if screenshot_as_user "$SHOT" 2>"$OUT/spectacle-$MODE.err"; then
        ui_ok "$MODE → $(basename "$SHOT")"
    else
        ui_fail "spectacle failed for $MODE (see spectacle-$MODE.err)"
    fi

    plymouth --quit >/dev/null 2>&1
    sleep 0.3
    kill "$PD_PID" 2>/dev/null
    wait "$PD_PID" 2>/dev/null
done

# ── summary ─────────────────────────────────────────────────────────────

ui_section "Captured frames"
shopt -s nullglob
for f in "$OUT"/*.png; do
    size=$(stat -c '%s' "$f" 2>/dev/null || echo "?")
    ui_info "$(basename "$f") (${size} bytes)"
done
shopt -u nullglob
echo
ui_info "Plymouth daemon debug logs: $OUT/plymouthd-*.log"
ui_info "Open frames with:  xdg-open $OUT/plymouth-boot-splash.png"
