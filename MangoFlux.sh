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
    printf '%s\n' 'Python Tk support is missing. Installing it with the system package manager...'
    if command -v pacman >/dev/null 2>&1; then
        install_tk=(pacman -S --needed --noconfirm tk)
    elif command -v apt-get >/dev/null 2>&1; then
        install_tk=(apt-get install -y python3-tk)
    elif command -v dnf >/dev/null 2>&1; then
        install_tk=(dnf install -y python3-tkinter)
    elif command -v zypper >/dev/null 2>&1; then
        install_tk=(zypper --non-interactive install python3-tk)
    else
        printf '%s\n' 'No supported package manager found. Install Tk support for python3, then run MangoFlux again.'
        exit 1
    fi
    if (( EUID != 0 )); then
        if ! command -v sudo >/dev/null 2>&1; then
            printf '%s\n' 'Installing Tk requires administrator access. Install Tk with your system package manager, then run MangoFlux again.'
            exit 1
        fi
        install_tk=(sudo "${install_tk[@]}")
    fi
    if ! "${install_tk[@]}"; then
        printf '%s\n' 'Tk installation failed. Resolve the package manager error above, then run MangoFlux again.'
        exit 1
    fi
    if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
        printf '%s\n' 'Tk was installed, but python3 still cannot import tkinter. Check that python3 matches your system Python installation.'
        exit 1
    fi
fi
if [ ! -x "$python_bin" ]; then
    mkdir -p "$data_dir"
    python3 -m venv "$data_dir/venv" || {
        printf '%s\n' 'Could not create the Python environment. Install Python venv support and try again.'
        exit 1
    }
fi
exec "$python_bin" "$app_dir/app.py"
