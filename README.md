# yt_summarize

Fetch a YouTube video's transcript and, optionally, summarize it with Claude.

```bash
pip install -r requirements.txt

# Save the transcript to <video_id>.txt
python yt_summarize.py https://youtu.be/R9momwXV9w4

# Fetch and summarize (needs ANTHROPIC_API_KEY)
python yt_summarize.py https://youtu.be/R9momwXV9w4 --summarize

# Summarize a transcript you already have
python yt_summarize.py --transcript-file transcript.txt --summarize
```

The script tries `youtube-transcript-api` first and falls back to `yt-dlp`
captions. Use `--lang` to change the caption languages, `--model` to change
the Claude model (default `claude-opus-5`), and `-o` to set the output path.

YouTube often blocks transcript requests from cloud and datacenter IPs
("IpBlocked" / "Sign in to confirm you're not a bot"). If that happens, run
the script from a home connection.

## Bulk transcripts: `yt_bulk.py`

Download transcripts for a whole channel, a set of search results, or a list
of IDs. Output is one `<video_id>.txt` per video plus an `index.tsv`. Re-runs
skip anything already downloaded.

```bash
# Every Knees Over Toes Guy upload and short, plus his guest appearances (85 videos)
python yt_bulk.py --ids-file kotg/videos.tsv -o kotg/transcripts

# Or discover videos live
python yt_bulk.py --channel @thekneesovertoesguy -o kotg/transcripts
python yt_bulk.py --search "Ben Patrick kneesovertoesguy podcast" --min-duration 900 \
    --exclude-channel "The Kneesovertoesguy" -o kotg/transcripts
```

`kotg/videos.tsv` lists his 44 channel uploads (videos and shorts) and 41
long-form guest appearances found via search in November 2026.
