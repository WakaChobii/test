#!/usr/bin/env python3
"""Fetch a YouTube video's transcript and (optionally) summarize it with Claude.

Run this on your own machine. YouTube blocks transcript requests from most
cloud/datacenter IPs, but serves them normally to home connections.

Examples:
    python yt_summarize.py https://youtu.be/R9momwXV9w4
    python yt_summarize.py R9momwXV9w4 --summarize
    python yt_summarize.py --transcript-file R9momwXV9w4.txt --summarize
"""

import argparse
import re
import sys
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5"

SUMMARY_PROMPT = """Below is the transcript of a YouTube video{title_part}.

Write a clear summary for someone who hasn't watched it:
1. A 2-3 sentence overview of the video's main argument.
2. A section-by-section breakdown of the key points, in the order they come up.
   Keep the specific claims, numbers, benchmarks, names and examples the speaker gives.
3. The speaker's conclusions or predictions.

Auto-generated captions can mangle names and technical terms; correct obvious
errors from context, and don't invent details that aren't in the transcript.

<transcript>
{transcript}
</transcript>"""


def extract_video_id(url_or_id: str) -> str:
    """Accept a bare 11-char ID or any common YouTube URL form."""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})", url_or_id)
    if not m:
        sys.exit(f"Couldn't find a video ID in: {url_or_id}")
    return m.group(1)


def fetch_with_transcript_api(video_id: str, langs: list[str]) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi

    fetched = YouTubeTranscriptApi().fetch(video_id, languages=langs)
    return " ".join(s.text.replace("\n", " ") for s in fetched)


class _SilentLogger:
    """Keep yt-dlp from printing errors itself; get_transcript reports them."""

    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def fetch_with_ytdlp(video_id: str, langs: list[str]) -> tuple[str, str]:
    """Fallback: ask yt-dlp for the caption track list, then download json3 captions."""
    import json

    import yt_dlp

    opts = {"skip_download": True, "quiet": True, "no_warnings": True, "logger": _SilentLogger()}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        # Prefer human-made subtitles, then auto-captions; prefer the untranslated "-orig" track.
        for tracks in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
            for lang in langs:
                for key in (f"{lang}-orig", lang):
                    fmt = next((f for f in tracks.get(key, []) if f.get("ext") == "json3"), None)
                    if fmt:
                        data = json.loads(ydl.urlopen(fmt["url"]).read().decode())
                        text = " ".join(
                            seg.get("utf8", "")
                            for ev in data.get("events", [])
                            for seg in ev.get("segs") or []
                        )
                        return re.sub(r"\s+", " ", text).strip(), info.get("title", "")
    raise RuntimeError(f"no captions found for languages {langs}")


def get_title(video_id: str) -> str:
    """Best-effort title lookup via oEmbed (no API key needed)."""
    import json
    import urllib.request

    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r).get("title", "")
    except Exception:
        return ""


def _first_line(e: Exception) -> str:
    return next((line.strip() for line in str(e).splitlines() if line.strip()), "")


def get_transcript(video_id: str, langs: list[str]) -> tuple[str, str]:
    errors = []
    try:
        return fetch_with_transcript_api(video_id, langs), get_title(video_id)
    except Exception as e:
        errors.append(f"youtube-transcript-api: {e.__class__.__name__}: {_first_line(e)}")
    try:
        return fetch_with_ytdlp(video_id, langs)
    except Exception as e:
        errors.append(f"yt-dlp: {e.__class__.__name__}: {_first_line(e)}")
    sys.exit("Couldn't fetch a transcript:\n  " + "\n  ".join(errors))


def summarize(transcript: str, title: str, model: str) -> None:
    import anthropic

    client = anthropic.Anthropic()
    prompt = SUMMARY_PROMPT.format(
        title_part=f' titled "{title}"' if title else "", transcript=transcript
    )
    # Server-side fallback re-runs the request on another model if a safety
    # classifier declines it, instead of returning an empty refusal.
    with client.beta.messages.stream(
        model=model,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        final = stream.get_final_message()
    print()
    if final.stop_reason == "refusal":
        sys.exit("Claude declined to summarize this transcript.")
    if final.stop_reason == "max_tokens":
        print("[summary was cut off at max_tokens]", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video", nargs="?", help="YouTube URL or 11-character video ID")
    p.add_argument("--transcript-file", type=Path, help="summarize an existing transcript file instead of fetching")
    p.add_argument("--lang", default="en", help="comma-separated caption languages to try (default: en)")
    p.add_argument("-o", "--output", type=Path, help="where to save the transcript (default: <video_id>.txt)")
    p.add_argument("--summarize", action="store_true", help="summarize with Claude (needs ANTHROPIC_API_KEY)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model for --summarize (default: {DEFAULT_MODEL})")
    args = p.parse_args()

    if args.transcript_file:
        transcript, title = args.transcript_file.read_text(), ""
    elif args.video:
        video_id = extract_video_id(args.video)
        langs = [l.strip() for l in args.lang.split(",") if l.strip()]
        transcript, title = get_transcript(video_id, langs)
        out = args.output or Path(f"{video_id}.txt")
        out.write_text(transcript + "\n")
        print(f"Saved transcript ({len(transcript.split()):,} words) to {out}", file=sys.stderr)
        if title:
            print(f"Title: {title}", file=sys.stderr)
    else:
        p.error("give a video URL/ID or --transcript-file")

    if args.summarize:
        summarize(transcript, title, args.model)
    elif args.transcript_file:
        p.error("--transcript-file only makes sense with --summarize")


if __name__ == "__main__":
    main()
