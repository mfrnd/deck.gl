#!/bin/bash
# Usage: run_sw.sh <version> <page with query> [wait seconds]
# Software rendering (SwiftShader) in Playwright's chrome-headless-shell. SYSLIBS: extra library folder
# for LD_LIBRARY_PATH when the shell lacks system libraries.
HERE=$(cd "$(dirname "$0")" && pwd)
HS=${HEADLESS_SHELL:-$(ls -d ~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell | head -1)}
v=$1; query=$2; wait_s=${3:-300}
rm -f "$HERE/out/result-$v.json"
LD_LIBRARY_PATH=${SYSLIBS:-} "$HS" --no-sandbox --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --window-size=800,600 \
  "http://127.0.0.1:8791/$query&v=$v&d=$RANDOM" > /dev/null 2>&1 &
pid=$!
start=$(date +%s)
until [ -f "$HERE/out/result-$v.json" ] || [ $(( $(date +%s) - start )) -gt "$wait_s" ]; do sleep 2; done
kill $pid 2>/dev/null; wait $pid 2>/dev/null
echo "$v ($query): result after $(( $(date +%s) - start )) s: $(ls "$HERE/out/result-$v.json" 2>/dev/null | wc -l)"
