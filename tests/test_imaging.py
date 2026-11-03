import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from imaging import positions, tile_boxes, blend_tiles, fit_size
from worker import PROMPT


class ImageTests(unittest.TestCase):
    def test_positions_cover_without_large_overlap(self):
        for length in (1, 1024, 1025, 1793, 4000):
            starts = positions(length)
            self.assertEqual(starts[0], 0)
            self.assertGreaterEqual(starts[-1] + 1024, length)
            for a, b in zip(starts, starts[1:]):
                self.assertEqual(b - a, 896)

    def test_tiles_preserve_solid_color_and_dimensions(self):
        for size in ((1025, 1070), (200, 3300), (1500, 1500)):
            tiles = [(box, Image.new('RGB', (box[2]-box[0], box[3]-box[1]), (45, 90, 150))) for box in tile_boxes(size)]
            result = blend_tiles(size, tiles)
            self.assertEqual(result.size, size)
            self.assertEqual(result.getextrema(), ((45, 45), (90, 90), (150, 150)))

    def test_fitted_sizes(self):
        for size in ((3000, 4000), (10, 20), (1000, 1500)):
            w, h = fit_size(size)
            self.assertEqual(w % 16, 0)
            self.assertEqual(h % 16, 0)
            self.assertLessEqual(w*h, 4_030_000)

    def test_prompt_is_exact(self):
        self.assertEqual(PROMPT, 'Erase all lettering and sound effects, then rebuild the artwork underneath: continue the surrounding line art, shading, screentones and colour so the panel reads as if the text was never there. Match the drawing style and palette of the surrounding artwork exactly. Do not add text, symbols, signatures or new objects. Return one image with the same framing and borders as the input.')

if __name__ == '__main__': unittest.main()
