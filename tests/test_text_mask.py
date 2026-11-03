import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sd_backend import invalid_black_result
from imaging import composite_text
from text_mask import detect

class FakeSession:
    def __init__(self, *args, **kwargs): pass
    def get_inputs(self): return [types.SimpleNamespace(name='images')]
    def run(self, *_):
        segmentation = np.zeros((1, 1, 1024, 1024), dtype=np.float32)
        segmentation[0, 0, 400:500, 400:500] = 1
        return [np.zeros((1, 1, 6)), segmentation, np.zeros((1, 2, 1024, 1024))]

class MaskTests(unittest.TestCase):
    def test_art_outside_lettering_stays_identical(self):
        original = Image.new('RGB', (64, 64), (23, 45, 67))
        generated = Image.new('RGB', (64, 64), (240, 220, 200))
        mask = Image.new('L', (64, 64), 0)
        mask.paste(255, (30, 30, 34, 34))
        composite_text(original, generated, mask)
        self.assertEqual(original.getpixel((0, 0)), (23, 45, 67))
        self.assertEqual(original.getpixel((31, 31)), (240, 220, 200))

    def test_mask_selects_detection_and_leaves_background_clear(self):
        fake = types.SimpleNamespace(InferenceSession=FakeSession)
        with patch.dict(sys.modules, {'onnxruntime': fake}):
            mask = detect(Image.new('RGB', (1024, 1024), 'white'), 'fake.onnx', lambda _: None)
        self.assertEqual(mask.getpixel((450, 450)), 255)
        self.assertEqual(mask.getpixel((20, 20)), 0)

    def test_rejects_black_result_without_rejecting_black_source(self):
        mask = Image.new('L', (32, 32), 255)
        white = Image.new('RGB', (32, 32), 'white')
        black = Image.new('RGB', (32, 32), 'black')
        self.assertTrue(invalid_black_result(white, black, mask))
        self.assertFalse(invalid_black_result(black, black, mask))
        self.assertFalse(invalid_black_result(white, white, mask))

if __name__ == '__main__': unittest.main()
