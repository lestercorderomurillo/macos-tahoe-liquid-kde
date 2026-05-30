#!/bin/bash
# Explicit skip until the installer has an immutable-image-aware path.

set -euo pipefail

echo "SKIP: Bazzite is rpm-ostree/immutable and the current installer writes into /usr/lib64/qt6, so a mutable Fedora proxy would be misleading."
exit 2
