#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target_dir="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/ai-usage@local"
command -v python3 >/dev/null
shell_version="$(gnome-shell --version)"
if [[ ! "$shell_version" =~ GNOME\ Shell\ 50[.\ ] ]]; then
    echo "This build targets GNOME 50. Detected: $shell_version"
    exit 1
fi
mkdir -p "$target_dir"
for name in metadata.json extension.js model.js collector.py quota.py README.md; do
    install -m 644 "$source_dir/$name" "$target_dir/$name"
done
echo 'Installed. Log out and log in, then run:'
echo 'gnome-extensions enable ai-usage@local'
