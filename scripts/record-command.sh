#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
label=${1:?usage: record-command.sh LABEL COMMAND [ARG ...]}
shift
[[ "$label" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo "Invalid label" >&2; exit 2; }
(( $# > 0 )) || { echo "Missing command" >&2; exit 2; }
run=$(mktemp -d "$root/logs/$(date -u +%Y%m%dT%H%M%SZ)-${label}-XXXXXX")
printf '%q ' "$@" > "$run/command.sh"
printf '\n' >> "$run/command.sh"
pwd > "$run/cwd.txt"
date -u +%FT%TZ > "$run/start.txt"
set +e
/usr/bin/time -v -o "$run/time.txt" -- "$@" > "$run/stdout" 2> "$run/stderr"
status=$?
set -e
printf '%s\n' "$status" > "$run/exit-status.txt"
date -u +%FT%TZ > "$run/end.txt"
printf '%s\n' "$run"
exit "$status"
