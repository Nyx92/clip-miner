# Clip Miner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A batch script that finds key moments (betrayal, conflict, puzzle solved, ...) in Korean reality show episodes, cuts each moment into a clip, and records it in an Excel file.

**Architecture:** Local scripts do all mechanical work for free: transcript (from a `.srt` file, or OCR of the burned-in subtitles on the GPU), clip cutting (`ffmpeg`), and Excel (`openpyxl`). Only the key moment step uses an LLM: one `claude -p` call per episode, on the user's Claude subscription, with a text-only transcript (about 20-30k tokens).

**Tech Stack:** Python 3.10, ffmpeg, rapidocr + onnxruntime-gpu, openpyxl, python-dotenv, Claude Code CLI (`claude -p`), pytest.

**Spec:** Agreed in conversation on 2026-10-31; summary below and in `README.md`.

## Global Constraints

- All settings come from environment variables (`.env`, template in `.env.example`). No machine paths in code.
- `ANTHROPIC_API_KEY` is removed from the environment of the `claude` subprocess, so the call uses the subscription login and never bills an API account by accident.
- Text only goes to the LLM. No frames.
- The LLM returns times and reasons only. The script fills the transcript column from its own cues (exact text, fewer output tokens).
- A run is resumable: an episode already in the Excel file is skipped; transcript and LLM output are cached per episode.
- Use the `.srt` next to the video when present and `USE_SRT=1`; otherwise OCR.
- File name format: `<Show.Name>.S<nn>E<nn>.<ext>`, for example `The.Devil's.Plan.S01E08.mp4`.

## Review Focus

1. A file name with no `SxxEyy` part: skip it with a clear message, do not crash the batch.
2. The `claude` call fails (usage limit, not logged in): stop the batch with the CLI's message; a rerun continues where it stopped.
3. The Excel file is open in Excel on Windows: saving fails; report it clearly.
4. A moment near the start or end of the video: padding must not make a negative start time.
5. OCR noise (the same subtitle read slightly differently on each frame) must merge into one cue.

---

### Task 1: Pure logic with tests

**Files:** Create `clipminer/core.py`, `tests/test_core.py`

**Interfaces (Produces):**
- `parse_name(path: Path) -> tuple[str, int, int] | None` (show with dots as spaces, season, episode)
- `parse_srt(text: str) -> list[Cue]` where `Cue = (start: float, end: float, text: str)`
- `merge_ocr(samples: list[tuple[float, str]], step: float) -> list[Cue]` (consecutive similar texts, `difflib` ratio >= 0.8, become one cue; the most common variant wins; empty text ends a cue)
- `fmt_ts(sec: float) -> str` (`HH:MM:SS`), `parse_ts(s: str) -> float`
- `text_between(cues, start, end) -> str`

- [ ] Write tests: `parse_name` on the real file name gives `("The Devil's Plan", 1, 8)`; no match gives `None`; `parse_srt` on a 2-cue sample with a 2-line cue; `merge_ocr` merges `"Ialready know"` and `"I already know"`; `fmt_ts(3723.4) == "01:02:03"`.
- [ ] Run `pytest` and see failures. Implement. Run `pytest` and see passes. Commit.

### Task 2: Transcript (OCR and `.srt`)

**Files:** Create `clipminer/transcript.py`

- `ocr_video(video: Path, fps: float, use_cuda: bool) -> list[Cue]`: ffmpeg pipes the bottom quarter of the frame, gray, 960 px wide, at `fps`. OCR runs only when the mask of bright pixels (> 200) changes by more than 1 %. Then `merge_ocr`.
- `get_cues(video, work_dir, cfg) -> list[Cue]`: use the `.srt` (same stem, any `.srt` suffix such as `.en.srt`) when `USE_SRT=1`, else OCR. Cache to `work_dir/transcript.srt`.
- Check: run on the sample episode, compare the first 2 minutes with the spike output.

### Task 3: Key moments with `claude -p`

**Files:** Create `clipminer/moments.py`, `prompt.md`

- `find_moments(cues, meta, cfg) -> list[dict]`: build the timeline (`[HH:MM:SS-HH:MM:SS] text` per cue), send `prompt.md` + timeline on stdin to `claude -p --model $CLAUDE_MODEL --tools "" --system-prompt ... --setting-sources "" --strict-mcp-config --no-session-persistence --output-format json --json-schema <schema>`. Return `structured_output["moments"]`. Raise on non-zero exit or `is_error`. Cache to `work_dir/moments.json`.
- Schema fields per moment: `start`, `end` (`HH:MM:SS`), `category`, `title`, `reason`, `confidence` (1-5).

### Task 4: Clips, Excel, batch CLI

**Files:** Create `clipminer/__main__.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`

- `cut_clip(video, start, end, out, pad)`: `ffmpeg -ss max(0,start-pad) -i video -t ... -c:v libx264 -preset veryfast -crf 20 -c:a aac`.
- Excel at `$OUTPUT_DIR/key_moments.xlsx`, columns: Show, Season, Episode, Start, End, Category, Title, Transcript, Reason, Confidence, Clip. Save after each episode.
- `python -m clipminer [--only GLOB]` loops over videos in `$INPUT_DIR`.
- Check: full run on `The.Devil's.Plan.S01E08.mp4` with `USE_SRT=0`, then open the Excel file and play two clips.
