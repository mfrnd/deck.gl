#!/bin/bash
# Usage: run_edge.sh <version> <mode> <page> [extra query] [wait seconds]
# Opens tools/<page>?v=<version>&m=<mode><extra> in headless Windows Edge on the GPU (from WSL), waits
# for server.py to receive the result and stops only the Edge processes using the temporary profile.
# EDGE: path of msedge.exe; EDGE_PROFILE: Windows path of a throwaway profile folder.
HERE=$(cd "$(dirname "$0")" && pwd)
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
EDGE=${EDGE:-"/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"}
EDGE_PROFILE=${EDGE_PROFILE:-"$(/mnt/c/Windows/System32/cmd.exe /c 'echo %TEMP%' 2>/dev/null | tr -d '\r')\\globe-repro-edge"}
v=$1; mode=${2:-check}; page=${3:-page.html}; extra=${4:-}; wait_s=${5:-240}
rm -f "$HERE/out/result-$v.json"
(cd /mnt/c && timeout $((wait_s + 60)) "$EDGE" --headless --no-first-run --disable-extensions --user-data-dir="$EDGE_PROFILE" \
  --window-size=800,600 "http://localhost:8791/$page?v=$v&m=$mode$extra&d=$RANDOM" > /dev/null 2>&1) &
start=$(date +%s)
until [ -f "$HERE/out/result-$v.json" ] || [ $(( $(date +%s) - start )) -gt "$wait_s" ]; do sleep 2; done
echo "$v: result after $(( $(date +%s) - start )) s: $(ls "$HERE/out/result-$v.json" 2>/dev/null | wc -l)"
profile_name=$(basename "${EDGE_PROFILE//\\//}")
pids=$(timeout 30 $PS -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*$profile_name*' } | Select-Object -ExpandProperty ProcessId" 2>/dev/null | tr -d '\r' | grep -E '^[0-9]+$' | paste -sd, -)
[ -n "$pids" ] && timeout 30 $PS -NoProfile -Command "Stop-Process -Id $pids -ErrorAction SilentlyContinue" > /dev/null 2>&1
wait
