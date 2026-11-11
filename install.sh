#!/bin/sh
set -eu
skill_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 2)' >/dev/null 2>&1; then
        exec "$candidate" "$skill_dir/scripts/install_runtime.py" "$@"
    fi
done
printf '%s\n' 'No executable Python 3.10+ found. Install Python, then run this installer again.' >&2
exit 2
