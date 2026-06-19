#!/bin/bash
# Build a Docker image per supported distro and run the in-container
# preflight + pytest. Reports a YES / NO matrix at the end so we can
# flip the README table from "Working" to "YES" with evidence.
#
# Usage:  ./tests/containers/run_matrix.sh [distro ...]
#   With no args, runs the full matrix. Otherwise runs just the named
#   distros (arch, gentoo, fedora, opensuse).
#
# Each distro is independent — one failure does not abort the rest.
# Exit status is 0 only if every requested distro passes.

set -u
shopt -s nullglob

cd "$(dirname "$0")/../.."
REPO_ROOT="$(pwd)"

ALL_DISTROS=(
    cachyos arch manjaro endeavouros garuda
    gentoo
    fedora nobara
    opensuse
    # Arch with [kde-unstable] — the newest-KWin compile target. Keep it
    # last; it pulls the staging Plasma so the acrylic-glass effect is
    # compiled against the next ABI (6.7+) before any release distro has it.
    arch-kdeunstable
)
if [[ $# -eq 0 ]]; then
    DISTROS=("${ALL_DISTROS[@]}")
else
    DISTROS=("$@")
fi

# Color codes — only emit when stdout is a tty so CI logs stay clean.
if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
else
    BOLD=''; GREEN=''; RED=''; YELLOW=''; RESET=''
fi

declare -A RESULT

for distro in "${DISTROS[@]}"; do
    dockerfile="tests/containers/Dockerfile.${distro}"
    if [[ ! -f "$dockerfile" ]]; then
        echo "${RED}no Dockerfile for ${distro} at ${dockerfile}${RESET}"
        RESULT[$distro]="MISSING"
        continue
    fi

    echo
    echo "${BOLD}── building ${distro} ──${RESET}"
    if ! docker build -f "$dockerfile" -t "mttkde-test-${distro}:latest" "$REPO_ROOT"; then
        RESULT[$distro]="BUILD-FAIL"
        continue
    fi

    echo
    echo "${BOLD}── running ${distro} ──${RESET}"
    if docker run --rm "mttkde-test-${distro}:latest"; then
        RESULT[$distro]="PASS"
    else
        RESULT[$distro]="FAIL"
    fi
done

echo
echo "${BOLD}=== container matrix ===${RESET}"
overall_ok=0
for distro in "${DISTROS[@]}"; do
    status="${RESULT[$distro]:-?}"
    case "$status" in
        PASS)        marker="${GREEN}✓ PASS${RESET}" ;;
        FAIL)        marker="${RED}✗ FAIL${RESET}";       overall_ok=1 ;;
        BUILD-FAIL)  marker="${RED}✗ BUILD-FAIL${RESET}"; overall_ok=1 ;;
        MISSING)     marker="${YELLOW}? MISSING${RESET}"; overall_ok=1 ;;
        *)           marker="${YELLOW}? ${status}${RESET}"; overall_ok=1 ;;
    esac
    printf "  %-12s %b\n" "$distro" "$marker"
done

exit "$overall_ok"
