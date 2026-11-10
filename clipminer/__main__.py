"""Batch: python -m clipminer [--only GLOB]"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font

from .core import clip_window, fmt_ts, parse_name, parse_ts, text_between
from .moments import find_moments
from .transcript import get_cues

VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm"}
COLUMNS = ["Show", "Season", "Episode", "Start", "End", "Category", "Title",
           "Transcript", "Reason", "Confidence", "Clip"]
WIDTHS = [22, 8, 8, 10, 10, 16, 36, 70, 60, 11, 50]


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        sys.exit(f"Missing setting {name}. Copy .env.example to .env and fill it in.")
    return value


def open_sheet(path: Path):
    if path.exists():
        wb = load_workbook(path)
        return wb, wb.active
    wb = Workbook()
    ws = wb.active
    ws.title = "Key moments"
    ws.append(COLUMNS)
    for cell, width in zip(ws[1], WIDTHS):
        cell.font = Font(bold=True)
        ws.column_dimensions[cell.column_letter].width = width
    ws.freeze_panes = "A2"
    return wb, ws


def save(wb, path: Path):
    try:
        wb.save(path)
    except PermissionError:
        sys.exit(f"Cannot write {path}. Close it in Excel, then run again (finished work is cached).")


def cut_clip(video: Path, start: float, end: float, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", str(video),
         "-t", f"{end - start:.2f}", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", str(out)],
        check=True,
    )


def video_duration(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:40]


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description="Find key moments, cut clips, update Excel.")
    ap.add_argument("--only", default="*", help="glob filter on video file names, e.g. '*S01E08*'")
    args = ap.parse_args()

    input_dir = Path(env("INPUT_DIR"))
    output_dir = Path(env("OUTPUT_DIR"))
    use_srt = env("USE_SRT", "1") == "1"
    fps = float(env("OCR_FPS", "2"))
    use_cuda = env("OCR_USE_CUDA", "1") == "1"
    length = float(env("CLIP_LENGTH_SEC", "60"))
    if not (math.isfinite(length) and length > 0):
        sys.exit("CLIP_LENGTH_SEC must be more than 0.")
    model = env("CLAUDE_MODEL", "sonnet")
    claude_bin = env("CLAUDE_BIN", "claude")
    prompt_file = Path(env("PROMPT_FILE", str(Path(__file__).resolve().parent.parent / "prompt.md")))

    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx = output_dir / "key_moments.xlsx"
    wb, ws = open_sheet(xlsx)
    done = {(r[0], r[1], r[2]) for r in ws.iter_rows(min_row=2, max_col=3, values_only=True)}

    videos = sorted(p for p in input_dir.glob(args.only) if p.suffix.lower() in VIDEO_EXT)
    if not videos:
        sys.exit(f"No videos match {args.only!r} in {input_dir}")
    for video in videos:
        meta = parse_name(video)
        if not meta:
            print(f"SKIP {video.name}: name has no SxxEyy part")
            continue
        show, season, episode = meta
        if meta in done:
            print(f"DONE {video.name} (already in Excel)")
            continue
        print(f"==> {video.name}")
        work = output_dir / "work" / video.stem
        cues = get_cues(video, work, use_srt, fps, use_cuda)
        print(f"    {len(cues)} subtitle cues")

        # Claude picks moments for one clip length, so each length has its own cache
        cache = work / f"moments_{length:g}s.json"
        if cache.exists():
            moments = json.loads(cache.read_text(encoding="utf-8"))
        else:
            print(f"    asking Claude ({model})...")
            moments, stats = find_moments(cues, show, season, episode, prompt_file, claude_bin, model, length)
            print(f"    {len(moments)} moments, {stats['input_tokens']} tokens in, "
                  f"{stats['output_tokens']} out, {stats['seconds']} s")
            cache.write_text(json.dumps(moments, indent=2, ensure_ascii=False), encoding="utf-8")

        duration = video_duration(video)
        clip_dir = output_dir / "clips" / slug(show) / f"S{season:02}E{episode:02}"
        for n, m in enumerate(moments, 1):
            start, end = parse_ts(m["start"]), parse_ts(m["end"])
            if end <= start:
                print(f"    skip moment {n}: end {m['end']} is not after start {m['start']}")
                continue
            start, end = clip_window(start, end, length, duration)
            # length in the name: a new CLIP_LENGTH_SEC never reuses an old clip
            clip = clip_dir / f"{n:02}_{slug(m['category'])}_{fmt_ts(start).replace(':', '')}_{length:g}s.mp4"
            if not clip.exists():
                cut_clip(video, start, end, clip)
            ws.append([show, season, episode, fmt_ts(start), fmt_ts(end), m["category"], m["title"],
                       text_between(cues, start, end), m["reason"], m["confidence"],
                       str(clip.relative_to(output_dir))])
            for cell in ws[ws.max_row]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        save(wb, xlsx)
        print(f"    saved {len(moments)} rows to {xlsx}")


if __name__ == "__main__":
    main()
