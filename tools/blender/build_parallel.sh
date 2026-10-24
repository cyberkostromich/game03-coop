#!/usr/bin/env bash
# Build all units with N parallel Blender workers.  usage: build_parallel.sh [N] [ids...]
set -e
cd "$(dirname "$0")/../.."
N=${1:-2}; shift || true
IDS=("$@")
if [ ${#IDS[@]} -eq 0 ]; then
  mapfile -t IDS < <(blender -b --python-expr "import sys; sys.path.insert(0,'tools/blender'); from akit import units; print('IDS', ' '.join(units.REGISTRY))" 2>/dev/null | grep '^IDS' | cut -d' ' -f2- | tr ' ' '\n')
fi
mkdir -p build/logs
printf '%s\n' "${IDS[@]}" | xargs -P "$N" -I{} sh -c 'blender -b -P tools/blender/build_units.py -- {} > build/logs/{}.log 2>&1 && grep BUILT build/logs/{}.log || (echo FAILED {}; grep -A5 Traceback build/logs/{}.log)'
