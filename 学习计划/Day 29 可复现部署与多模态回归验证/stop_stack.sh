#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/root/autodl-tmp}"
PID_FILE="$ROOT/day29-deployment/runtime/pids.tsv"

[[ -f "$PID_FILE" ]] || { echo "No Day29 PID file found; nothing to stop."; exit 0; }

mapfile -t lines < "$PID_FILE"
for (( index=${#lines[@]}-1; index>=0; index-- )); do
  IFS=$'\t' read -r name pid marker <<< "${lines[$index]}"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$name (pid=$pid) already stopped"
    continue
  fi
  cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
  if [[ "$cmdline" == *"$marker"* ]]; then
    kill -TERM "$pid"
    echo "Stopped $name (pid=$pid)"
  else
    echo "Refused to stop $name: pid=$pid no longer matches marker '$marker'" >&2
  fi
done
rm -f "$PID_FILE"
