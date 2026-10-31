# clip-miner

Finds the key moments (betrayal, conflict, puzzle solved, ...) in reality show episodes,
cuts each one into a clip, and lists them in an Excel file.

```
video ──► transcript ──► claude -p ──► key moments ──► ffmpeg clips + key_moments.xlsx
          (.srt, or OCR of           (text only,
           burned-in subtitles)      your subscription)
```

Only the key-moment step uses an LLM. Everything else runs locally and costs nothing.

## Requirements

- Python 3.10+
- `ffmpeg` on the PATH
- [Claude Code](https://claude.com/claude-code) (`claude`), logged in with your Claude subscription
- Optional: an NVIDIA GPU for fast OCR (about 6 min per 1-hour episode; CPU is about 10x slower)

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # no NVIDIA GPU: see the note in requirements.txt
cp .env.example .env                        # then set INPUT_DIR and OUTPUT_DIR
claude                                      # once, then /login with your subscription account
```

## Run

```bash
.venv/bin/python -m clipminer                    # all videos in INPUT_DIR
.venv/bin/python -m clipminer --only '*S01E08*'  # some of them
.venv/bin/python -m pytest                       # unit tests
```

File names must contain the season and episode: `The.Devil's.Plan.S01E08.mp4`.
If a `.srt` with the same name sits next to the video (`The.Devil's.Plan.S01E08.en.srt`)
and `USE_SRT=1`, it replaces OCR.

## Output (`OUTPUT_DIR`)

| Path | Content |
|---|---|
| `key_moments.xlsx` | One row per moment: Show, Season, Episode, Start, End, Category, Title, Transcript, Reason, Confidence, Clip |
| `clips/<Show>/S01E08/*.mp4` | One clip per moment |
| `work/<video>/transcript.srt` | Cached transcript (from OCR or the .srt) |
| `work/<video>/moments.json` | Cached Claude answer |

The batch can stop and restart at any time. An episode already in the Excel file is skipped.
The caches mean a rerun never repeats OCR or a Claude call.
To redo one episode: delete its rows in Excel, and delete `work/<video>/` for a fresh transcript
or only `moments.json` for a fresh Claude answer.

## Tune the results

Edit `prompt.md`: the categories, how many moments, how long a clip is.
Then delete `moments.json` of an episode and run again.

## Cost

One `claude -p` call per episode, text only: about 20,000-30,000 tokens for a one-hour episode.
It counts against your subscription usage limits, not an API bill:
the script removes `ANTHROPIC_API_KEY` from the environment of the `claude` call on purpose.
If the usage limit stops a batch, run it again after the limit resets.
