import base64
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sd_backend

class QuantizedTests(unittest.TestCase):
    def test_rejects_black_blocks_without_rejecting_original_black_art(self):
        white = Image.new('RGB', (256, 256), 'white')
        black = Image.new('RGB', (256, 256), 'black')
        mask = Image.new('L', (256, 256), 255)
        damaged = white.copy()
        damaged.paste('black', (0, 0, 128, 128))
        self.assertTrue(sd_backend.invalid_black_result(white, damaged, mask))
        self.assertFalse(sd_backend.invalid_black_result(black, black, mask))
        self.assertFalse(sd_backend.invalid_black_result(white, white, mask))
    def test_vulkan_runtime_and_explicit_device(self):
        self.assertIn('win-vulkan', sd_backend.ASSETS['Vulkan'][0][0])
        self.assertEqual(sd_backend.backend_args('Vulkan', platform='win32'), ['--backend', 'vulkan0', '--params-backend', 'disk', '--max-vram', 'vulkan0=4'])

    def test_linux_selects_only_the_requested_gpu(self):
        self.assertEqual(sd_backend.backend_args('ROCm', 1, 'linux'), ['--backend', 'rocm1'])
        self.assertEqual(sd_backend.backend_args('Vulkan', 2, 'linux'), ['--backend', 'vulkan2'])
        self.assertIn('Linux-Ubuntu-24.04', sd_backend.LINUX_ASSETS['ROCm'][0][0])
        self.assertIn('Linux-Ubuntu-24.04', sd_backend.LINUX_ASSETS['Vulkan'][0][0])

    def test_komatose_q8_files(self):
        self.assertEqual(sd_backend.FILES[0][2], 'flux3-image-klein-Q8_0.gguf')
        self.assertEqual(sd_backend.FILES[1][2], 'Qwen3VL-4B-Instruct-Q8_0.gguf')
        self.assertEqual(sd_backend.FILES[2][2], 'split_files/vae/flux2-vae.safetensors')

    def test_edit_request_has_sampling_and_mask(self):
        b = io.BytesIO(); Image.new('RGB', (32,32), 'red').save(b, format='PNG')
        result = json.dumps({'data': [{'b64_json': base64.b64encode(b.getvalue()).decode()}]}).encode()
        response = io.BytesIO(result)
        response.__enter__ = lambda self: self
        response.__exit__ = lambda self, *args: None
        with patch('urllib.request.urlopen', return_value=response) as request:
            image = sd_backend.edit_request('http://127.0.0.1:123', Image.new('RGB',(32,32)), 'test prompt')
        self.assertEqual(image.size, (32,32))
        payload = request.call_args.args[0].data
        self.assertIn(b'"sample_steps":16', payload)
        self.assertIn(b'"txt_cfg":1', payload)
        self.assertIn(b'name="mask"', payload)
        self.assertIn(b'test prompt', payload)

if __name__ == '__main__': unittest.main()
