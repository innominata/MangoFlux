import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worker

class SetupTests(unittest.TestCase):
    def test_run_relays_errors_and_fails(self):
        import contextlib
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, 'exit code 7'):
                worker.run([sys.executable, '-c', 'import sys; print("diagnostic", file=sys.stderr); sys.exit(7)'])
        self.assertIn('diagnostic', output.getvalue())

if __name__ == '__main__': unittest.main()
