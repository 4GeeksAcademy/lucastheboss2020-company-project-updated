#!/bin/sh
set -eu

export CHOKIDAR_USEPOLLING=true
export WATCHPACK_POLLING=true

exec npm run dev -- --hostname 0.0.0.0 --port "${PORT:-3000}"