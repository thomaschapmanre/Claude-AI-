"""Pick the best 15–60s moments.

Two scorers share one validation step:
  1. Claude reads the timestamped transcript + loudness spikes and proposes clips
     with hooks, titles, captions, hashtags and a viral score with reasons.
  2. A local heuristic (hook words, loudness, pace, emotion, clean ending) — used when
     no ANTHROPIC_API_KEY is set or the API call fails, so the tool always works.
"""
import logging
import os
import re
import statistics

from pydantic import BaseModel

from .config import CLAUDE_MODEL

log = logging.getLogger(__name__)
MIN_LEN, MAX_LEN = 15.0, 60.0

HOOK_WORDS = re.compile(
    r"\b(here'?s|truth|never|nobody|no one|why|how|secret|stop|mistake|worst|best|crazy|"
    r"insane|actually|biggest|wrong|everyone|you need|the reason|imagine|what if)\b", re.I)
EMOTION_WORDS = re.compile(
    r"\b(love|hate|amazing|terrible|shocked|crazy|insane|unbelievable|hilarious|scared|angry|"
    r"cried|died|million|billion|fired|broke|rich|money|fight|controversial|honestly|literally)\b", re.I)


class ClipIdea(BaseModel):
    start: float
    end: float
    hook: str
    title: str
    caption: str
    hashtags: list[str]
    viral_score: int
    category: str
    reasons: list[str]


class ClipIdeas(BaseModel):
    clips: list[ClipIdea]


# ---------- shared helpers ----------

def _words(transcript: dict) -> list[dict]:
    return [w for s in transcript["segments"] for w in s["words"]]


def snap(start: float, end: float, words: list[dict]) -> tuple[float, float] | None:
    """Snap to word boundaries and force the 15–60s window."""
    if not words:
        return None
    first = next((w for w in words if w["e"] > start), None)
    if not first:
        return None
    s = first["s"]
    inside = [w for w in words if w["s"] >= s and w["e"] <= max(end, s + MIN_LEN) + 0.5]
    e = inside[-1]["e"] if inside else end
    if e - s > MAX_LEN:
        e = max((w["e"] for w in words if w["s"] >= s and w["e"] <= s + MAX_LEN), default=s + MAX_LEN)
    if e - s < MIN_LEN:
        later = [w["e"] for w in words if w["e"] >= s + MIN_LEN]
        if not later:
            return None
        e = min(later)
        if e - s > MAX_LEN:
            return None
    return round(max(0.0, s - 0.15), 2), round(e + 0.25, 2)


def dedupe(clips: list[dict], n: int) -> list[dict]:
    """Highest score first, drop anything overlapping a kept clip by >30%."""
    kept: list[dict] = []
    for c in sorted(clips, key=lambda c: -c["score"]):
        ok = all(
            max(0, min(c["end"], k["end"]) - max(c["start"], k["start"])) < 0.3 * (c["end"] - c["start"])
            for k in kept
        )
        if ok:
            kept.append(c)
        if len(kept) == n:
            break
    return kept


def loud_moments(loudness: list[float], top: int = 15) -> list[int]:
    if len(loudness) < 10:
        return []
    med = statistics.median(loudness)
    peaks = [i for i, v in enumerate(loudness) if v > med + 8]
    return sorted(peaks, key=lambda i: -loudness[i])[:top]


def text_between(transcript: dict, start: float, end: float) -> str:
    return " ".join(w["w"] for w in _words(transcript) if start <= w["s"] < end)


# ---------- heuristic scorer ----------

def heuristic(transcript: dict, loudness: list[float], n: int) -> list[dict]:
    segs = transcript["segments"]
    words = _words(transcript)
    med = statistics.median(loudness) if loudness else -30.0
    cands = []
    for i, first in enumerate(segs):
        for j in range(i, len(segs)):
            dur = segs[j]["end"] - first["start"]
            if dur > MAX_LEN:
                break
            if dur < MIN_LEN:
                continue
            text = " ".join(s["text"] for s in segs[i : j + 1])
            nwords = len(text.split())
            loud = loudness[int(first["start"]) : int(segs[j]["end"]) + 1] or [med]
            reasons, score = [], 0.0

            hook_hits = len(HOOK_WORDS.findall(first["text"])) + ("?" in first["text"]) + bool(re.search(r"\d", first["text"]))
            score += min(30, hook_hits * 12)
            if hook_hits:
                reasons.append("Opens with a hook (question, bold claim or number)")

            energy = statistics.mean(loud) - med + 0.5 * (max(loud) - med)
            score += max(0, min(25, energy * 2.5))
            if max(loud) - med > 8:
                reasons.append("Audio spike — likely laughter, shouting or a big reaction")

            pace = nwords / dur
            score += 15 - min(15, abs(pace - 3.0) * 8)
            if 2.4 <= pace <= 3.8:
                reasons.append("Fast, dense delivery that holds attention")

            emo = len(EMOTION_WORDS.findall(text))
            score += min(20, emo * 5)
            if emo >= 2:
                reasons.append("Emotional / high-stakes language")

            if segs[j]["text"].rstrip().endswith((".", "!", "?")):
                score += 10
                reasons.append("Ends on a complete thought")
            if 25 <= dur <= 45:
                score += 5

            cands.append({"start": first["start"], "end": segs[j]["end"], "score": round(min(99, score)), "reasons": reasons or ["Steady, clear segment"], "first": first["text"]})

    out = []
    for c in dedupe(cands, n):
        sn = snap(c["start"], c["end"], words)
        if not sn:
            continue
        hook = c["first"].split(".")[0][:60]
        out.append({
            "start": sn[0], "end": sn[1], "score": c["score"], "reasons": c["reasons"], "category": "highlight",
            "hook": hook, "title": hook, "caption": hook + " 👀",
            "hashtags": ["#fyp", "#viral", "#clips", "#podcast", "#reels"],
        })
    return out


# ---------- Claude scorer ----------

PROMPT = """You are a top short-form video editor who has grown many clip accounts on TikTok and Instagram Reels.
Below is a timestamped transcript of a long video. Pick the {n} best moments to post as standalone vertical clips.

Rules:
- Each clip is {min_len:.0f}–{max_len:.0f} seconds and must make sense with zero context.
- Start right on the hook (no warm-up), end on a payoff or punchline, never mid-sentence.
- Prefer: strong hooks, emotional peaks, punchlines, surprising insights, controversial takes, stories with a payoff.
- Clips must not overlap.
- "hook": an on-screen text hook (max 8 words) that creates curiosity; empty string if the opening line is already a perfect hook.
- "title": a short post title. "caption": a ready-to-post caption (1–2 sentences, may include one emoji). "hashtags": 4–7 relevant hashtags with #.
- "viral_score": 0–100, calibrated (most clips 50–80; 90+ only for exceptional moments).
- "reasons": 2–4 short, specific reasons tied to what is said (not generic).
- "category": one of hook, story, insight, funny, emotional, controversial.

Loud audio moments (seconds; often laughter or big reactions): {loud}

Transcript:
{transcript}"""


def with_claude(transcript: dict, loudness: list[float], n: int) -> list[dict]:
    import anthropic

    lines = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in transcript["segments"])
    resp = anthropic.Anthropic().messages.parse(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": PROMPT.format(
            n=n, min_len=MIN_LEN, max_len=MAX_LEN, loud=loud_moments(loudness) or "none", transcript=lines)}],
        output_format=ClipIdeas,
    )
    if resp.stop_reason != "end_turn" or not resp.parsed_output:
        raise RuntimeError(f"Claude returned stop_reason={resp.stop_reason}")
    words = _words(transcript)
    out = []
    for c in resp.parsed_output.clips:
        sn = snap(c.start, c.end, words)
        if sn:
            out.append({**c.model_dump(exclude={"start", "end", "viral_score"}), "start": sn[0], "end": sn[1],
                        "score": max(0, min(100, c.viral_score))})
    return out


def find_highlights(transcript: dict, loudness: list[float], n: int = 8) -> tuple[list[dict], str]:
    """Returns (clips sorted by score, engine used)."""
    if not transcript["segments"]:
        return [], "none"
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            clips = dedupe(with_claude(transcript, loudness, n), n)
            if clips:
                return clips, "claude"
        except Exception:
            log.exception("Claude highlight detection failed; using heuristic")
    return heuristic(transcript, loudness, n), "heuristic"
