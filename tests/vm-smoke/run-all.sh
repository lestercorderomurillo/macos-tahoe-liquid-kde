#!/bin/bash
# Run every checked-in VM smoke entrypoint. Scripts that exit 2 are
# treated as explicit skips with a human-readable reason.

set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
scripts=(
    run-fedora.sh
    run-arch.sh
    run-opensuse.sh
    run-cachyos.sh
    run-manjaro.sh
    run-endeavouros.sh
    run-garuda.sh
    run-gentoo.sh
    run-nobara.sh
)

rc=0

for script in "${scripts[@]}"; do
    echo
    echo "=== ${script} ==="
    if bash "$script_dir/$script"; then
        continue
    fi
    status=$?
    if (( status == 2 )); then
        echo "→ skipped: ${script}"
        continue
    fi
    rc=$status
done

exit "$rc"
