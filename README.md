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

## Install

1. Get the code:
   ```bash
   git clone https://github.com/Nyx92/clip-miner.git
   cd clip-miner
   ```
2. Install `ffmpeg` (Ubuntu/WSL: `sudo apt install ffmpeg`).
3. Make a virtual environment and install the Python packages:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
   No NVIDIA GPU? Before this step, replace the GPU lines in `requirements.txt` with `onnxruntime`,
   and set `OCR_USE_CUDA=0` in `.env`.
4. Copy the settings file:
   ```bash
   cp .env.example .env
   ```
5. Log in to Claude Code once: run `claude`, then type `/login` and use your subscription account.

## Settings (`.env`)

| Setting | Meaning |
|---|---|
| `INPUT_DIR` | Folder with the episodes |
| `OUTPUT_DIR` | Folder for clips, `key_moments.xlsx` and the cache |
| `CLIP_MIN_SEC`, `CLIP_MAX_SEC` | Shortest and longest clip, in seconds. A shorter moment is extended and a longer one is trimmed, around its middle. Set both to the same value for clips of one fixed length |
| `USE_SRT` | `1` = use a `.srt` next to the video when there is one. `0` = always OCR |
| `OCR_FPS` | OCR samples per second |
| `OCR_USE_CUDA` | `1` = OCR on the NVIDIA GPU. `0` = CPU |
| `CLAUDE_BIN`, `CLAUDE_MODEL` | The `claude` command and the model it uses |
| `PROMPT_FILE` | Optional: your own rubric instead of `prompt.md` |

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
| `work/<video>/moments_<min>-<max>s.json` | Cached Claude answer, one per clip length range |

The batch can stop and restart at any time. An episode already in the Excel file is skipped.
The caches mean a rerun never repeats OCR or a Claude call.
To redo one episode: delete its rows in Excel, and delete `work/<video>/` for a fresh transcript
or only `moments_*.json` for a fresh Claude answer.

## Tune the results

Edit `prompt.md` to change the categories or how many moments. Change `CLIP_MIN_SEC` and `CLIP_MAX_SEC` for different clip lengths.
After a prompt change, delete `moments_*.json` of an episode and run again.
A new clip length range gets a new Claude answer automatically, because Claude chooses moments that fit the range.

## Cost

One `claude -p` call per episode, text only: about 20,000-30,000 tokens for a one-hour episode.
It counts against your subscription usage limits, not an API bill:
the script removes `ANTHROPIC_API_KEY` from the environment of the `claude` call on purpose.
If the usage limit stops a batch, run it again after the limit resets.
