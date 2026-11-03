#!/usr/bin/env bash
set -euo pipefail

app_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/MangoFlux"
python_bin="${data_dir}/venv/bin/python"

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3 is required. On Omarchy/Arch: sudo pacman -S --needed python tk'
    exit 1
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    printf '%s\n' 'Python Tk support is required. On Omarchy/Arch: sudo pacman -S --needed python tk'
    exit 1
fi
if [ ! -x "$python_bin" ]; then
    mkdir -p "$data_dir"
    python3 -m venv "$data_dir/venv" || {
        printf '%s\n' 'Could not create the Python environment. Install Python venv support and try again.'
        exit 1
    }
fi
exec "$python_bin" "$app_dir/app.py"
