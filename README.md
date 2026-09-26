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
