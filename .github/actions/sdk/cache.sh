#!/usr/bin/env bash
set -euo pipefail
recipe="tests/containers/Dockerfile.$DISTRO"
digest=$( { cat "$recipe"; if [[ "$DISTRO" == neon ]]; then cat tests/containers/neon/*; fi; } | sha256sum | cut -c1-16)
image="ghcr.io/${REPOSITORY,,}/sdk-$DISTRO:$(date -u +%G-%V)-$digest"
echo "image=$image" >> "$GITHUB_OUTPUT"
if ! docker pull "$image"; then
  docker build --pull --target sdk --label "org.opencontainers.image.source=https://github.com/$REPOSITORY" -f "$recipe" -t "$image" .
  if [[ "$EVENT" != pull_request ]]; then
    if ! docker push "$image" && ! docker push "$image"; then
      echo "::warning::SDK cache upload failed; running the complete tests with the locally built image."
    fi
  fi
fi
