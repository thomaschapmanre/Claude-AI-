"""Render a clip: 9:16 reframe → optional push-in zoom → burned-in word-by-word captions + hook."""
import os
import statistics
import subprocess
from pathlib import Path

from .config import X264_PRESET

W, H = 1080, 1920
FONT = os.getenv("CAPTION_FONT", "Montserrat ExtraBold")  # falls back via fontconfig if missing


def face_center_x(src: Path, start: float, end: float, samples: int = 8) -> float:
    """Median horizontal face position (0–1) over the clip; 0.5 when no face is found.
    shortcut: one static crop per clip, upgrade to per-shot tracking (mediapipe + scene cuts) for multi-speaker videos."""
    import cv2

    cap = cv2.VideoCapture(str(src))
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    xs = []
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_MSEC, (start + (end - start) * (i + 0.5) / samples) * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = det.detectMultiScale(gray, 1.2, 5, minSize=(gray.shape[0] // 10, gray.shape[0] // 10))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + w / 2) / frame.shape[1])
    cap.release()
    return statistics.median(xs) if xs else 0.5


def _ts(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").upper()


def build_ass(words: list[dict], start: float, end: float, hook: str, captions: bool) -> str:
    out = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{FONT},88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,2,80,80,560,1",
        f"Style: Hook,{FONT},70,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,90,90,300,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook:
        out.append(f"Dialogue: 1,{_ts(0)},{_ts(min(3.5, end - start))},Hook,,0,0,0,,{{\\fad(150,200)}}{_esc(hook)}")
    if captions:
        ws = [w for w in words if w["s"] >= start - 0.05 and w["e"] <= end + 0.05]
        # chunk into 1–3 word groups, breaking on punctuation or pauses
        chunks, cur = [], []
        for i, w in enumerate(ws):
            cur.append(w)
            nxt = ws[i + 1] if i + 1 < len(ws) else None
            if len(cur) == 3 or w["w"][-1:] in ".,!?" or not nxt or nxt["s"] - w["e"] > 0.6:
                chunks.append(cur)
                cur = []
        for chunk in chunks:
            for k, w in enumerate(chunk):
                t0 = w["s"] - start
                t1 = (chunk[k + 1]["s"] if k + 1 < len(chunk) else w["e"]) - start
                text = " ".join(
                    ("{\\c&H0000E5FF&}" + _esc(x["w"]) + "{\\c&H00FFFFFF&}") if j == k else _esc(x["w"])
                    for j, x in enumerate(chunk)
                )
                pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
                out.append(f"Dialogue: 0,{_ts(t0)},{_ts(max(t1, t0 + 0.05))},Cap,,0,0,0,,{pop}{text}")
    return "\n".join(out) + "\n"


def video_filter(src_w: int, src_h: int, layout: str, face_x: float, zoom: bool, dur: float) -> str:
    if layout == "fit":
        # whole frame centred over a blurred, cropped copy of itself
        v = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:2[bg];"
             f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    elif src_w / src_h > W / H:
        cw = int(src_h * W / H) // 2 * 2
        x = int(min(max(face_x * src_w - cw / 2, 0), src_w - cw))
        v = f"[0:v]crop={cw}:{src_h}:{x}:0,scale={W}:{H}"
    else:
        ch = int(src_w * H / W) // 2 * 2
        v = f"[0:v]crop={src_w}:{ch}:0:(ih-{ch})/2,scale={W}:{H}"
    if zoom:
        v += (f",scale=w='trunc({W}*(1+0.08*t/{dur:.2f})/2)*2':h='trunc({H}*(1+0.08*t/{dur:.2f})/2)*2':eval=frame,"
              f"crop={W}:{H}")
    return v + ",setsar=1,ass=captions.ass[v]"


def render_clip(src: Path, meta: dict, words: list[dict], clip: dict, out_dir: Path) -> None:
    """Writes out_dir/clip.mp4, out_dir/thumb.jpg."""
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = clip["start"], clip["end"]
    dur = end - start
    (out_dir / "captions.ass").write_text(build_ass(words, start, end, clip.get("hook", ""), clip.get("captions", True)))
    face_x = face_center_x(src, start, end) if clip.get("layout", "crop") == "crop" else 0.5
    vf = video_filter(meta["width"], meta["height"], clip.get("layout", "crop"), face_x, clip.get("zoom", False), dur)
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(src.resolve()),
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", X264_PRESET, "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", "clip.tmp.mp4",
    ]
    r = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-500:]}")
    os.replace(out_dir / "clip.tmp.mp4", out_dir / "clip.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1", "-i", "clip.mp4", "-frames:v", "1", "-vf", "scale=360:-2", "thumb.jpg"],
                   cwd=out_dir, check=True)
