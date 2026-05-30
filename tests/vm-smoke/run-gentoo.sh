#!/bin/bash
# Explicit skip until the Gentoo path has either a prebuilt Plasma
# image or a binpkg-driven first-boot flow that is practical for this
# smoke harness.

set -euo pipefail

echo "SKIP: Gentoo has an official cloud-init qcow2, but first-boot Plasma provisioning is still too heavy for this harness without a prebuilt Plasma/binpkg flow."
exit 2
