import os
from pathlib import Path
import subprocess
import tempfile
import unittest


LAUNCHER = Path(__file__).resolve().parents[1] / 'MangoFlux.sh'


class LauncherTests(unittest.TestCase):
    def run_launcher(self, installed=False, install_fails=False, import_broken=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / 'bin'
            commands.mkdir()
            marker = root / 'tk-installed'
            log = root / 'commands.log'
            if installed:
                marker.touch()

            def executable(path, body):
                path.write_text('#!/bin/bash\n' + body)
                path.chmod(0o755)

            executable(commands / 'python3',
                       '[[ -f "$TK_MARKER" && "$IMPORT_BROKEN" != 1 ]]\n')
            executable(commands / 'sudo', 'exec "$@"\n')
            executable(commands / 'pacman',
                       'printf "pacman %s\\n" "$*" >> "$LAUNCH_LOG"\n'
                       '[[ "$INSTALL_FAILS" != 1 ]] || exit 1\n'
                       '/usr/bin/touch "$TK_MARKER"\n')
            venv = root / 'data' / 'MangoFlux' / 'venv' / 'bin'
            venv.mkdir(parents=True)
            executable(venv / 'python',
                       'printf "launched %s\\n" "$*" >> "$LAUNCH_LOG"\n')
            env = dict(os.environ, PATH=f'{commands}:/usr/bin:/bin',
                       XDG_DATA_HOME=str(root / 'data'), TK_MARKER=str(marker),
                       LAUNCH_LOG=str(log), INSTALL_FAILS=str(int(install_fails)),
                       IMPORT_BROKEN=str(int(import_broken)))
            result = subprocess.run(['/bin/bash', str(LAUNCHER)], env=env,
                                    capture_output=True, text=True, timeout=10)
            return result, log.read_text() if log.exists() else ''

    def test_existing_tk_skips_installation(self):
        result, log = self.run_launcher(installed=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('pacman', log)
        self.assertIn('launched', log)

    def test_missing_tk_is_installed_before_launch(self):
        result, log = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('pacman -S --needed --noconfirm tk', log)
        self.assertLess(log.index('pacman'), log.index('launched'))

    def test_installation_failure_stops_launch(self):
        result, log = self.run_launcher(install_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Tk installation failed', result.stdout)
        self.assertNotIn('launched', log)

    def test_failed_import_after_installation_stops_launch(self):
        result, log = self.run_launcher(import_broken=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('still cannot import tkinter', result.stdout)
        self.assertNotIn('launched', log)
