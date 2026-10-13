"""Captions + intro/outro cards + ffmpeg walkthrough video.

Uses ./enhanced/<room>.jpg; if ./staged/<room>.jpg exists the clip shows the
empty room for 1.5s then crossfades to the staged version.
Env: PROPERTY (name for title/file), MUSIC (path to mp3), BRAND (hex accent).
"""
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
BUILD = HERE / "build"
FONT = "/usr/share/fonts/opentype/inter/Inter-{}.otf"
PROPERTY = os.environ.get("PROPERTY", "")
MUSIC = os.environ.get("MUSIC", "")
ACCENT = os.environ.get("BRAND", "#C9A46A")
W, H, FPS, CLIP, CARD, XF = 1920, 1080, 30, 5.0, 3.5, 0.8

ROOMS = [  # (file stem, label, feature note) - identified from the photos
    ("01-kitchen", "Kitchen", "Stainless appliances, granite counters & tile backsplash"),
    ("02-living", "Living Area", "Open layout with sliding glass door & ceiling fan"),
    ("03-balcony", "Balcony", "Covered private balcony with open views"),
    ("04-primary-bedroom", "Primary Bedroom", "Ceiling fan, walk-in closet & private en suite"),
    ("05-walk-in-closet", "Walk-In Closet", "Built-in shelving and hanging rods on two walls"),
    ("06-en-suite-bath", "En Suite Bath", "Walk-in shower & granite vanity"),
    ("07-second-bedroom", "Second Bedroom", "Bright room with plush carpet"),
    ("08-second-bath", "Second Bath", "Tub/shower combo & granite vanity"),
]


def font(weight, size):
    return ImageFont.truetype(FONT.format(weight), size)


def frame_16x9(src, dst):
    """Bottom-anchored 16:9 crop (keeps the corner watermark), scaled to 4K for smooth zoompan."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    ch = round(w * 9 / 16)
    im.crop((0, h - ch, w, h)).resize((W * 2, H * 2), Image.LANCZOS).save(dst, quality=95)


def caption_png(i, label, note, dst):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.linear_gradient("L").resize((W, 420)).point(lambda v: int(v * 0.72))
    im.paste((0, 0, 0, 255), (0, H - 420), grad)
    d = ImageDraw.Draw(im)
    x, y = 90, H - 200
    d.rectangle((x - 28, y + 6, x - 20, y + 128), fill=ACCENT)
    d.text((x, y), label, font=font("SemiBold", 64), fill="white")
    d.text((x, y + 88), note, font=font("Regular", 34), fill=(235, 235, 235))
    # counter sits above the bottom-right corner so it never covers the photo watermark
    d.text((W - 90, H - 120), f"{i:02d} / {len(ROOMS):02d}", font=font("SemiBold", 34),
           fill="white", anchor="rs")
    im.save(dst)


def card_png(photo, lines, dst):
    im = Image.open(photo).convert("RGB").resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.42))
    d = ImageDraw.Draw(im)
    y = H // 2 - 40 * len(lines)
    for text, weight, size, fill in lines:
        d.text((W // 2, y), text, font=font(weight, size), fill=fill, anchor="mm")
        y += size + 40
    d.line((W // 2 - 80, y - 10, W // 2 + 80, y - 10), fill=ACCENT, width=4)
    if (HERE / "logo.png").exists():
        logo = Image.open(HERE / "logo.png").convert("RGBA")
        logo.thumbnail((360, 160))
        im.paste(logo, ((W - logo.width) // 2, 110), logo)
    im.save(dst, quality=95)


def zoompan(i):
    """Alternate zoom-in, pan right, zoom-out, pan left (max 12%), eased, anchored at the bottom."""
    n = int(CLIP * FPS)
    p = f"(1-cos(PI*on/{n - 1}))/2"
    z, x = [("1+0.12*" + p, "iw-iw/zoom"), ("1.12", f"(iw-iw/zoom)*{p}"),
            ("1.12-0.12*" + p, "iw-iw/zoom"), ("1.12", f"(iw-iw/zoom)*(1-{p})")][i % 4]
    return f"zoompan=z='{z}':x='{x}':y='ih-ih/zoom':d={n}:s={W}x{H}:fps={FPS}"


def ff(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *args], check=True)


ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def build_room(i, stem, label, note):
    still, cap, out = BUILD / f"{stem}_4k.jpg", BUILD / f"{stem}_cap.png", BUILD / f"{stem}.mp4"
    frame_16x9(HERE / "enhanced" / f"{stem}.jpg", still)
    caption_png(i + 1, label, note, cap)
    staged = HERE / "staged" / f"{stem}.jpg"
    if staged.exists():
        sstill = BUILD / f"{stem}_staged_4k.jpg"
        frame_16x9(staged, sstill)
        # same motion on both, then a time-based blend so the camera move stays continuous
        fc = (f"[0]{zoompan(i)},format=yuv444p[a];[1]{zoompan(i)},format=yuv444p[b];"
              f"[a][b]blend=all_expr='A*(1-clip((T-1.5)/{XF},0,1))+B*clip((T-1.5)/{XF},0,1)'[v];"
              f"[v][2]overlay[o]")
        ff("-i", still, "-i", sstill, "-i", cap, "-filter_complex", fc, "-map", "[o]", *ENC, out)
    else:
        ff("-i", still, "-i", cap, "-filter_complex", f"[0]{zoompan(i)}[v];[v][1]overlay[o]",
           "-map", "[o]", *ENC, out)
    return out


def build_card(png, out):
    n = int(CARD * FPS)
    ff("-i", png, "-vf", f"zoompan=z='1+0.04*on/{n}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={n}:s={W}x{H}:fps={FPS}",
       *ENC, out)
    return out


def main():
    BUILD.mkdir(exist_ok=True)
    title = [(PROPERTY.upper(), "SemiBold", 48, ACCENT)] if PROPERTY else []
    card_png(HERE / "enhanced/02-living.jpg", title + [
        ("VIRTUAL WALKTHROUGH", "SemiBold", 96, "white"),
        ("2 Bed  ·  2 Bath  ·  1,100 sq ft", "Regular", 48, (230, 230, 230))], BUILD / "intro.jpg")
    card_png(HERE / "enhanced/03-balcony.jpg", title + [
        ("Schedule your tour today", "SemiBold", 88, "white"),
        ("2 Bed  ·  2 Bath  ·  1,100 sq ft", "Regular", 44, (230, 230, 230))], BUILD / "outro.jpg")

    clips = [build_card(BUILD / "intro.jpg", BUILD / "intro.mp4")]
    clips += [build_room(i, *r) for i, r in enumerate(ROOMS)]
    clips.append(build_card(BUILD / "outro.jpg", BUILD / "outro.mp4"))

    durs = [CARD] + [CLIP] * len(ROOMS) + [CARD]
    chain, prev, t = [], "[0:v]", 0.0
    for k in range(1, len(clips)):
        t += durs[k - 1] - XF
        chain.append(f"{prev}[{k}:v]xfade=transition=fade:duration={XF}:offset={t:.3f}[x{k}]")
        prev = f"[x{k}]"
    total = sum(durs) - XF * (len(clips) - 1)

    name = (PROPERTY.replace(" ", "-") + "-" if PROPERTY else "") + "2BR-" + \
        ("Staged-" if (HERE / "staged").exists() and any((HERE / "staged").iterdir()) else "") + "Walkthrough.mp4"
    args = [x for c in clips for x in ("-i", c)]
    audio = []
    if MUSIC:
        args += ["-i", MUSIC]
        chain.append(f"[{len(clips)}:a]atrim=0:{total},afade=t=in:d=2,afade=t=out:st={total - 2}:d=2[a]")
        audio = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    ff(*args, "-filter_complex", ";".join(chain), "-map", prev, *audio, *ENC,
       "-movflags", "+faststart", "-t", f"{total}", HERE / name)
    print(HERE / name, f"{total:.1f}s")


if __name__ == "__main__":
    main()
