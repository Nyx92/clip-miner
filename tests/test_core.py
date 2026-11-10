from pathlib import Path

from clipminer.core import clip_window, fmt_ts, merge_ocr, parse_name, parse_srt, parse_ts, text_between


def test_parse_name():
    assert parse_name(Path("The.Devil's.Plan.S01E08.mp4")) == ("The Devil's Plan", 1, 8)
    assert parse_name(Path("Running Man - s12e345.mkv")) == ("Running Man", 12, 345)
    assert parse_name(Path("random_video.mp4")) is None


def test_parse_srt():
    srt = (
        "1\r\n00:00:13,263 --> 00:00:14,431\r\nMy hunch was right!\r\n\r\n"
        "2\r\n00:00:16,641 --> 00:00:19,602\r\nHow did you know\r\nthere would be a secret?\r\n"
    )
    assert parse_srt(srt) == [
        (13.263, 14.431, "My hunch was right!"),
        (16.641, 19.602, "How did you know there would be a secret?"),
    ]


def test_merge_ocr_merges_noisy_reads():
    samples = [
        (10.0, "I already know how to solve this."),
        (10.5, "Ialready know how to solve this."),
        (11.0, "I already know how to solve this."),
        (11.5, ""),
        (12.0, "叫 This or that?"),
        (12.5, "叫对 互左对"),  # Korean caption misread as CJK noise: dropped
    ]
    assert merge_ocr(samples, step=0.5) == [
        (10.0, 11.5, "I already know how to solve this."),
        (12.0, 12.5, "This or that?"),
    ]


def test_timestamps():
    assert fmt_ts(3723.4) == "01:02:03"
    assert parse_ts("01:02:03") == 3723
    assert parse_ts("02:03") == 123


def test_text_between():
    cues = [(1, 2, "a"), (5, 6, "b"), (9, 10, "c")]
    assert text_between(cues, 4, 9.5) == "b\nc"


def test_clip_window():
    assert clip_window(100, 140, 60, 3600) == (90, 150)    # short moment: grows around the middle
    assert clip_window(100, 300, 60, 3600) == (170, 230)   # long moment: middle part
    assert clip_window(5, 15, 60, 3600) == (0, 60)         # never before the video starts
    assert clip_window(3580, 3595, 60, 3600) == (3540, 3600)  # never after the video ends
    assert clip_window(10, 20, 60, 40) == (0, 40)          # video shorter than a clip
