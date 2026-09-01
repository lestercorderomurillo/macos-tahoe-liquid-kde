#!/usr/bin/env bash
# Run Plymouth in debug mode inside an isolated nested X server. Standard
# Plymouth dev
# workflow per freedesktop.org/wiki/Software/Plymouth/Themes/:
#
#   1. copy theme into /usr/share/plymouth/themes/
#   2. plymouthd --no-daemon --debug --mode=X
#   3. plymouth show-splash
#   4. screenshot, plymouth --quit, remove the theme copy
#
# No Docker, VM, initramfs rebuild, desktop focus, or compositor screenshot.
# Xvfb supplies a private framebuffer whose pixels can be asserted directly.

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

needed=()
command -v plymouthd >/dev/null || needed+=(plymouth)
command -v magick    >/dev/null || needed+=(imagemagick)
command -v xwininfo  >/dev/null || needed+=(xorg-xwininfo)
command -v scrot     >/dev/null || needed+=(scrot)
command -v Xvfb      >/dev/null || needed+=(xorg-server-xvfb)
if [[ ${#needed[@]} -gt 0 ]]; then
    ui_step "installing missing packages: ${needed[*]}"
    pacman -S --noconfirm "${needed[@]}" || {
        ui_fail "pacman install failed"
        exit 1
    }
    ui_ok "deps installed"
fi

# The harness ALWAYS renders against the source tree
# (src/offline/plymouth/...), not whatever's currently installed —
# the whole point of `./test --vm` is to see what your .script
# changes look like BEFORE shipping a release.
#
# If the user already ran ./install, the system dir has the previous
# version. Move it aside, drop our source in, render, restore on
# cleanup. Standard transactional install pattern.
BACKUP="$DEST.mttkde-test-backup"
RESTORE_BACKUP=0
if [[ -d "$DEST" ]]; then
    if [[ -e "$BACKUP" ]]; then
        # Stale backup from a crashed previous run — kill it so the mv works.
        rm -rf "$BACKUP"
    fi
    mv "$DEST" "$BACKUP"
    RESTORE_BACKUP=1
    ui_info "moved existing $DEST aside (will restore on exit)"
fi

# Resolve the invoking account once so output can be returned with the right
# ownership. The Plymouth X11 test window itself is captured directly from the
# nested framebuffer and does not need compositor screenshot permission.
if [[ -z "${SUDO_USER:-}" ]]; then
    ui_fail "couldn't determine the invoking user (no SUDO_USER)"
    exit 1
fi
# Capture Plymouth's own X11 window, never the desktop or active application.
screenshot_plymouth_window() {
    local window_id="$1"
    local out="$2"
    scrot --overwrite --window "$window_id" "$out"
}

metric_at_least() {
    awk -v actual="$1" -v minimum="$2" \
        'BEGIN { exit !(actual + 0 >= minimum + 0) }'
}

metric_at_most() {
    awk -v actual="$1" -v maximum="$2" \
        'BEGIN { exit !(actual + 0 <= maximum + 0) }'
}

validate_capture() {
    local mode="$1"
    local shot="$2"
    local width height short_axis logo_size logo_x logo_y
    local bar_w bar_h bar_x bar_y frame_mean logo_mean bar_mean

    read -r width height < <(magick identify -format '%w %h' "$shot")
    if [[ -z "$width" || -z "$height" || "$width" -lt 640 || "$height" -lt 480 ]]; then
        ui_fail "$mode capture has invalid dimensions"
        return 1
    fi

    # A valid splash is almost entirely black. This immediately rejects the
    # launcher/Chrome screenshots the former harness accepted as passing.
    frame_mean=$(magick "$shot" -colorspace Gray -format '%[fx:mean]' info:)
    if ! metric_at_most "$frame_mean" 0.035; then
        ui_fail "$mode captured the desktop, not Plymouth (mean=$frame_mean)"
        return 1
    fi

    if (( width < height )); then short_axis=$width; else short_axis=$height; fi
    logo_size=$(( short_axis * 7 / 100 ))
    (( logo_size < 16 )) && logo_size=16
    logo_x=$(( width / 2 - logo_size / 2 ))
    logo_y=$(( height / 2 - logo_size / 2 ))
    logo_mean=$(magick "$shot" \
        -crop "${logo_size}x${logo_size}+${logo_x}+${logo_y}" +repage \
        -colorspace Gray -format '%[fx:mean]' info:)
    if ! metric_at_least "$logo_mean" 0.08; then
        ui_fail "$mode logo is missing or off-centre (centre mean=$logo_mean)"
        return 1
    fi

    bar_w=$(( width * 72 / 1000 ))
    bar_h=$(( bar_w * 2 / 100 ))
    (( bar_h < 4 )) && bar_h=4
    bar_x=$(( width / 2 - bar_w / 2 ))
    bar_y=$(( logo_y + logo_size + height * 35 / 1000 ))
    bar_mean=$(magick "$shot" \
        -crop "${bar_w}x${bar_h}+${bar_x}+${bar_y}" +repage \
        -colorspace Gray -format '%[fx:mean]' info:)

    if [[ "$mode" == "boot" ]]; then
        # The staged test hook drives 65% progress. A missing fill is far below
        # this threshold, so a logo-only boot frame cannot pass silently.
        if ! metric_at_least "$bar_mean" 0.45; then
            ui_fail "boot progress fill is missing (mean=$bar_mean)"
            return 1
        fi
    elif ! metric_at_most "$bar_mean" 0.04; then
        ui_fail "shutdown unexpectedly shows a progress bar (mean=$bar_mean)"
        return 1
    fi

    ui_ok "$mode pixels validated (frame=$frame_mean logo=$logo_mean bar=$bar_mean)"
}

# ── stage theme + register cleanup that chowns the output back ─────────

cleanup() {
    set +u
    plymouth --quit >/dev/null 2>&1
    if [[ -n "${XVFB_PID:-}" ]]; then
        kill "$XVFB_PID" >/dev/null 2>&1
        wait "$XVFB_PID" >/dev/null 2>&1
    fi
    # Remove our test copy.
    [[ -d "$DEST" ]] && rm -rf "$DEST"
    # Restore the user's real install if we moved one aside.
    if [[ "$RESTORE_BACKUP" == "1" && -d "$BACKUP" ]]; then
        mv "$BACKUP" "$DEST"
    fi
    # Chown output back to invoking user.
    if [[ -d "$OUT" && -n "${SUDO_USER:-}" ]]; then
        chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$OUT" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

mkdir -p "$OUT"
rm -f "$OUT"/*.png "$OUT"/*.log "$OUT"/*.err

# Pick a private display without clobbering a nested server the user may
# already have running. Xvfb's 1920x1080 framebuffer makes geometry exact and
# keeps every capture independent of the host's monitor layout or scale.
TEST_DISPLAY=""
for display_num in 97 98 99; do
    if [[ ! -e "/tmp/.X11-unix/X$display_num" ]]; then
        TEST_DISPLAY=":$display_num"
        break
    fi
done
if [[ -z "$TEST_DISPLAY" ]]; then
    ui_fail "no free nested X display (:97-:99)"
    exit 1
fi

ui_step "starting isolated 1920x1080 Xvfb on $TEST_DISPLAY"
Xvfb "$TEST_DISPLAY" -screen 0 1920x1080x24 -ac -nolisten tcp \
    >"$OUT/xvfb.log" 2>&1 &
XVFB_PID=$!
export DISPLAY="$TEST_DISPLAY"
unset XAUTHORITY
for _ in $(seq 1 50); do
    xwininfo -root >/dev/null 2>&1 && break
    sleep 0.1
done
if ! xwininfo -root >/dev/null 2>&1; then
    ui_fail "Xvfb did not become ready (see xvfb.log)"
    exit 1
fi
ui_ok "nested X framebuffer ready"

ui_step "copying theme source into /usr/share/plymouth/themes/"
cp -r "$SRC" "$DEST"

# Exercise a state a normal preview does not reach deterministically: a
# non-zero boot progress fill. This modifies only the temporary test copy and
# is removed by cleanup; the shipped OG script remains byte-for-byte intact.
printf '%s\n' \
    '' \
    '# MTTKDE render-harness hook (temporary staged copy only).' \
    'fun mttkde_harness_progress(duration, ignored)' \
    '{' \
    '  on_boot_progress(duration, 0.65);' \
    '}' \
    'if (show_progress)' \
    '{' \
    '  Plymouth.SetBootProgressFunction(mttkde_harness_progress);' \
    '  on_boot_progress(0, 0.65);' \
    '}' >> "$DEST/MacTahoeLiquidKde.script"

# ── render boot + shutdown ──────────────────────────────────────────────

FAILURES=0

# Chown OUT to the invoking user up front; the trap repeats this at the end to
# catch the root-owned Plymouth logs and window captures written mid-run.
chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$OUT" 2>/dev/null

for MODE in boot shutdown; do
    ui_step "rendering mode=$MODE in the nested framebuffer"

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

    sleep 2

    SHOT="$OUT/plymouth-$MODE-splash.png"
    xwininfo -tree -root >"$OUT/xwin-tree-$MODE.log" 2>&1
    WID="$(awk '$2 ~ /plymouthd/ {
              split($5, size, "x");
              if (size[1] + 0 >= 640) { print $1; exit }
            }' "$OUT/xwin-tree-$MODE.log")"

    if [[ -z "$WID" ]]; then
        ui_fail "could not locate Plymouth's X11 test window"
        FAILURES=$((FAILURES + 1))
    else
        WID_DEC=$((WID))
        ui_info "Plymouth X11 window: $WID ($WID_DEC)"
        xwininfo -id "$WID" >"$OUT/xwininfo-$MODE.log" 2>&1
    fi

    if [[ -n "$WID" ]] && screenshot_plymouth_window "$WID_DEC" "$SHOT" \
            2>"$OUT/capture-$MODE.err"; then
        ui_ok "$MODE → $(basename "$SHOT")"
        if ! validate_capture "$MODE" "$SHOT"; then
            FAILURES=$((FAILURES + 1))
        fi
    else
        ui_fail "X11 window capture failed for $MODE (see capture-$MODE.err)"
        FAILURES=$((FAILURES + 1))
    fi

    plymouth --quit >/dev/null 2>&1
    sleep 0.3
    kill "$PD_PID" 2>/dev/null
    wait "$PD_PID" 2>/dev/null

    if [[ ! -f "$OUT/plymouthd-$MODE.log" ]]; then
        ui_fail "$MODE Plymouth debug log was not written"
        FAILURES=$((FAILURES + 1))
    elif rg -qi 'syntax error|script[^:]*:.*(error|failed)' \
            "$OUT/plymouthd-$MODE.log"; then
        ui_fail "$MODE Plymouth log contains a script error"
        FAILURES=$((FAILURES + 1))
    fi
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

if (( FAILURES > 0 )); then
    ui_fail "$FAILURES Plymouth render validation(s) failed"
    exit 1
fi

ui_ok "all Plymouth render validations passed"
