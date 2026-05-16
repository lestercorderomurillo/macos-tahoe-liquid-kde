# Shared TTY UI helpers for the VM harness. Sourced by build-base.sh
# and run-test.sh — kept in one place so the visual style stays
# consistent (and so a tweak to the spinner / palette propagates to
# both runners without copy-paste drift).
#
# Detects TTY at source time. If stdout isn't a terminal (output is
# piped, captured, or redirected) we silently degrade to plain text
# with no in-place carriage returns, so logs still make sense.
#
# Exposed surface:
#   ui_section "Header"          ─── header block
#   ui_step    "doing the thing" → starts an in-place spinner line
#   ui_ok      "result text"     ✓ green tick + total time (if step active)
#   ui_fail    "result text"     ✗ red cross + total time
#   ui_info    "extra detail"    plain dimmed line
#   ui_wait_for LABEL TIMEOUT PROBE [TAIL_FILE [TAIL_GREP]]
#                                spinner + heartbeat + console-tail until
#                                PROBE succeeds or TIMEOUT fires
#
# All functions are safe to call from `set -e` scripts: they don't
# return errors except ui_wait_for, which returns 1 on timeout (so
# the caller can decide how to surface it).

# ── palette ─────────────────────────────────────────────────────────────

if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]] && [[ "${TERM:-}" != "dumb" ]]; then
    _UI_TTY=1
    _UI_RESET=$'\033[0m'
    _UI_DIM=$'\033[2m'
    _UI_BOLD=$'\033[1m'
    _UI_RED=$'\033[0;31m'
    _UI_GREEN=$'\033[0;32m'
    _UI_YELLOW=$'\033[0;33m'
    _UI_BLUE=$'\033[0;34m'
    _UI_CYAN=$'\033[0;36m'
    _UI_CLEAR_LINE=$'\r\033[K'
else
    _UI_TTY=0
    _UI_RESET=""
    _UI_DIM=""
    _UI_BOLD=""
    _UI_RED=""
    _UI_GREEN=""
    _UI_YELLOW=""
    _UI_BLUE=""
    _UI_CYAN=""
    _UI_CLEAR_LINE=$'\n'
fi

# Braille-dot spinner — same set kubectl / cargo / pnpm use. Renders
# nicely at any font size; ASCII fallback is `| / - \` if a user's
# terminal can't render U+2800 range, but that's rare in 2026.
_UI_SPIN_FRAMES=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)

# Tracks the in-progress step so ui_ok / ui_fail can compute elapsed.
_ui_step_start=0
_ui_step_label=""
_ui_step_active=0

# ── public ──────────────────────────────────────────────────────────────

ui_section() {
    printf "\n${_UI_BOLD}═══ %s ═══${_UI_RESET}\n\n" "$1"
}

ui_step() {
    _ui_step_label="$1"
    _ui_step_start=$(date +%s)
    _ui_step_active=1
    # Always print with a trailing newline. The old "hold the line open
    # so ui_ok can overwrite with a checkmark" trick looked nice for
    # cases where the script controlled the terminal between ui_step
    # and ui_ok, but it collided badly with interactive commands like
    # ``sudo`` (whose password prompt landed on the same line as the
    # spinner). ui_wait_for is the right place for live-spinner UI —
    # it owns its loop and rewrites its own line cleanly.
    printf "  ${_UI_BLUE}→${_UI_RESET}  %s\n" "$_ui_step_label"
}

ui_ok() {
    local detail="${1:-}"
    local elapsed=0
    if (( _ui_step_active )); then
        elapsed=$(( $(date +%s) - _ui_step_start ))
        _ui_step_active=0
    fi
    local time_part=""
    (( elapsed > 0 )) && time_part="${_UI_DIM} (${elapsed}s)${_UI_RESET}"
    local label="${detail:-$_ui_step_label}"
    printf "  ${_UI_GREEN}✓${_UI_RESET}  %s%s\n" "$label" "$time_part"
}

ui_fail() {
    local detail="${1:-}"
    local elapsed=0
    if (( _ui_step_active )); then
        elapsed=$(( $(date +%s) - _ui_step_start ))
        _ui_step_active=0
    fi
    local time_part=""
    (( elapsed > 0 )) && time_part="${_UI_DIM} (${elapsed}s)${_UI_RESET}"
    local label="${detail:-$_ui_step_label}"
    printf "  ${_UI_RED}✗${_UI_RESET}  %s%s\n" "$label" "$time_part" >&2
}

ui_info() {
    printf "  ${_UI_DIM}%s${_UI_RESET}\n" "$1"
}

# Y/n prompt matching the style of cli.py's confirm() — bold red
# message, "Continue? [Y/n]", default-yes, EOF or "" counts as yes,
# "n" aborts. Honors MTTKDE_NO_CONFIRM=1 for the SSH-driven VM
# harness path (same env var as the installer).
#
# Reads from /dev/tty when possible (so it works even when stdout is
# piped), falls back to read from stdin otherwise. Returns 0 on yes,
# 1 on no — caller decides what to do with the answer.
ui_confirm() {
    local msg="$1"
    printf "\n  ${_UI_BOLD}${_UI_RED}%s${_UI_RESET}\n\n" "$msg"
    if [[ "${MTTKDE_NO_CONFIRM:-}" == "1" ]]; then
        printf "  ${_UI_DIM}MTTKDE_NO_CONFIRM=1 — auto-accepting${_UI_RESET}\n\n"
        return 0
    fi
    local answer=""
    if [[ -r /dev/tty ]] && [[ -w /dev/tty ]]; then
        printf "  Continue? [Y/n] " > /dev/tty
        IFS= read -r answer < /dev/tty || true
    else
        printf "  Continue? [Y/n] "
        IFS= read -r answer || true
    fi
    answer="$(echo "$answer" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
    if [[ "$answer" == "n" ]] || [[ "$answer" == "no" ]]; then
        printf "  ${_UI_DIM}Aborted.${_UI_RESET}\n\n"
        return 1
    fi
    echo
    return 0
}

# Run a spinner + probe loop. Probe is a shell expression; PROBE
# succeeds when it exits 0. Optional TAIL_FILE + TAIL_GREP let us
# surface the latest interesting line from the guest's console log
# next to the spinner so the user sees what the VM is actually doing.
ui_wait_for() {
    local label="$1" timeout="$2" probe="$3"
    local tail_file="${4:-}" tail_grep="${5:-}"

    _ui_step_label="$label"
    _ui_step_start=$(date +%s)
    _ui_step_active=1

    local start; start=$(date +%s)
    local elapsed=0
    local frame_idx=0
    local last_tail=""
    local probe_pid=""
    local probe_rc_file
    probe_rc_file="$(mktemp)"

    # We background the probe so the spinner can keep rendering at
    # 8 fps in the foreground while the probe (e.g. ssh with a 5-second
    # ConnectTimeout) blocks. The previous version inlined ``eval
    # "$probe"`` directly, so the spinner froze for the entire probe
    # duration — making a 180s wait look like ~36 spinner updates and
    # giving the false impression that the script was hung.
    _ui_fire_probe() {
        : > "$probe_rc_file"
        ( eval "$probe" >/dev/null 2>&1; printf '%d' "$?" > "$probe_rc_file" ) &
        probe_pid=$!
    }

    _ui_reap_probe() {
        if [[ -n "$probe_pid" ]]; then
            if kill -0 "$probe_pid" 2>/dev/null; then
                kill "$probe_pid" 2>/dev/null || true
            fi
            wait "$probe_pid" 2>/dev/null || true
            probe_pid=""
        fi
    }

    _ui_fire_probe

    while true; do
        elapsed=$(( $(date +%s) - start ))

        # If the backgrounded probe wrote its exit code, check it.
        # The rc_file is empty until the subshell's printf completes,
        # so an empty file = still running.
        if [[ -s "$probe_rc_file" ]]; then
            local rc
            rc="$(cat "$probe_rc_file" 2>/dev/null || echo 1)"
            wait "$probe_pid" 2>/dev/null || true
            probe_pid=""
            if [[ "$rc" == "0" ]]; then
                rm -f "$probe_rc_file"
                ui_ok "$label"
                return 0
            fi
            # Probe failed — fire the next one in the background and
            # keep the spinner rolling.
            _ui_fire_probe
        fi

        if (( elapsed >= timeout )); then
            _ui_reap_probe
            rm -f "$probe_rc_file"
            ui_fail "$label timed out after ${elapsed}s"
            if [[ -n "$tail_file" ]] && [[ -f "$tail_file" ]]; then
                echo "      ${_UI_DIM}last 20 lines of guest console:${_UI_RESET}" >&2
                tail -n 20 "$tail_file" 2>/dev/null | sed 's/^/      /' >&2
            fi
            return 1
        fi

        if (( _UI_TTY )); then
            # Render the spinner line at ~8 fps. The probe runs in
            # parallel; we don't block here on it.
            local frame="${_UI_SPIN_FRAMES[$((frame_idx % 10))]}"
            local tail_hint=""
            if [[ -n "$tail_file" ]] && [[ -f "$tail_file" ]]; then
                local fresh
                fresh="$(grep -E "${tail_grep:-.}" "$tail_file" 2>/dev/null \
                    | tail -n 1 | tr -d '\r' || true)"
                if [[ -n "$fresh" ]]; then
                    # Strip ANSI, kernel timestamp prefix [    8.123456],
                    # and cloud-init[NNN]: PID tag for a cleaner tail.
                    last_tail="$(echo "$fresh" \
                        | sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g; s/^\[[[:space:]]*[0-9.]+\][[:space:]]+//; s/cloud-init\[[0-9]+\]:[[:space:]]+//' \
                        | cut -c1-70)"
                fi
            fi
            [[ -n "$last_tail" ]] && tail_hint=" ${_UI_DIM}— ${last_tail}${_UI_RESET}"
            printf "${_UI_CLEAR_LINE}  ${_UI_BLUE}%s${_UI_RESET}  %s ${_UI_DIM}(%ds)${_UI_RESET}%s" \
                "$frame" "$label" "$elapsed" "$tail_hint"
            frame_idx=$((frame_idx + 1))
            sleep 0.12
        else
            # Non-TTY fallback: heartbeat once every 10s, plain text.
            if (( elapsed % 10 == 0 )); then
                printf "  … %s (%ds / %ds)\n" "$label" "$elapsed" "$timeout"
            fi
            sleep 1
        fi
    done
}
