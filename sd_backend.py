"""Komatose-compatible Q8 inference and private stable-diffusion.cpp runtime."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile

RELEASE = 'master-1043-3be2378'
ASSETS = {
    'CPU': [('sd-master-3be2378-bin-win-cpu-x64.zip', '10ef877a334c97d014e3e23b4bf6c9077f6b78ff9da3bb157664d2103cb1ae0f')],
    'CUDA': [('sd-master-3be2378-bin-win-cuda12-x64.zip', '76da083337834ff9c383c5f80a49c8cf7485f8fa28d1fac1ef5ce057bbcb3e51'), ('cudart-sd-bin-win-cu12-x64.zip', 'fe20366827d357c00797eebb58244dddab7fd9a348d70090c3871004c320f38d')],
    'ROCm': [('sd-master-3be2378-bin-win-rocm-10.1.0-x64.zip', 'df5ce14e778784ab9f5302aab72bda49c3e4b512f15fea0ad5f32c616e5c5015')],
    'Vulkan': [('sd-master-3be2378-bin-win-vulkan-x64.zip', 'a5e1fa679561a3bb99b114a8f4a41e67239da29173ff725391ecfa5772e869ee')],
}
LINUX_ASSETS = {
    'CPU': [('sd-master-3be2378-bin-Linux-Ubuntu-24.04-x86_64.zip', '01e1c773c1bc2a6276952f6dbd13294e58b7255c659b4a770086934c4e8fad3a')],
    'Vulkan': [('sd-master-3be2378-bin-Linux-Ubuntu-24.04-x86_64-vulkan.zip', '7608901016fb4a348bc5b75c46fc971085dadadf44e6f30daa97301844b1ce2e')],
    'ROCm': [('sd-master-3be2378-bin-Linux-Ubuntu-24.04-x86_64-rocm-10.1.0.zip', '0058c3547163d455c478ab593653908bfaadaf2d48e4224ad9669e9509b1c67d')],
}
FILES = [
    ('leejet/flux-3-image-klein-GGUF', '1c2ad2f9b9247ccca6506a23bdb033fdb0873321', 'flux3-image-klein-Q8_0.gguf', 6151716032, '8b71ffd749bcacbd50cc0acca4f2d31a044c94412743e1e780db99bf13f89752'),
    ('Qwen/Qwen3-VL-4B-Instruct-GGUF', '1cd86afb9a95c410a6038ab3b40d8b578c892266', 'Qwen3VL-4B-Instruct-Q8_0.gguf', 4280406144, '054721f478bc5fa6beffb7f38eae575d45298f88cbb8d2f83ef675a727863eb1'),
    ('Comfy-Org/Flux-2-Klein-4B', '5b3abca5c0dc1ecd4eaf3340868d09063fc1c965', 'split_files/vae/flux2-vae.safetensors', 336211292, '868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3'),
]


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def setup_runtime(root, backend, event):
    import shutil
    import sys
    from worker import run
    run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', 'huggingface_hub>=1.0,<2', 'Pillow>=10,<13'])
    dest = root / 'runtime-gguf' / backend
    dest.mkdir(parents=True, exist_ok=True)
    assets = LINUX_ASSETS if sys.platform.startswith('linux') else ASSETS
    if backend not in assets:
        raise RuntimeError('No packaged Linux CUDA runtime is available. Select Vulkan on Linux.')
    if sys.platform.startswith('linux'):
        import platform
        if platform.machine().lower() not in ('x86_64', 'amd64'):
            raise RuntimeError('The bundled Linux runtime requires an x86-64 system.')
    for name, expected in assets[backend]:
        archive = root / name
        event(f'Downloading {name}...')
        try:
            url = f'https://github.com/leejet/stable-diffusion.cpp/releases/download/{RELEASE}/{name}'
            with urllib.request.urlopen(url, timeout=60) as response, archive.open('wb') as out:
                while True:
                    data = response.read(1024 * 1024)
                    if not data: break
                    out.write(data)
            event(f'Verifying {name}...')
            if digest(archive) != expected: raise RuntimeError(f'Checksum failed for {name}. Retry the download.')
            with zipfile.ZipFile(archive) as z:
                for info in z.infolist():
                    target = (dest / info.filename).resolve()
                    if not target.is_relative_to(dest.resolve()): raise RuntimeError('Runtime archive contains an unsafe path.')
                    z.extract(info, dest)
        finally:
            archive.unlink(missing_ok=True)
    executable = 'sd-server.exe' if os.name == 'nt' else 'sd-server'
    matches = list(dest.rglob(executable))
    if len(matches) != 1: raise RuntimeError(f'The runtime archive did not contain exactly one {executable}.')
    server = matches[0]
    if os.name != 'nt':
        server.chmod(server.stat().st_mode | 0o111)
        env = server_env(server)
        try:
            check = subprocess.run(['ldd', str(server)], capture_output=True, text=True, timeout=15, env=env)
            if check.returncode or 'not found' in check.stdout:
                raise RuntimeError('Linux runtime dependencies are missing. The prebuilt runtime targets Ubuntu 24.04; on Arch/Omarchy try Vulkan or install the required libraries.\n' + check.stdout[-2500:])
        except FileNotFoundError:
            event('ldd unavailable; runtime dependencies will be checked on startup.')
    for dll in dest.rglob('*.dll'):
        target = server.parent / dll.name
        if dll != target and not target.exists(): shutil.copy2(dll, target)
    (root / 'runtime-gguf.json').write_text(json.dumps({'backend': backend, 'server': str(server)}), encoding='utf-8')
    event(f'{backend} Q8 runtime installed successfully.')


def download_model(root, token, event):
    from huggingface_hub import hf_hub_download
    dest = root / 'model-gguf'
    dest.mkdir(parents=True, exist_ok=True)
    for repo, revision, filename, size, sha in FILES:
        path = dest / filename
        if path.is_file() and path.stat().st_size == size and digest(path) == sha:
            event(f'Already verified {Path(filename).name}.')
            continue
        event(f'Downloading {Path(filename).name} ({size / 1e9:.2f} GB)...')
        hf_hub_download(repo_id=repo, revision=revision, filename=filename, local_dir=dest, token=token or None)
        event(f'Verifying {Path(filename).name}...')
        if not path.is_file() or path.stat().st_size != size or digest(path) != sha:
            raise RuntimeError(f'Checksum failed for {filename}; remove the model and try again.')
    (root / 'model-ready-q8').write_text('ok', encoding='utf-8')
    event('Q8 model download complete.')


def multipart(fields, files):
    boundary = 'mangoflux-' + uuid.uuid4().hex
    chunks = []
    for key, value in fields.items():
        chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'.encode(), value.encode(), b'\r\n']
    for key, name, data in files:
        chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n'.encode(), data, b'\r\n']
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks), 'multipart/form-data; boundary=' + boundary


def edit_request(url, image, prompt, selection=None):
    from PIL import Image
    buf = io.BytesIO(); image.save(buf, format='PNG')
    mask = io.BytesIO(); (selection if selection is not None else Image.new('L', image.size, 255)).save(mask, format='PNG')
    args = {'sample_params': {'sample_steps': 16, 'sample_method': 'euler', 'guidance': {'txt_cfg': 1}}, 'strength': 1}
    fields = {'prompt': prompt + ' <sd_cpp_extra_args>' + json.dumps(args, separators=(',', ':')) + '</sd_cpp_extra_args>', 'size': f'{image.width}x{image.height}'}
    data, content_type = multipart(fields, [('image', 'crop.png', buf.getvalue()), ('mask', 'mask.png', mask.getvalue())])
    req = urllib.request.Request(url + '/v1/images/edits', data=data, headers={'Content-Type': content_type})
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp: body = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Image editor returned HTTP {exc.code}: {exc.read(1000).decode(errors="replace")}') from exc
    return Image.open(io.BytesIO(base64.b64decode(body['data'][0]['b64_json']))).convert('RGB')


def backend_args(backend, gpu_index=0, platform=None):
    platform = platform or sys.platform
    if backend == 'CPU':
        return ['--backend', 'cpu']
    if backend == 'Vulkan':
        # Integrated GPUs share system memory. Keeping another copy of all Q8
        # weights in RAM can leave no Vulkan workspace; stream them from disk.
        device = f'vulkan{gpu_index}'
        if platform.startswith('linux'):
            return ['--backend', device]
        return ['--backend', device, '--params-backend', 'disk', '--max-vram', f'{device}=4']
    if backend in ('CUDA', 'ROCm'):
        return ['--backend', f'{backend.lower()}{gpu_index}']
    raise ValueError(f'Unknown backend: {backend}')


def server_env(server):
    env = os.environ.copy()
    if os.name != 'nt':
        env['LD_LIBRARY_PATH'] = str(Path(server).parent) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    return env


def clean(root, source, destination, mode, backend, prompt, event, gpu_index=0):
    from PIL import Image, ImageOps
    from imaging import fit_size, merge_reconstruction
    config = json.loads((root / 'runtime-gguf.json').read_text(encoding='utf-8'))
    if config['backend'] != backend: raise RuntimeError('Install the selected runtime first.')
    model = root / 'model-gguf'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    args = [config['server'], '--diffusion-model', str(model / FILES[0][2]), '--llm', str(model / FILES[1][2]), '--vae', str(model / FILES[2][2]), '--listen-ip', '127.0.0.1', '--listen-port', str(port)]
    args += backend_args(backend, gpu_index)
    if backend == 'Vulkan':
        event(f'Using Vulkan device {gpu_index}. Check the runtime log for the GPU name.')
    event('Starting the Q8 image editor...')
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', bufsize=1, env=server_env(config['server']), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    def logs():
        for line in proc.stdout: event(line.rstrip())
    threading.Thread(target=logs, daemon=True).start()
    try:
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            if proc.poll() is not None: raise RuntimeError(f'Image editor exited with code {proc.returncode}; see its messages above.')
            try:
                with urllib.request.urlopen(url + '/v1/models', timeout=2) as resp:
                    if resp.status == 200: break
            except (OSError, urllib.error.URLError): pass
            time.sleep(1)
        else: raise RuntimeError('Image editor did not finish loading within 15 minutes.')
        image = ImageOps.exif_transpose(Image.open(source)).convert('RGB')
        size = image.size
        def edit(crop, selection=None):
            # The server expects dimensions on a 32-pixel grid.
            fitted = fit_size(crop.size)
            fitted = tuple(max(32, (v + 31) // 32 * 32) for v in fitted)
            ref = crop.resize(fitted, Image.Resampling.LANCZOS) if crop.size != fitted else crop
            if selection is not None and selection.size != fitted:
                selection = selection.resize(fitted, Image.Resampling.NEAREST)
            result = edit_request(url, ref, prompt, selection)
            return result.resize(crop.size, Image.Resampling.LANCZOS) if result.size != crop.size else result
        if mode == 'Tiled':
            result = image.copy()
            covered = Image.new('L', size, 0)
            full_page_mask = Image.new('L', size, 255)
            cores = [(x, y, min(x + 768, size[0]), min(y + 768, size[1]))
                     for y in range(0, size[1], 768) for x in range(0, size[0], 768)]
            for i, (x0, y0, x1, y1) in enumerate(cores):
                event(f'Cleaning tile {i+1} of {len(cores)}...')
                left, top = max(0, x0 - 128), max(0, y0 - 128)
                right, bottom = min(size[0], x1 + 128), min(size[1], y1 + 128)
                width = max(512, ((right - left + 31) // 32) * 32)
                height = max(512, ((bottom - top + 31) // 32) * 32)
                left = round(left + ((right - left) - width) / 2)
                top = round(top + ((bottom - top) - height) / 2)
                # Replicate edge pixels for context outside the page, as Komatose does.
                clipped = result.crop((max(0, left), max(0, top), min(size[0], left + width), min(size[1], top + height)))
                border = (max(0, -left), max(0, -top), max(0, left + width - size[0]), max(0, top + height - size[1]))
                crop = ImageOps.expand(clipped, border=border)
                if border[0]: crop.paste(clipped.crop((0, 0, 1, clipped.height)).resize((border[0], clipped.height)), (0, border[1]))
                if border[2]: crop.paste(clipped.crop((clipped.width-1, 0, clipped.width, clipped.height)).resize((border[2], clipped.height)), (border[0]+clipped.width, border[1]))
                if border[1]: crop.paste(crop.crop((0, border[1], width, border[1]+1)).resize((width, border[1])), (0, 0))
                if border[3]: crop.paste(crop.crop((0, border[1]+clipped.height-1, width, border[1]+clipped.height)).resize((width, border[3])), (0, border[1]+clipped.height))
                selection = full_page_mask.crop((left, top, left + width, top + height))
                generated = edit(crop, selection)
                visible = (max(0, left), max(0, top), min(size[0], left + width), min(size[1], top + height))
                local = (visible[0]-left, visible[1]-top, visible[2]-left, visible[3]-top)
                merge_reconstruction(result, covered, generated, visible, local, (x0, y0))
        else:
            event('Cleaning the page (16 Euler steps)...')
            result = edit(image)
        result.save(destination, format='PNG')
        event('Cleaning complete.')
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
