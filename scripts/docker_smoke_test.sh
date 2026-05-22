#!/usr/bin/env bash
set -euo pipefail

docker compose build uav-control
docker compose run --rm uav-control \
  python -m app.main \
  --app-config config/app.docker.yaml \
  --no-yolo-udp \
  --run-seconds 1 \
  --send-commands false \
  --no-web-ui
