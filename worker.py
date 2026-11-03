"""Separate process for setup and inference; the UI can cancel it safely."""
import json
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'MangoFlux'
MODEL = 'black-forest-labs/flux-3-image-klein'
PROMPT = ('Erase all lettering and sound effects, then rebuild the artwork underneath: continue the surrounding line art, shading, screentones and colour so the panel reads as if the text was never there. Match the drawing style and palette of the surrounding artwork exactly. Do not add text, symbols, signatures or new objects. Return one image with the same framing and borders as the input.')


def event(message):
    print(message, flush=True)


def run(args):
    event('Running: ' + ' '.join(args))
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors='replace', bufsize=1) as process:
        for line in process.stdout:
            print(line, end='', flush=True)
        code = process.wait()
    if code:
        raise RuntimeError(f'The installation command failed (exit code {code}). See pip output above.')


def setup(backend):
    from sd_backend import setup_runtime
    setup_runtime(ROOT, backend, event)


def download():
    from sd_backend import download_model
    download_model(ROOT, os.environ.get('HF_TOKEN'), event)


def inference(source, destination, mode, backend):
    from sd_backend import clean
    clean(ROOT, source, destination, mode, backend, PROMPT, event)


if __name__ == '__main__':
    try:
        operation = sys.argv[1]
        if operation == 'setup': setup(sys.argv[2])
        elif operation == 'download': download()
        elif operation == 'clean': inference(*sys.argv[2:6])
        else: raise ValueError('Unknown operation')
    except Exception as exc:
        event(f'ERROR: {exc}')
        sys.exit(1)
