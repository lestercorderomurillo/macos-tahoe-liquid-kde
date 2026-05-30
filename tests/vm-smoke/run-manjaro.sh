#!/bin/bash
# Explicit skip until Manjaro publishes a reliable unattended cloud/VM
# image path instead of an installer-only ISO.

set -euo pipefail

echo "SKIP: Manjaro VM smoke needs a real unattended image path; use run-arch.sh for the closest Arch-family Plasma smoke in the meantime."
exit 2
