import os
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths


class PathsTests(unittest.TestCase):
    def test_linux_data_home_is_shared(self):
        fake_os = SimpleNamespace(name='posix', environ={'XDG_DATA_HOME': 'test-data'})
        with patch.object(paths, 'os', fake_os):
            self.assertEqual(paths.data_root(), Path('test-data') / 'MangoFlux')


if __name__ == '__main__': unittest.main()
