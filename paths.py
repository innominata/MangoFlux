"""Application data paths shared by the UI and its worker."""
import os
from pathlib import Path


def data_root():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'MangoFlux'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'MangoFlux'
