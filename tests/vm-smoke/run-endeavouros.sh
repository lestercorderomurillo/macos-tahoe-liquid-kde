#!/bin/bash
# Explicit skip until EndeavourOS has a real unattended VM path rather
# than an installer-first ISO flow.

set -euo pipefail

echo "SKIP: EndeavourOS VM smoke needs a real unattended image path; use run-arch.sh for the closest Arch-family Plasma smoke in the meantime."
exit 2
