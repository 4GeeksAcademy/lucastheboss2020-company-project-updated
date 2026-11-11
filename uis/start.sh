#!/usr/bin/env bash
set -Eeuo pipefail

export CHOKIDAR_USEPOLLING=true
export WATCHPACK_POLLING=true

cd /app/uis/website
npm run dev -- --hostname 0.0.0.0 --port 3000 &
website_pid=$!

cd /app/uis/backoffice
npm run dev -- --hostname 0.0.0.0 --port 3001 &
backoffice_pid=$!

stop_apps() {
	kill "$website_pid" "$backoffice_pid" 2>/dev/null || true
	wait "$website_pid" "$backoffice_pid" 2>/dev/null || true
}

trap stop_apps INT TERM
set +e
wait -n "$website_pid" "$backoffice_pid"
status=$?
set -e
stop_apps
exit "$status"