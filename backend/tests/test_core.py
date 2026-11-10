from app import highlights, render


def _transcript():
    # 40 sentences of 5 words, 0.4s per word, 0.5s gap between sentences -> ~100s of speech
    segs, t = [], 0.0
    for i in range(40):
        words = []
        text = "Here's the secret nobody tells you?" if i == 20 else f"this is sentence number {i}."
        for w in text.split():
            words.append({"w": w, "s": round(t, 2), "e": round(t + 0.35, 2)})
            t += 0.4
        segs.append({"start": words[0]["s"], "end": words[-1]["e"], "text": text, "words": words})
        t += 0.5
    return {"language": "en", "segments": segs}


def test_snap_enforces_length_and_word_bounds():
    words = [w for s in _transcript()["segments"] for w in s["words"]]
    s, e = highlights.snap(10.1, 12.0, words)  # too short -> extended
    assert 15 <= e - s <= 60.5
    s, e = highlights.snap(0, 500, words)  # too long -> trimmed
    assert e - s <= 60.5
    assert highlights.snap(10_000, 10_020, words) is None


def test_dedupe_drops_overlaps_and_keeps_best():
    clips = [{"start": 0, "end": 30, "score": 50}, {"start": 5, "end": 35, "score": 90}, {"start": 40, "end": 70, "score": 10}]
    assert [c["score"] for c in highlights.dedupe(clips, 5)] == [90, 10]


def test_heuristic_finds_hook_and_valid_clips():
    tr = _transcript()
    loud = [-30.0] * 120
    loud[60] = -10.0  # spike near the hook sentence
    clips = highlights.heuristic(tr, loud, 3)
    assert clips and all(15 <= c["end"] - c["start"] <= 60.5 for c in clips)
    best = clips[0]
    assert "secret" in highlights.text_between(tr, best["start"], best["end"]).lower()


def test_find_highlights_without_key_uses_heuristic(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    clips, engine = highlights.find_highlights(_transcript(), [-30.0] * 120, 2)
    assert engine == "heuristic" and len(clips) == 2


def test_ass_highlights_active_word_and_hook():
    words = [{"w": "hello", "s": 1.0, "e": 1.3}, {"w": "big", "s": 1.4, "e": 1.6}, {"w": "world!", "s": 1.7, "e": 2.0}]
    ass = render.build_ass(words, 1.0, 20.0, "Wait for it", True)
    assert "WAIT FOR IT" in ass
    assert ass.count("Dialogue: 0") == 3  # one event per active word
    assert "{\\c&H0000E5FF&}BIG" in ass
