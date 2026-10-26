#!/usr/bin/env bash
# Stop and remove the app container if it exists.
set -euo pipefail

CONTAINER="pm-app"

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped $CONTAINER"
else
  echo "$CONTAINER is not running"
fi
