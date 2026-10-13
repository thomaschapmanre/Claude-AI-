"""Crop phone-screenshot bars and enhance photos -> ./enhanced (1920x1280)."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).parent


def photo_box(a):
    """Bounding box of the photo: longest run of rows that are mostly non-black."""
    lum = a.mean(axis=2)
    rows = (lum > 12).mean(axis=1) > 0.5
    best, start = (0, 0), None
    for i, r in enumerate(np.append(rows, False)):
        if r and start is None:
            start = i
        elif not r and start is not None:
            best = max(best, (start, i), key=lambda s: s[1] - s[0])
            start = None
    y0, y1 = best
    cols = np.where((lum[y0:y1] > 12).mean(axis=0) > 0.5)[0]
    return cols[0], y0, cols[-1] + 1, y1


def enhance(a):
    x = a.astype(np.float64) / 255
    # partial gray-world white balance, 60% strength
    m = x.reshape(-1, 3).mean(axis=0)
    x *= 1 + 0.6 * (m.mean() / m - 1)
    # levels: black 0, white at 99.7th luminance percentile
    lum = x @ [0.2126, 0.7152, 0.0722]
    x = np.clip(x / np.percentile(lum, 99.7), 0, 1)
    # midtone lift + gentle shadow lift
    x = x ** 0.82
    x = x + 0.06 * x * (1 - x) ** 3
    # saturation +8%
    lum = (x @ [0.2126, 0.7152, 0.0722])[..., None]
    x = np.clip(lum + 1.08 * (x - lum), 0, 1)
    return (x * 255 + 0.5).astype(np.uint8)


def main(src=HERE / "photos", dst=HERE / "enhanced"):
    dst.mkdir(exist_ok=True)
    for p in sorted(src.glob("*.*")):
        im = Image.open(p).convert("RGB")
        box = photo_box(np.asarray(im))
        im = im.crop(box)
        # center-crop to 3:2 so the resize doesn't stretch
        w, h = im.size
        if w / h > 1.5:
            nw = round(h * 1.5); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w / 1.5); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        out = Image.fromarray(enhance(np.asarray(im))).resize((1920, 1280), Image.LANCZOS)
        out = out.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))
        out.save(dst / (p.stem + ".jpg"), quality=94)
        print(p.name, "photo box", box)


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:]))
