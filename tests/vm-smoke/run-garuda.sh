#!/bin/bash
# Explicit skip until Garuda has a real unattended VM path rather than
# a Calamares-first ISO workflow.

set -euo pipefail

echo "SKIP: Garuda VM smoke needs a real unattended image path; use run-arch.sh for the closest Arch-family Plasma smoke in the meantime."
exit 2
