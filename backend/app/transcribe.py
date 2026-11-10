"""Word-level transcription with faster-whisper, plus per-second loudness."""
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import WHISPER_DEVICE, WHISPER_MODEL


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    compute = "int8" if WHISPER_DEVICE in ("auto", "cpu") else "float16"
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=compute)


def transcribe(wav: Path, on_progress=lambda p: None) -> dict:
    segments, info = _model().transcribe(str(wav), word_timestamps=True, vad_filter=True)
    out = []
    for s in segments:
        words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for w in (s.words or []) if w.word.strip()]
        if words:
            out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(), "words": words})
            on_progress(min(1.0, s.end / max(info.duration, 1)))
    return {"language": info.language, "segments": out}


def loudness_per_second(wav: Path) -> list[float]:
    """RMS dB per second; spikes ≈ laughter, shouting, applause."""
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(pcm) // sr
    if n == 0:
        return []
    rms = np.sqrt(np.mean(pcm[: n * sr].reshape(n, sr) ** 2, axis=1)) + 1e-6
    return [round(float(x), 2) for x in 20 * np.log10(rms)]
