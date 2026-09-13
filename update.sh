#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo 'Use a Git clone for updates. See README.'
    exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
    echo 'Local changes exist. Commit or stash them before updating.'
    exit 1
fi
git pull --ff-only
bash install.sh
