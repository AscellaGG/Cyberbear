#!/bin/sh
set -eu

APP_DIR=/opt/cyberbear
STATE_DIR=/var/lib/cyberbear

cd "$APP_DIR"
git fetch --quiet origin main

target_commit=$(git rev-parse origin/main)
last_deployed_commit=
if [ -f "$STATE_DIR/last-deployed-commit" ]; then
    last_deployed_commit=$(cat "$STATE_DIR/last-deployed-commit")
fi

if [ "$target_commit" = "$last_deployed_commit" ]; then
    exit 0
fi

# This is a dedicated deployment checkout, so discard no user work here.
git reset --hard "$target_commit"
docker compose up -d --build
printf '%s\n' "$target_commit" > "$STATE_DIR/last-deployed-commit"
