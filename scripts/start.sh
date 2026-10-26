#!/usr/bin/env bash
# Build the image and run the app container on http://localhost:8000.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="pm-app"
CONTAINER="pm-app"

docker build -t "$IMAGE" "$ROOT"

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null
fi

ENV_ARGS=()
if [ -f "$ROOT/.env" ]; then
  ENV_ARGS=(--env-file "$ROOT/.env")
fi

docker run -d --name "$CONTAINER" -p 8000:8000 ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} "$IMAGE" >/dev/null
echo "Running at http://localhost:8000"
