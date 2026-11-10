import os
from pathlib import Path

DATA_DIR = Path(os.getenv("CLIPPER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # tiny|base|small|medium|large-v3
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")  # auto|cpu|cuda
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "4096"))
MAX_VIDEO_MINUTES = int(os.getenv("MAX_VIDEO_MINUTES", "180"))
WORKERS = int(os.getenv("WORKERS", "2"))
X264_PRESET = os.getenv("X264_PRESET", "veryfast")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

DATA_DIR.mkdir(parents=True, exist_ok=True)
