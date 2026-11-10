"""Pure helpers: file names, timestamps, subtitle cues."""
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

Cue = tuple[float, float, str]  # (start_sec, end_sec, text)

NAME_RE = re.compile(r"^(?P<show>.+?)[\s._-]+S(?P<s>\d+)E(?P<e>\d+)", re.I)
CJK_RE = re.compile(r"[⺀-鿿가-힯＀-￯]+")
SRT_TIME =r"(\d+):(\d+):(\d+)[,.](\d+)"
SRT_RE = re.compile(SRT_TIME + r"\s*-->\s*" + SRT_TIME + r"[^\n]*\n(.*?)(?:\n\s*\n|\Z)", re.S)


def parse_name(path: Path) -> tuple[str, int, int] | None:
    m = NAME_RE.match(path.stem)
    if not m:
        return None
    show = re.sub(r"[._]+", " ", m["show"]).strip(" -")
    return show, int(m["s"]), int(m["e"])


def parse_srt(text: str) -> list[Cue]:
    text = text.replace("\r\n", "\n").lstrip("﻿")
    cues = []
    for m in SRT_RE.finditer(text):
        h1, m1, s1, ms1, h2, m2, s2, ms2, body = m.groups()
        start = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000
        end = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000
        cues.append((start, end, " ".join(body.split())))
    return cues


def to_srt(cues: list[Cue]) -> str:
    def t(sec):
        ms = round(sec * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    return "".join(f"{i}\n{t(s)} --> {t(e)}\n{txt}\n\n" for i, (s, e, txt) in enumerate(cues, 1))


def merge_ocr(samples: list[tuple[float, str]], step: float) -> list[Cue]:
    """Join consecutive OCR reads of the same subtitle into one cue.

    OCR reads one subtitle slightly differently on each frame, so similar
    neighbours (ratio >= 0.8) merge and the most common variant wins.
    """
    cues, run = [], []

    def flush():
        if run:
            text = Counter(t for _, t in run).most_common(1)[0][0]
            cues.append((run[0][0], run[-1][0] + step, text))
            run.clear()

    for t, text in samples:
        # the OCR model reads Korean on-screen captions as random CJK characters: drop them
        text = " ".join(CJK_RE.sub(" ", text).split())
        if run and (not text or SequenceMatcher(None, run[-1][1], text).ratio() < 0.8):
            flush()
        if len(text) >= 2:
            run.append((t, text))
    flush()
    return cues


def fmt_ts(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600:02}:{s // 60 % 60:02}:{s % 60:02}"


def parse_ts(s: str) -> float:
    total = 0.0
    for part in s.strip().split(":"):
        total = total * 60 + float(part)
    return total


def clip_window(start: float, end: float, length: float, duration: float) -> tuple[float, float]:
    """A window of exactly `length` seconds, centred on the moment, inside the video."""
    s = max(0.0, min((start + end - length) / 2, duration - length))
    return s, min(s + length, duration)


def text_between(cues: list[Cue], start: float, end: float) -> str:
    return "\n".join(t for s, e, t in cues if e > start and s < end)
