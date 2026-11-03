"""Detect comic lettering locally and build a conservative editable-pixel mask."""
from PIL import Image, ImageChops, ImageFilter


def detect(image, model_path, event):
    import numpy as np
    import onnxruntime as ort

    event('Detecting lettering with Comic Text Detector...')
    session = ort.InferenceSession(str(model_path), providers=['CPUExecutionProvider'])
    width, height = image.size
    combined = Image.new('L', image.size, 0)
    for top in range(0, height, 768):
        bottom = min(height, top + 1024)
        crop = image.crop((0, top, width, bottom)).convert('RGB')
        scale = min(1024 / crop.width, 1024 / crop.height)
        nw = max(1, round(crop.width * scale))
        nh = max(1, round(crop.height * scale))
        px, py = (1024 - nw) // 2, (1024 - nh) // 2
        padded = Image.new('RGB', (1024, 1024), (114, 114, 114))
        padded.paste(crop.resize((nw, nh), Image.Resampling.BILINEAR), (px, py))
        tensor = (np.asarray(padded, dtype=np.float32) / 255.0).transpose(2, 0, 1)[None]
        outputs = session.run(None, {session.get_inputs()[0].name: tensor})
        masks = [x for x in outputs if x.ndim == 4 and x.shape[1] == 1]
        if len(masks) != 1:
            raise RuntimeError('Unexpected Comic Text Detector output; no page was changed.')
        probability = np.asarray(masks[0][0, 0], dtype=np.float32)
        if not np.isfinite(probability).all():
            raise RuntimeError('Text detector returned invalid values; no page was changed.')
        mask = Image.fromarray(np.uint8(np.clip(probability, 0, 1) * 255), mode='L')
        if mask.size != (1024, 1024):
            mask = mask.resize((1024, 1024), Image.Resampling.BILINEAR)
        mask = mask.crop((px, py, px + nw, py + nh)).resize(crop.size, Image.Resampling.BILINEAR)
        mask = mask.point(lambda p: 255 if p >= 77 else 0).filter(ImageFilter.MaxFilter(11))
        current = combined.crop((0, top, width, bottom))
        combined.paste(ImageChops.lighter(current, mask), (0, top))
        if bottom == height:
            break
    count = combined.histogram()[255]
    if count == 0:
        raise RuntimeError('No lettering was detected; no page was changed.')
    if count > width * height * 0.4:
        raise RuntimeError('The text mask covers too much of the page; no page was changed.')
    event(f'Detected lettering in {100 * count / (width * height):.1f}% of the page.')
    return combined
