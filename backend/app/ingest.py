"""Get the source video onto disk: from a URL via yt-dlp, or from an upload."""
import ipaddress
import json
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .config import MAX_VIDEO_MINUTES


def validate_url(url: str) -> str:
    """Block non-http(s) schemes and private/internal hosts (SSRF)."""
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("URL must be http(s)")
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror:
        raise ValueError("Could not resolve host")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("URL points to a private address")
    return url.strip()


def download(url: str, out_dir: Path) -> Path:
    out = out_dir / "source.mp4"
    cmd = [
        "yt-dlp", "--no-playlist", "--no-progress",
        "--match-filter", f"duration < {MAX_VIDEO_MINUTES * 60}",
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4", "-o", str(out), url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"Download failed: {(r.stderr or r.stdout)[-400:]}")
    return out


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(r.stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not v:
        raise RuntimeError("No video stream found")
    duration = float(info["format"]["duration"])
    if duration > MAX_VIDEO_MINUTES * 60:
        raise RuntimeError(f"Video longer than {MAX_VIDEO_MINUTES} minutes")
    return {"duration": duration, "width": int(v["width"]), "height": int(v["height"])}


def extract_audio(src: Path, out_dir: Path) -> Path:
    """16 kHz mono WAV — what Whisper wants, and cheap to analyse for loudness."""
    wav = out_dir / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        check=True,
    )
    return wav
