#!/bin/bash
# Explicit skip until Nobara ships a real unattended VM path instead
# of installer ISOs.

set -euo pipefail

echo "SKIP: Nobara VM smoke needs either a published cloud image or a scripted Anaconda path; the current project only publishes installer ISOs."
exit 2
