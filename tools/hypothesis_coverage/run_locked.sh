#!/usr/bin/env bash
set -u
root=$(git rev-parse --show-toplevel)
cd "$root" || exit 1
label=$1
shift
receipt="logs/hypothesis-coverage/$(date -u +%Y%m%dT%H%M%SZ)-$label"
mkdir -p "$receipt"
printf '%s\n' "$PWD" > "$receipt/cwd"
printf '%q ' "$@" > "$receipt/argv"
date -u +%FT%TZ > "$receipt/start"
(
 flock -w 10 9 || exit 75
 available=$(df -B1 --output=avail . | tail -1)
 test "$available" -ge 32212254720 || exit 76
 ulimit -v 2097152
 ulimit -t 120
 ulimit -f 204800
 /usr/bin/time -v -o "$receipt/time" "$@" > "$receipt/stdout" 2> "$receipt/stderr"
) 9>/home/jake/Projects/nanopore_basecaller/results/stock/host.lock
status=$?
printf '%s\n' "$status" > "$receipt/exit"
date -u +%FT%TZ > "$receipt/end"
printf '%s exit=%s\n' "$receipt" "$status"
cat "$receipt/stdout" "$receipt/stderr" 2>/dev/null
exit "$status"
