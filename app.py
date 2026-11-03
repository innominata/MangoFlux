"""MangoFlux: small local Windows interface for FLUX 3 page cleaning."""
import json
import os
import queue
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import webbrowser
import token_store
from paths import data_root

ROOT = data_root()
HERE = Path(__file__).resolve().parent
MODEL_URL = 'https://huggingface.co/black-forest-labs/flux-3-image-klein'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('MangoFlux')
        if sys.platform.startswith('linux'):
            # Tk uses X11/XWayland on Linux. Give its windows an explicit X11
            # pointer instead of relying on a compositor-provided default.
            try:
                self.configure(cursor='left_ptr')
            except tk.TclError:
                self.configure(cursor='arrow')
            cursor = self.cget('cursor')
            # X11 file choosers, message boxes, and combobox menus are separate
            # toplevels. Give those classes the same pointer as the main window.
            for dialog_class in ('Dialog', 'TkFDialog', 'TkMotifFDialog', 'TkChooseDir', 'ComboboxPopdown'):
                self.option_add(f'*{dialog_class}.cursor', cursor, 'userDefault')
        self.geometry('1000x760')
        self.minsize(760, 600)
        self.proc = None
        self.events = queue.Queue()
        self.source = None
        self.result = ROOT / 'last-result.png'
        self.photos = []
        self.operation = None
        self.warned_keyring = False
        self.protocol('WM_DELETE_WINDOW', self.close)
        ROOT.mkdir(parents=True, exist_ok=True)
        self.build()
        self.refresh()
        self.after(100, self.poll)

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        setup = ttk.LabelFrame(self, text='1. Setup', padding=10)
        setup.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 5))
        setup.columnconfigure(5, weight=1)
        ttk.Label(setup, text='Hardware:').grid(row=0, column=0, sticky='w')
        self.backend = tk.StringVar(value=self.detect_backend())
        ttk.Combobox(setup, textvariable=self.backend, values=['CPU', 'CUDA', 'ROCm', 'Vulkan'], state='readonly', width=10).grid(row=0, column=1, padx=5)
        ttk.Button(setup, text='Install runtime', command=self.install).grid(row=0, column=2, padx=5)
        ttk.Button(setup, text='Open model license', command=lambda: webbrowser.open(MODEL_URL)).grid(row=0, column=3, padx=5)
        ttk.Label(setup, text='HF token:').grid(row=1, column=0, pady=6)
        self.token = ttk.Entry(setup, show='*', width=28)
        self.token.grid(row=1, column=1, columnspan=2, sticky='w', padx=5)
        try:
            self.token.insert(0, token_store.load(ROOT / 'hf-token.bin'))
        except (OSError, UnicodeError) as exc:
            self.after_idle(lambda error=str(exc): messagebox.showerror('Token unavailable', f'The saved token could not be read. Enter it again.\n\n{error}'))
        self.token.bind('<FocusOut>', self.save_token)
        ttk.Button(setup, text='Download model', command=self.download).grid(row=1, column=3, padx=5)
        ttk.Button(setup, text='Remove model', command=self.remove_model).grid(row=1, column=4, padx=5)
        ttk.Button(setup, text='Forget token', command=self.forget_token).grid(row=1, column=5, padx=5, sticky='w')
        self.setup_status = ttk.Label(setup, text='', wraplength=920)
        self.setup_status.grid(row=2, column=0, columnspan=6, sticky='w')
        ttk.Label(setup, text='Accept the model license first. CPU and integrated GPUs can be slow. Vulkan works with compatible Intel, AMD, and NVIDIA GPUs.', wraplength=920).grid(row=3, column=0, columnspan=6, sticky='w', pady=(4, 0))
        ttk.Label(setup, text='GPU index:').grid(row=4, column=0, sticky='w', pady=(5, 0))
        self.gpu_index = tk.StringVar(value='0')
        ttk.Spinbox(setup, from_=0, to=31, textvariable=self.gpu_index, width=5).grid(row=4, column=1, sticky='w', padx=5, pady=(5, 0))
        ttk.Button(setup, text='List devices', command=self.list_devices).grid(row=4, column=2, sticky='w', pady=(5, 0))
        ttk.Label(setup, text='Select one GPU; see activity for device names.').grid(row=4, column=3, columnspan=3, sticky='w', pady=(5, 0))

        bar = ttk.LabelFrame(self, text='2. Clean a page', padding=10)
        bar.grid(row=1, column=0, sticky='ew', padx=10, pady=5)
        ttk.Button(bar, text='Open page', command=self.open_image).pack(side='left')
        self.mode = tk.StringVar(value='Auto')
        ttk.Combobox(bar, textvariable=self.mode, values=['Auto', 'Whole page', 'Tiled'], state='readonly', width=12).pack(side='left', padx=8)
        ttk.Button(bar, text='Clean', command=self.clean).pack(side='left', padx=4)
        ttk.Button(bar, text='Cancel', command=self.cancel).pack(side='left', padx=4)
        ttk.Button(bar, text='Save cleaned PNG', command=self.save).pack(side='left', padx=4)
        self.page_label = ttk.Label(bar, text='No page selected')
        self.page_label.pack(side='left', padx=10)

        previews = ttk.Frame(self)
        previews.grid(row=2, column=0, sticky='nsew', padx=10, pady=5)
        previews.columnconfigure((0, 1), weight=1, uniform='preview')
        previews.rowconfigure(1, weight=1)
        ttk.Label(previews, text='Original').grid(row=0, column=0)
        ttk.Label(previews, text='Cleaned').grid(row=0, column=1)
        self.original_view = ttk.Label(previews, anchor='center')
        self.result_view = ttk.Label(previews, anchor='center')
        self.original_view.grid(row=1, column=0, sticky='nsew')
        self.result_view.grid(row=1, column=1, sticky='nsew')
        previews.bind('<Configure>', lambda event: self.after_idle(self.show_previews))
        bottom = ttk.LabelFrame(self, text='Activity', padding=5)
        bottom.grid(row=3, column=0, sticky='ew', padx=10, pady=(5, 10))
        self.log = tk.Text(bottom, height=7, wrap='word', state='disabled')
        self.log.pack(fill='x')
        self.progress = ttk.Progressbar(bottom, mode='indeterminate')
        self.progress.pack(fill='x', pady=(4, 0))
        self.progress_label = ttk.Label(bottom, text='Ready')
        self.progress_label.pack(anchor='w')

    def detect_backend(self):
        if sys.platform.startswith('linux'):
            vendors = set()
            for device in Path('/sys/class/drm').glob('card[0-9]*/device/vendor'):
                try:
                    vendors.add(device.read_text().strip().lower())
                except OSError: pass
            if '0x1002' in vendors: return 'ROCm'
            if '0x8086' in vendors: return 'Vulkan'
            return 'CPU'
        try:
            result = subprocess.run(['nvidia-smi', '-L'], capture_output=True, timeout=4, creationflags=NO_WINDOW)
            if result.returncode == 0: return 'CUDA'
        except (OSError, subprocess.SubprocessError): pass
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'], capture_output=True, text=True, timeout=6, creationflags=NO_WINDOW)
            if 'AMD' in r.stdout or 'Radeon' in r.stdout: return 'ROCm'
            if 'Intel' in r.stdout: return 'Vulkan'
        except (OSError, subprocess.SubprocessError): pass
        return 'CPU'

    def append(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text.rstrip() + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def refresh(self):
        try: installed = json.loads((ROOT / 'runtime-gguf.json').read_text(encoding='utf-8'))['backend']
        except (OSError, ValueError, KeyError): installed = 'not installed'
        self.installed = installed
        model = 'Q8 downloaded' if (ROOT / 'model-ready-q8').exists() else 'Q8 not downloaded'
        free = shutil.disk_usage(ROOT).free / 1024**3
        self.setup_status.config(text=f'Runtime: {installed}  |  Model: {model}  |  Free disk: {free:.1f} GB. Allow at least 40 GB for setup and model; actual usage varies.')

    def launch(self, args, token=None, success=None):
        if self.proc:
            messagebox.showinfo('Busy', 'Wait for the current operation or cancel it first.')
            return
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        env['HF_HOME'] = str(ROOT / 'hf-cache')
        if token: env['HF_TOKEN'] = token
        else: env.pop('HF_TOKEN', None)
        try:
            # pythonw.exe has no console streams; use its console sibling for workers
            # so pip and native libraries can reliably report diagnostics.
            python = str(Path(sys.executable).with_name('python.exe')) if os.name == 'nt' else sys.executable
            self.proc = subprocess.Popen([python, '-u', str(HERE / 'worker.py'), *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', env=env, creationflags=NO_WINDOW, start_new_session=(os.name != 'nt'))
        except OSError as exc:
            messagebox.showerror('Could not start', str(exc)); return
        proc = self.proc
        self.operation = args[0]
        self.progress.start(12)
        def read():
            for line in proc.stdout: self.events.put(('line', line))
            self.events.put(('done', (proc.wait(), success)))
        threading.Thread(target=read, daemon=True).start()

    def install(self):
        if self.proc: messagebox.showinfo('Busy', 'Finish or cancel the current operation first.'); return
        backend = self.backend.get()
        if backend not in ('CPU', 'CUDA', 'ROCm', 'Vulkan'): return
        if not messagebox.askyesno('Install runtime', f'Install the {backend} runtime? A compatible graphics driver is required for GPU acceleration.'): return
        (ROOT / 'runtime-gguf.json').unlink(missing_ok=True)
        self.refresh()
        self.launch(['setup', backend])

    def download(self):
        if self.proc: messagebox.showinfo('Busy', 'Finish or cancel the current operation first.'); return
        if self.installed == 'not installed':
            messagebox.showinfo('Setup', 'Install a runtime first.'); return
        token = self.token.get().strip()
        if not self.save_token(): return
        self.launch(['download'], token=token)

    def list_devices(self):
        if self.installed == 'not installed':
            messagebox.showinfo('Setup', 'Install a runtime first.'); return
        self.launch(['devices'])

    def save_token(self, event=None):
        token = self.token.get().strip()
        try:
            if token:
                token_store.save(ROOT / 'hf-token.bin', token)
            else:
                token_store.forget(ROOT / 'hf-token.bin')
        except OSError as exc:
            if os.name != 'nt':
                if not self.warned_keyring:
                    messagebox.showwarning('Token kept for this session', f'The desktop keyring is unavailable; the token will not be saved.\n\n{exc}')
                    self.warned_keyring = True
                return True
            messagebox.showerror('Could not save token', f'Windows could not protect or save the token.\n\n{exc}'); return False
        return True

    def forget_token(self):
        try:
            token_store.forget(ROOT / 'hf-token.bin')
            self.token.delete(0, 'end')
        except OSError as exc:
            messagebox.showerror('Could not forget token', str(exc))

    def open_image(self):
        if self.proc: messagebox.showinfo('Busy', 'Finish or cancel the current operation first.'); return
        path = filedialog.askopenfilename(filetypes=[('Images', '*.png *.jpg *.jpeg *.webp')])
        if not path: return
        try:
            from PIL import Image, ImageOps
            with Image.open(path) as im: ImageOps.exif_transpose(im).load()
        except Exception as exc:
            messagebox.showerror('Cannot open image', f'Install the runtime first, and select a valid image.\n\n{exc}'); return
        self.source = Path(path)
        self.result.unlink(missing_ok=True)
        self.page_label.config(text=self.source.name)
        self.show_previews()

    def show_previews(self):
        try:
            from PIL import Image, ImageTk, ImageOps
            self.photos = []
            for path, label in ((self.source, self.original_view), (self.result if self.result.exists() else None, self.result_view)):
                if not path:
                    label.configure(image='', text=''); continue
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im).convert('RGB')
                    im.thumbnail((max(100, label.winfo_width()-10), max(100, label.winfo_height()-10)))
                    photo = ImageTk.PhotoImage(im)
                self.photos.append(photo)
                label.configure(image=photo)
        except Exception: pass

    def clean(self):
        if self.proc: messagebox.showinfo('Busy', 'Finish or cancel the current operation first.'); return
        if not self.source: messagebox.showinfo('Open a page', 'Choose a page first.'); return
        if self.installed != self.backend.get(): messagebox.showinfo('Runtime', 'Install the selected runtime first.'); return
        if not (ROOT / 'model-ready-q8').exists(): messagebox.showinfo('Model', 'Download the Q8 model first.'); return
        from PIL import Image, ImageOps
        with Image.open(self.source) as im:
            im = ImageOps.exif_transpose(im)
            mode = self.mode.get()
            if mode == 'Auto': mode = 'Tiled'
        self.result.unlink(missing_ok=True)
        self.show_previews()
        try:
            index = int(self.gpu_index.get())
            if not 0 <= index <= 31: raise ValueError()
        except ValueError:
            messagebox.showerror('Invalid GPU index', 'Enter a GPU index from 0 to 31.'); return
        self.launch(['clean', str(self.source), str(self.result), mode, self.installed, str(index)], success=self.show_previews)

    def save(self):
        if self.proc: messagebox.showinfo('Busy', 'Finish or cancel the current operation first.'); return
        if not self.result.exists(): messagebox.showinfo('No result', 'Clean a page first.'); return
        path = filedialog.asksaveasfilename(defaultextension='.png', initialfile=self.source.stem + '-cleaned.png', filetypes=[('PNG image', '*.png')])
        if not path: return
        if Path(path).resolve() == self.source.resolve(): messagebox.showerror('Choose another file', 'The source image cannot be overwritten.'); return
        try: shutil.copyfile(self.result, path)
        except OSError as exc: messagebox.showerror('Save failed', str(exc))

    def cancel(self):
        if self.proc:
            if os.name == 'nt': subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.proc.pid)], capture_output=True, creationflags=NO_WINDOW)
            else:
                try: os.killpg(self.proc.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            self.append('Cancellation requested.')

    def remove_model(self):
        if self.proc: messagebox.showinfo('Busy', 'Cancel or finish the current operation first.'); return
        if messagebox.askyesno('Remove model', 'Delete the downloaded model and its download cache?'):
            for p in (ROOT / 'model-gguf', ROOT / 'model', ROOT / 'hf-cache', ROOT / 'text-detector'): shutil.rmtree(p, ignore_errors=True)
            (ROOT / 'model-ready').unlink(missing_ok=True)
            (ROOT / 'model-ready-q8').unlink(missing_ok=True)
            (ROOT / 'model-ready-fp8').unlink(missing_ok=True)
            self.refresh()

    def poll(self):
        try:
            while True:
                typ, value = self.events.get_nowait()
                if typ == 'line': self.append(value)
                else:
                    code, success = value
                    self.proc = None
                    self.operation = None
                    self.progress.stop()
                    self.progress_label.config(text='Ready' if code == 0 else 'Stopped or failed')
                    self.refresh()
                    if code == 0:
                        if success: success()
                    else:
                        self.append('Operation stopped or failed. Check the message above. For gated models, accept the license and use a Hugging Face read token; for GPU errors, check the driver and hardware.')
        except queue.Empty: pass
        if self.operation == 'download':
            # Local download files include resumable partial files.
            try:
                total = sum(p.stat().st_size for p in (ROOT / 'model-gguf').rglob('*') if p.is_file())
                self.progress_label.config(text=f'Model data on disk: {total / 1024**3:.2f} GiB (about 10.7 GB for Q8 model files)')
            except OSError: pass
        elif self.operation:
            self.progress_label.config(text={'setup': 'Installing runtime...', 'clean': 'Cleaning image...'}.get(self.operation, 'Working...'))
        self.after(1000, self.poll)

    def close(self):
        if not self.save_token(): return
        if self.proc: self.cancel()
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
