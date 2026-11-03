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
    def test_vulkan_runtime_and_explicit_device(self):
        self.assertIn('win-vulkan', sd_backend.ASSETS['Vulkan'][0][0])
        self.assertEqual(sd_backend.backend_args('Vulkan'), ['--backend', 'vulkan0', '--params-backend', 'disk', '--max-vram', 'vulkan0=4'])

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
