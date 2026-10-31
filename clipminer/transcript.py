"""Get the dialogue of an episode: from a .srt file, or by OCR of burned-in subtitles."""
import subprocess
from pathlib import Path

import numpy as np

from .core import Cue, merge_ocr, parse_srt, to_srt

W, H = 960, 135  # bottom quarter of a 16:9 frame, scaled down


def find_srt(video: Path) -> Path | None:
    # matches "Show.S01E08.srt" and "Show.S01E08.en.srt"
    return next(iter(sorted(video.parent.glob(f"{glob_escape(video.stem)}*.srt"))), None)


def glob_escape(s: str) -> str:
    return "".join(f"[{c}]" if c in "*?[" else c for c in s)


def ocr_video(video: Path, fps: float, use_cuda: bool) -> list[Cue]:
    if use_cuda:
        import onnxruntime
        onnxruntime.preload_dlls()  # CUDA/cuDNN from the nvidia-* pip wheels
    from rapidocr import RapidOCR
    ocr = RapidOCR(params={
        "EngineConfig.onnxruntime.use_cuda": use_cuda,
        "Global.log_level": "error",
        "Global.use_cls": False,  # subtitles are never rotated
        # default "min 736" upscales the 135 px strip to ~5000x736: 5x slower, no better
        "Det.limit_type": "max",
        "Det.limit_side_len": W,
    })

    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(video), "-an", "-sn",
         "-vf", f"fps={fps},crop=iw:ih/4:0:ih*3/4,scale={W}:{H},format=gray",
         "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE,
    )
    samples, prev_mask, prev_text, i = [], None, "", 0
    while chunk := proc.stdout.read(W * H):
        if len(chunk) < W * H:
            break
        frame = np.frombuffer(chunk, np.uint8).reshape(H, W)
        mask = frame > 200  # subtitle text is white
        # ponytail: OCR only when the bright pixels change; misses a subtitle change
        # that keeps <1% of pixels different (rare, adjacent near-identical lines)
        if prev_mask is None or (mask ^ prev_mask).mean() > 0.01:
            prev_mask = mask
            prev_text = " ".join(ocr(np.dstack([frame] * 3)).txts or ()) if mask.any() else ""
        samples.append((i / fps, prev_text))
        i += 1
        if i % (fps * 300) == 0:
            print(f"    OCR {i / fps / 60:.0f} min")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on {video}")
    return merge_ocr(samples, 1 / fps)


def get_cues(video: Path, work_dir: Path, use_srt: bool, fps: float, use_cuda: bool) -> list[Cue]:
    cache = work_dir / "transcript.srt"
    if cache.exists():
        return parse_srt(cache.read_text(encoding="utf-8"))
    srt = find_srt(video) if use_srt else None
    if srt:
        print(f"    transcript: {srt.name}")
        cues = parse_srt(srt.read_text(encoding="utf-8-sig", errors="replace"))
    else:
        print(f"    transcript: OCR at {fps} fps ({'GPU' if use_cuda else 'CPU'})")
        cues = ocr_video(video, fps, use_cuda)
    work_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(to_srt(cues), encoding="utf-8")
    return cues
