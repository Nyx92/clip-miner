"""Find key moments with one `claude -p` call per episode (Claude subscription)."""
import json
import os
import subprocess
from pathlib import Path

from .core import Cue, fmt_ts

SCHEMA = {
    "type": "object",
    "properties": {
        "moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "HH:MM:SS"},
                    "end": {"type": "string", "description": "HH:MM:SS"},
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["start", "end", "category", "title", "reason", "confidence"],
            },
        }
    },
    "required": ["moments"],
}


def find_moments(cues: list[Cue], show: str, season: int, episode: int,
                 prompt_file: Path, claude_bin: str, model: str,
                 lo: float, hi: float) -> tuple[list[dict], dict]:
    timeline = "\n".join(f"[{fmt_ts(s)}] {t}" for s, _, t in cues)
    stdin = (
        f"{prompt_file.read_text(encoding='utf-8')}\n\n"
        f"# Clip length\nEvery clip is {lo:g} to {hi:g} seconds. A shorter moment is extended and a longer one "
        f"is trimmed, both around its middle. Choose moments whose key part fits in {hi:g} seconds.\n\n"
        f"# Episode\nShow: {show}\nSeason: {season}\nEpisode: {episode}\n\n"
        f"# Transcript\n{timeline}\n"
    )
    # Without ANTHROPIC_API_KEY the CLI uses the subscription login, never API billing.
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(
        [claude_bin, "-p", "--model", model, "--tools", "",
         "--system-prompt", "You are a video editor who finds key moments in reality show transcripts.",
         "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
         "--output-format", "json", "--json-schema", json.dumps(SCHEMA)],
        input=stdin, capture_output=True, text=True, env=env, timeout=1800,
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude failed (exit {proc.returncode}): {(proc.stderr or proc.stdout)[-500:]}")
    if proc.returncode != 0 or out.get("is_error") or "structured_output" not in out:
        raise RuntimeError(f"claude failed: {out.get('result') or out.get('subtype')}")
    usage = out.get("usage", {})
    stats = {
        "input_tokens": sum(usage.get(k, 0) for k in
                            ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
        "output_tokens": usage.get("output_tokens", 0),
        "seconds": round(out.get("duration_ms", 0) / 1000),
    }
    return out["structured_output"]["moments"], stats
