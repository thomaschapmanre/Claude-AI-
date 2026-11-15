#!/usr/bin/env python3
"""
Make Clips - paste a Twitch VOD link, get video clips of the best moments.

What it does, start to finish:
  1. Asks for the VOD link.
  2. Downloads the helper tools the first time (TwitchDownloaderCLI + FFmpeg).
  3. Downloads the VOD's chat.
  4. Finds the moments where chat blew up (3x+ normal, hype words count extra).
  5. Downloads a video clip of each moment, starting 20 seconds early.
  6. Opens the folder with your clips.

Easiest way to run it on Windows: double-click "Make Clips.bat".
Standard library only. Needs Python 3.8 or newer.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from collections import Counter

# --------------------------------------------------------------------------
# Settings you can change
# --------------------------------------------------------------------------
HOW_MANY_CLIPS = 20        # clips to make (the strongest moments)
SECONDS_BEFORE = 20        # start each clip this long before the spike
SECONDS_AFTER = 40         # keep recording this long after the spike starts
MAX_CLIP_SECONDS = 120     # never make a clip longer than this
SPIKE_MULTIPLIER = 3.0     # a spike is this many times normal chat speed
WINDOW_SECONDS = 10        # chat is counted in windows of this size
ROLLING_SECONDS = 300      # "normal" = the 5 minutes before each window
MIN_MESSAGES = 5           # ignore windows with fewer messages than this

# A message containing one of these counts as (1 + bonus) messages.
HYPE_WORDS = {"kekw": 1.0, "lul": 1.0, "omegalul": 1.5, "w": 0.5}
HYPE_PREFIXES = {"pog": 1.0}                      # Pog, PogChamp, POGGERS...
HYPE_PHRASES = {"clip it": 2.0, "no way": 1.0}
# --------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "clip_tools")
IS_WINDOWS = os.name == "nt"
CLI_NAME = "TwitchDownloaderCLI.exe" if IS_WINDOWS else "TwitchDownloaderCLI"
FFMPEG_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
RELEASES_API = "https://api.github.com/repos/lay295/TwitchDownloader/releases/latest"
RELEASES_PAGE = "https://github.com/lay295/TwitchDownloader/releases/latest"
WORD_RE = re.compile(r"[a-z0-9']+")


class Problem(Exception):
    """An error with a message meant for the person running the script."""


def say(text=""):
    print(text, flush=True)


def hhmmss(seconds):
    seconds = int(max(0, seconds))
    return "%d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


# ---------- step 1: the link ----------

def vod_id_from(text):
    text = text.strip().strip('"').strip("'")
    match = re.search(r"videos/(\d+)", text) or re.fullmatch(r"v?(\d+)", text)
    return match.group(1) if match else None


def ask_for_vod():
    if len(sys.argv) > 1:
        vod = vod_id_from(sys.argv[1])
        if not vod:
            raise Problem("That doesn't look like a VOD link: " + sys.argv[1])
        return vod
    while True:
        say("Paste the Twitch VOD link here, then press Enter.")
        say("(It looks like https://www.twitch.tv/videos/123456789)")
        vod = vod_id_from(input("> "))
        if vod:
            return vod
        say("\nThat doesn't look like a VOD link. Try again.\n")


# ---------- step 2: helper tools ----------

def download(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": "clip-maker"})
    with urllib.request.urlopen(request, timeout=60) as response, open(dest, "wb") as out:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)


def get_tools():
    """Return (cli_path, ffmpeg_path), downloading them on the first run."""
    os.makedirs(TOOLS, exist_ok=True)
    cli = os.environ.get("CLIP_CLI") or os.path.join(TOOLS, CLI_NAME)
    ffmpeg = os.path.join(TOOLS, FFMPEG_NAME)

    if not os.path.exists(cli):
        if not IS_WINDOWS:
            raise Problem(
                "Automatic setup only works on Windows. Download TwitchDownloaderCLI from\n"
                "%s and put it in:\n%s" % (RELEASES_PAGE, TOOLS)
            )
        say("First run: downloading TwitchDownloaderCLI (one time only)...")
        manual = (
            "Couldn't download TwitchDownloaderCLI automatically.\n"
            "Do it by hand instead:\n"
            "  1. Open %s\n"
            "  2. Download the file with CLI and Windows-x64 in its name\n"
            "  3. Open the zip and copy TwitchDownloaderCLI.exe into:\n     %s\n"
            "  4. Run this again." % (RELEASES_PAGE, TOOLS)
        )
        try:
            request = urllib.request.Request(RELEASES_API, headers={"User-Agent": "clip-maker"})
            with urllib.request.urlopen(request, timeout=60) as response:
                release = json.load(response)
            wanted = [
                a["browser_download_url"] for a in release.get("assets", [])
                if "cli" in a["name"].lower() and "windows-x64" in a["name"].lower()
                and a["name"].lower().endswith(".zip")
            ]
            if not wanted:
                raise Problem(manual)
            zip_path = os.path.join(TOOLS, "cli.zip")
            download(wanted[0], zip_path)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(TOOLS)
            os.remove(zip_path)
        except Problem:
            raise
        except Exception as error:
            raise Problem(manual + "\n\n(Details: %s)" % error)
        if not os.path.exists(cli):
            raise Problem(manual)

    if not os.path.exists(ffmpeg):
        say("First run: downloading FFmpeg (one time only)...")
        subprocess.run([cli, "ffmpeg", "--download"], cwd=TOOLS)
        if not os.path.exists(ffmpeg):
            raise Problem(
                "FFmpeg didn't download. Check your internet connection and run this again."
            )
    return cli, ffmpeg


# ---------- step 3: chat ----------

def download_chat(cli, vod, chat_path):
    if os.path.exists(chat_path) and os.path.getsize(chat_path) > 0:
        say("Chat already downloaded, reusing it.")
        return
    say("Downloading chat (long streams can take a few minutes)...")
    code = subprocess.run(
        [cli, "chatdownload", "--id", vod, "-o", chat_path, "--collision", "Overwrite"],
        cwd=TOOLS,
    ).returncode
    if code != 0 or not os.path.exists(chat_path):
        raise Problem(
            "Couldn't download the chat for that VOD.\n"
            "Check the link is right and the VOD still exists. Subscriber-only\n"
            "and deleted VODs can't be downloaded."
        )


def load_chat(chat_path):
    with open(chat_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    comments = data.get("comments") if isinstance(data, dict) else None
    if not isinstance(comments, list):
        raise Problem("The chat file doesn't look right. Delete the clips folder and try again.")
    messages = []
    for c in comments:
        if not isinstance(c, dict):
            continue
        offset = c.get("content_offset_seconds")
        if not isinstance(offset, (int, float)):
            continue
        msg = c.get("message")
        body = msg.get("body") if isinstance(msg, dict) else None
        messages.append((float(offset), body.strip() if isinstance(body, str) else ""))
    messages.sort(key=lambda m: m[0])
    if not messages:
        raise Problem("That VOD has no chat messages, so there's nothing to find.")
    video = data.get("video") if isinstance(data.get("video"), dict) else {}
    end = video.get("end")
    vod_length = float(end) if isinstance(end, (int, float)) and end > 0 else messages[-1][0]
    return messages, max(vod_length, messages[-1][0])


# ---------- step 4: find the moments ----------

def hype_bonus(text):
    lowered = text.lower()
    best = 0.0
    for word in WORD_RE.findall(lowered):
        best = max(best, HYPE_WORDS.get(word, 0.0))
        for prefix, bonus in HYPE_PREFIXES.items():
            if word.startswith(prefix):
                best = max(best, bonus)
    normalized = " ".join(lowered.split())
    for phrase, bonus in HYPE_PHRASES.items():
        if phrase in normalized:
            best = max(best, bonus)
    return best


def find_moments(messages):
    window = WINDOW_SECONDS
    n = int(messages[-1][0] // window) + 1
    counts = [0] * n
    scores = [0.0] * n
    texts = [[] for _ in range(n)]
    for offset, text in messages:
        i = max(0, int(offset // window))
        counts[i] += 1
        scores[i] += 1.0 + hype_bonus(text)
        if text:
            texts[i].append(text)

    mean = sum(scores) / n
    floor = max(1.0, mean * 0.5)
    lookback = max(1, ROLLING_SECONDS // window)
    prefix = [0.0]
    for s in scores:
        prefix.append(prefix[-1] + s)

    ratios = []
    for i in range(n):
        lo = max(0, i - lookback)
        baseline = (prefix[i] - prefix[lo]) / (i - lo) if i - lo >= 3 else mean
        ratios.append(scores[i] / max(baseline, floor))

    groups = []
    max_gap = 20 // window + 1
    for i in range(n):
        if ratios[i] >= SPIKE_MULTIPLIER and counts[i] >= MIN_MESSAGES:
            if groups and i - groups[-1][-1] <= max_gap:
                groups[-1].append(i)
            else:
                groups.append([i])

    moments = []
    for group in groups:
        peak = max(group, key=lambda i: scores[i])
        tally = Counter(texts[peak])
        moments.append({
            "spike": group[0] * window,
            "length": (group[-1] - group[0] + 1) * window,
            "per_sec": counts[peak] / window,
            "ratio": max(ratios[i] for i in group),
            "samples": [
                (t if len(t) <= 80 else t[:77] + "...") + (" (x%d)" % c if c > 1 else "")
                for t, c in tally.most_common(5)
            ],
        })
    moments.sort(key=lambda m: m["ratio"], reverse=True)
    return moments[:HOW_MANY_CLIPS]


# ---------- step 5: clips ----------

def make_clips(cli, ffmpeg, vod, moments, vod_length, folder):
    made = 0
    lines = []
    for number, m in enumerate(moments, 1):
        start = max(0, m["spike"] - SECONDS_BEFORE)
        length = min(MAX_CLIP_SECONDS, SECONDS_BEFORE + max(SECONDS_AFTER, m["length"] + 15))
        end = min(start + length, vod_length)
        stamp = hhmmss(start)
        name = "clip_%02d_at_%s.mp4" % (number, stamp.replace(":", "-"))
        out = os.path.join(folder, name)

        lines.append("#%d  %s  starts at %s  (spike at %s, %.1f msgs/sec, %.1fx normal)"
                     % (number, name, stamp, hhmmss(m["spike"]), m["per_sec"], m["ratio"]))
        lines.append("    https://www.twitch.tv/videos/%s?t=%dh%dm%ds"
                     % (vod, start // 3600, start % 3600 // 60, start % 60))
        for s in m["samples"]:
            lines.append("      > " + s)
        lines.append("")

        say("\nClip %d of %d  (starts at %s, chat said: %s)"
            % (number, len(moments), stamp, m["samples"][0] if m["samples"] else "?"))
        if end - start < 1:
            say("  Skipped: too close to the end of the VOD.")
            continue
        if os.path.exists(out) and os.path.getsize(out) > 0:
            say("  Already made, skipping.")
            made += 1
            continue
        code = subprocess.run(
            [cli, "videodownload", "--id", vod, "-b", hhmmss(start), "-e", hhmmss(end),
             "-o", out, "--ffmpeg-path", ffmpeg, "--collision", "Overwrite"],
            cwd=TOOLS,
        ).returncode
        if code == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
            made += 1
        else:
            say("  This clip failed to download. Moving on.")

    with open(os.path.join(folder, "moments.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return made


# ---------- putting it together ----------

def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    say("=" * 50)
    say("  MAKE CLIPS - best chat moments from a Twitch VOD")
    say("=" * 50)
    say()

    vod = ask_for_vod()
    cli, ffmpeg = get_tools()

    folder = os.path.join(HERE, "clips_" + vod)
    os.makedirs(folder, exist_ok=True)
    chat_path = os.path.join(folder, "chat.json")

    download_chat(cli, vod, chat_path)
    messages, vod_length = load_chat(chat_path)
    say("Read %d chat messages over %s." % (len(messages), hhmmss(vod_length)))

    moments = find_moments(messages)
    if not moments:
        raise Problem(
            "Chat never spiked to %.0fx normal in this VOD, so no clips were made.\n"
            "To be less picky, open make_clips.py in Notepad and change\n"
            "SPIKE_MULTIPLIER = 3.0 to 2.0, then run this again." % SPIKE_MULTIPLIER
        )
    say("Found %d moments. Downloading the clips now..." % len(moments))

    made = make_clips(cli, ffmpeg, vod, moments, vod_length, folder)
    say()
    say("=" * 50)
    say("  DONE: %d of %d clips made." % (made, len(moments)))
    say("  They are in: " + folder)
    say("  moments.txt in that folder lists what chat said for each one.")
    say("=" * 50)
    if IS_WINDOWS:
        try:
            os.startfile(folder)
        except OSError:
            pass
    return 0 if made else 1


if __name__ == "__main__":
    try:
        code = main()
    except Problem as problem:
        say("\nSOMETHING WENT WRONG:\n" + str(problem))
        code = 1
    except KeyboardInterrupt:
        say("\nStopped.")
        code = 1
    sys.exit(code)
