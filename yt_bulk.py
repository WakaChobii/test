#!/usr/bin/env python3
"""Bulk-download YouTube transcripts for whole channels, search results or ID lists.

Reuses the fetching logic from yt_summarize.py. Each transcript is saved as
<out>/<video_id>.txt with a small header, and <out>/index.tsv records every
video (id, channel, title, duration, status). Re-running skips videos that
already have a transcript, so an interrupted run can just be started again.

Run this from a home connection: YouTube blocks transcript requests from most
cloud/datacenter IPs.

Examples:
    # Everything on a channel (uploads + shorts)
    python yt_bulk.py --channel @thekneesovertoesguy -o kotg

    # Guest appearances: top search results longer than 15 minutes
    python yt_bulk.py --search "Ben Patrick kneesovertoesguy podcast" --min-duration 900 -o kotg

    # A list of IDs/URLs, one per line (e.g. kotg/videos.tsv, first column)
    python yt_bulk.py --ids-file kotg/videos.tsv -o kotg
"""

import argparse
import csv
import random
import sys
import time
from pathlib import Path

from yt_summarize import _SilentLogger, extract_video_id, get_transcript


def list_videos(url: str) -> list[dict]:
    """Flat-list a channel tab, playlist or ytsearch query with yt-dlp."""
    import yt_dlp

    opts = {"extract_flat": True, "quiet": True, "no_warnings": True, "ignoreerrors": True,
            "logger": _SilentLogger()}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    out = []
    for e in info.get("entries") or []:
        if not e:
            continue
        if e.get("_type") == "playlist":  # channel root returns tabs as nested playlists
            out.extend(list_videos(e["url"]))
        elif e.get("id"):
            out.append({
                "id": e["id"],
                "channel": e.get("channel") or info.get("channel") or "",
                "title": e.get("title") or "",
                "duration": int(e.get("duration") or 0),
            })
    return out


def channel_urls(handle: str) -> list[str]:
    base = handle if handle.startswith("http") else f"https://www.youtube.com/{handle.lstrip('/')}"
    base = base.rstrip("/")
    return [f"{base}/{tab}" for tab in ("videos", "shorts", "streams")]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--channel", action="append", default=[], help="channel handle or URL (repeatable)")
    p.add_argument("--search", action="append", default=[], help="YouTube search query (repeatable)")
    p.add_argument("--search-limit", type=int, default=30, help="results per search (default 30)")
    p.add_argument("--ids-file", type=Path, help="file with one video ID/URL per line (first tab-separated column)")
    p.add_argument("--min-duration", type=int, default=0, help="skip videos shorter than this many seconds")
    p.add_argument("--exclude-channel", action="append", default=[], help="skip search results from this channel name")
    p.add_argument("--lang", default="en", help="comma-separated caption languages (default: en)")
    p.add_argument("--delay", type=float, default=4.0, help="seconds to wait between videos (default 4)")
    p.add_argument("-o", "--out", type=Path, default=Path("transcripts"), help="output directory")
    args = p.parse_args()

    videos: dict[str, dict] = {}
    for ch in args.channel:
        for url in channel_urls(ch):
            for v in list_videos(url):
                videos.setdefault(v["id"], v)
    for q in args.search:
        for v in list_videos(f"ytsearch{args.search_limit}:{q}"):
            if v["channel"] not in args.exclude_channel:
                videos.setdefault(v["id"], v)
    if args.ids_file:
        for line in args.ids_file.read_text().splitlines():
            first = line.split("\t")[0].strip()
            if first and not first.startswith("#") and first != "id":
                vid = extract_video_id(first)
                videos.setdefault(vid, {"id": vid, "channel": "", "title": "", "duration": 0})
    if not videos:
        p.error("nothing to fetch: give --channel, --search or --ids-file")

    todo = [v for v in videos.values() if not v["duration"] or v["duration"] >= args.min_duration]
    args.out.mkdir(parents=True, exist_ok=True)
    langs = [l.strip() for l in args.lang.split(",") if l.strip()]
    print(f"{len(todo)} videos to process -> {args.out}/", file=sys.stderr)

    rows = []
    for i, v in enumerate(todo, 1):
        path = args.out / f"{v['id']}.txt"
        if path.exists():
            status = "ok (cached)"
        else:
            try:
                # get_transcript calls sys.exit on failure; catch it so one bad video doesn't stop the run.
                text, title = get_transcript(v["id"], langs)
                v["title"] = v["title"] or title
                header = f"# {v['title']}\n# channel: {v['channel']}\n# https://youtu.be/{v['id']}\n\n"
                path.write_text(header + text + "\n")
                status = "ok"
            except SystemExit as e:
                status = "failed: " + str(e).replace("\n", " ")[:200]
            time.sleep(args.delay + random.uniform(0, args.delay / 2))
        print(f"[{i}/{len(todo)}] {status[:60]:<60} {v['title'][:70]}", file=sys.stderr)
        rows.append([v["id"], v["channel"], v["title"], v["duration"], status])

    with open(args.out / "index.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["id", "channel", "title", "duration_s", "status"])
        w.writerows(rows)
    ok = sum(r[4].startswith("ok") for r in rows)
    print(f"Done: {ok}/{len(rows)} transcripts in {args.out}/ (index.tsv lists every video)", file=sys.stderr)


if __name__ == "__main__":
    main()
