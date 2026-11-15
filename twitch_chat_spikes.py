#!/usr/bin/env python3
"""
Twitch chat spike detector - finds clip-worthy moments in a VOD chat log.

Input:  chat JSON downloaded with TwitchDownloader.
Output: the top moments where chat suddenly blew up, with a suggested clip
        start time, printed to the screen and saved to a text file.

Usage:
    python twitch_chat_spikes.py chat.json
    python twitch_chat_spikes.py chat.json --threshold 2.5 --top 30

Standard library only. Needs Python 3.8 or newer.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

# --------------------------------------------------------------------------
# Settings you may want to tweak
# --------------------------------------------------------------------------
WINDOW_SECONDS = 10        # size of each counting window
ROLLING_SECONDS = 300      # how far back the "normal chat speed" average looks
SPIKE_MULTIPLIER = 3.0     # a spike is this many times the rolling average
PRE_ROLL_SECONDS = 20      # start the clip this long before the spike
TOP_N = 20                 # how many moments to list
MIN_MESSAGES = 5           # ignore windows with fewer messages than this
MERGE_GAP_SECONDS = 20     # spikes closer together than this are one moment
SAMPLE_COUNT = 5           # chat messages to show per moment
HYPE_WEIGHT = 1.0          # multiplies every bonus below (0 = ignore hype words)

# Single words/emotes: a message containing one counts as (1 + bonus) messages.
# Matched as whole words, ignoring upper/lower case.
HYPE_WORDS = {
    "kekw": 1.0,
    "lul": 1.0,
    "omegalul": 1.5,
    "w": 0.5,
}
# Anything starting with these counts too (Pog, PogChamp, POGGERS, PogU...).
HYPE_PREFIXES = {
    "pog": 1.0,
}
# Phrases, matched anywhere in the message, ignoring upper/lower case.
HYPE_PHRASES = {
    "clip it": 2.0,
    "no way": 1.0,
}
# --------------------------------------------------------------------------

WORD_RE = re.compile(r"[a-z0-9']+")


def hype_bonus(text):
    """Extra weight for a message. Uses the strongest hype term it contains."""
    lowered = text.lower()
    best = 0.0
    for word in WORD_RE.findall(lowered):
        if word in HYPE_WORDS:
            best = max(best, HYPE_WORDS[word])
        for prefix, bonus in HYPE_PREFIXES.items():
            if word.startswith(prefix):
                best = max(best, bonus)
    normalized = " ".join(lowered.split())
    for phrase, bonus in HYPE_PHRASES.items():
        if phrase in normalized:
            best = max(best, bonus)
    return best


def hhmmss(seconds):
    seconds = int(max(0, seconds))
    return "%02d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


def load_messages(path):
    """Return a list of (offset_seconds, text) from a TwitchDownloader JSON."""
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    comments = data.get("comments") if isinstance(data, dict) else data
    if not isinstance(comments, list):
        raise ValueError(
            "No 'comments' list found. Is this a chat JSON from TwitchDownloader?"
        )

    messages = []
    for c in comments:
        if not isinstance(c, dict):
            continue
        offset = c.get("content_offset_seconds")
        if not isinstance(offset, (int, float)):
            continue
        msg = c.get("message")
        body = msg.get("body") if isinstance(msg, dict) else None
        if not isinstance(body, str):
            body = ""
        messages.append((float(offset), body.strip()))
    messages.sort(key=lambda m: m[0])
    return messages


def find_moments(messages, args):
    window = args.window
    n_windows = int(messages[-1][0] // window) + 1

    counts = [0] * n_windows        # raw messages per window
    scores = [0.0] * n_windows      # messages + hype bonuses per window
    texts = [[] for _ in range(n_windows)]
    for offset, text in messages:
        i = int(offset // window)
        counts[i] += 1
        scores[i] += 1.0 + args.hype_weight * hype_bonus(text)
        if text:
            texts[i].append(text)

    # Baseline = average score of the windows BEFORE this one (trailing
    # average), so the spike itself doesn't inflate what it's compared to.
    # A floor stops dead-quiet stretches from turning 4 messages into a "spike".
    overall_mean = sum(scores) / n_windows
    floor = max(1.0, overall_mean * 0.5)
    lookback = max(1, int(args.rolling // window))
    prefix = [0.0]
    for s in scores:
        prefix.append(prefix[-1] + s)

    ratios = [0.0] * n_windows
    for i in range(n_windows):
        lo = max(0, i - lookback)
        if i - lo >= 3:
            baseline = (prefix[i] - prefix[lo]) / (i - lo)
        else:  # very start of the VOD: not enough history yet
            baseline = overall_mean
        ratios[i] = scores[i] / max(baseline, floor)

    spike_idx = [
        i for i in range(n_windows)
        if ratios[i] >= args.threshold and counts[i] >= args.min_messages
    ]

    # Merge neighbouring spike windows into one moment.
    max_gap = int(args.merge_gap // window) + 1
    groups = []
    for i in spike_idx:
        if groups and i - groups[-1][-1] <= max_gap:
            groups[-1].append(i)
        else:
            groups.append([i])

    moments = []
    for group in groups:
        peak = max(group, key=lambda i: scores[i])
        spike_start = group[0] * window
        moments.append({
            "spike": spike_start,
            "clip_start": max(0, spike_start - args.pre_roll),
            "msgs_per_sec": counts[peak] / window,
            "ratio": max(ratios[i] for i in group),
            "length": (group[-1] - group[0] + 1) * window,
            "samples": pick_samples(texts[peak], args.samples),
        })

    moments.sort(key=lambda m: m["ratio"], reverse=True)
    moments = moments[: args.top]
    if args.chrono:
        moments.sort(key=lambda m: m["spike"])
    return moments


def pick_samples(window_texts, how_many):
    """Most-repeated messages first, then the rest in the order they appeared."""
    tally = Counter(window_texts)
    order = {t: i for i, t in reversed(list(enumerate(window_texts)))}
    ranked = sorted(tally, key=lambda t: (-tally[t], order[t]))
    out = []
    for t in ranked[:how_many]:
        shown = t if len(t) <= 80 else t[:77] + "..."
        out.append("%s (x%d)" % (shown, tally[t]) if tally[t] > 1 else shown)
    return out


def build_report(moments, messages, args, source):
    lines = [
        "Chat spike report for: %s" % os.path.basename(source),
        "%d messages over %s  |  %ds windows, spike = %.1fx the previous %d min"
        % (len(messages), hhmmss(messages[-1][0]), args.window, args.threshold,
           args.rolling // 60),
        "",
    ]
    if not moments:
        lines.append("No spikes found. Try a lower threshold, e.g. --threshold 2")
        return "\n".join(lines)

    order = "in VOD order" if args.chrono else "strongest first"
    lines.append("Top %d moments (%s):" % (len(moments), order))
    lines.append("")
    for n, m in enumerate(moments, 1):
        lines.append(
            "#%-2d START CLIP AT %s   (spike at %s, %.1f msgs/sec, %.1fx normal, ~%ds long)"
            % (n, hhmmss(m["clip_start"]), hhmmss(m["spike"]), m["msgs_per_sec"],
               m["ratio"], m["length"])
        )
        for s in m["samples"]:
            lines.append("      > " + s)
        lines.append("")
    if len(moments) < args.top:
        lines.append(
            "Only %d spikes passed %.1fx. Lower --threshold to see more."
            % (len(moments), args.threshold)
        )
    return "\n".join(lines)


def parse_args():
    p = argparse.ArgumentParser(description="Find clip-worthy chat spikes in a Twitch VOD.")
    p.add_argument("chat_json", nargs="?", help="chat JSON file from TwitchDownloader")
    p.add_argument("--window", type=int, default=WINDOW_SECONDS, help="window size in seconds")
    p.add_argument("--rolling", type=int, default=ROLLING_SECONDS, help="rolling average length in seconds")
    p.add_argument("--threshold", type=float, default=SPIKE_MULTIPLIER, help="spike multiplier (default 3)")
    p.add_argument("--pre-roll", type=int, default=PRE_ROLL_SECONDS, help="seconds before the spike to start the clip")
    p.add_argument("--top", type=int, default=TOP_N, help="number of moments to list")
    p.add_argument("--min-messages", type=int, default=MIN_MESSAGES, help="minimum messages in a spike window")
    p.add_argument("--merge-gap", type=int, default=MERGE_GAP_SECONDS, help="merge spikes closer than this many seconds")
    p.add_argument("--samples", type=int, default=SAMPLE_COUNT, help="chat messages shown per moment")
    p.add_argument("--hype-weight", type=float, default=HYPE_WEIGHT, help="strength of hype word bonus (0 = off)")
    p.add_argument("--chrono", action="store_true", help="list moments in VOD order instead of strongest first")
    p.add_argument("--output", help="where to save the report (default: next to the JSON)")
    return p.parse_args()


def main():
    # Windows consoles often can't print emoji; replace them instead of crashing.
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    args = parse_args()
    interactive = args.chat_json is None
    if interactive:
        print("Drag your chat JSON file onto this window, then press Enter:")
        args.chat_json = input("> ")
    path = args.chat_json.strip().strip('"').strip("'")

    try:
        if args.window <= 0:
            raise ValueError("--window must be greater than 0")
        messages = load_messages(path)
        if not messages:
            raise ValueError("The file has no chat messages in it.")
        moments = find_moments(messages, args)
        report = build_report(moments, messages, args, path)
        print(report)

        out_path = args.output or os.path.splitext(path)[0] + "_spikes.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print("\nSaved to: " + out_path)
        code = 0
    except FileNotFoundError:
        print("ERROR: file not found: " + path)
        code = 1
    except (ValueError, json.JSONDecodeError) as e:
        print("ERROR: %s" % e)
        code = 1

    if interactive:
        input("\nPress Enter to close...")
    return code


if __name__ == "__main__":
    sys.exit(main())
