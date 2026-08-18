"""Zero-cost, zero-signup background video generator.

Module 4's original design assumed stock footage from Pexels/Pixabay,
which needs a (free but external) API key. Without one, the pipeline
used to just give up and produce no rendered video at all — meaning
nothing in this project could show real output without first signing up
for something. This generates an animated gradient background using
ffmpeg's own built-in `gradients` source filter instead: no network
call, no API key, no model download, just ffmpeg. It's the automatic
fallback in video/run.py whenever no stock footage is available.
"""
import hashlib
import logging
from pathlib import Path

from faceless_pipeline.config import settings
from faceless_pipeline.modules.video.assemble import TARGET_HEIGHT, TARGET_WIDTH, run_ffmpeg

logger = logging.getLogger(__name__)

# Curated (dark, vibrant) color pairs — chosen so white burned-in
# captions with a black outline stay readable against all of them, and
# animated enough to not look like a static slide.
PALETTE: list[tuple[str, str]] = [
    ("0x1e1b4b", "0x7c3aed"),  # midnight indigo -> violet
    ("0x0c4a6e", "0x06b6d4"),  # deep teal -> cyan
    ("0x1a1a2e", "0xe94560"),  # near-black -> crimson
    ("0x134e4a", "0x2dd4bf"),  # forest teal -> mint
    ("0x581c87", "0xf59e0b"),  # deep purple -> amber
    ("0x7f1d1d", "0xf97316"),  # dark red -> orange
    ("0x0f172a", "0x6366f1"),  # slate black -> indigo
    ("0x164e63", "0xa855f7"),  # deep cyan -> purple
]

GRADIENT_TYPES = ["linear", "radial", "circular", "spiral"]


def _pick_for_topic(topic: str) -> tuple[str, str, str, int]:
    """Deterministic per-topic pick, so regenerating the same script's
    video keeps a consistent look, but different topics get variety."""
    digest = hashlib.sha256(topic.encode("utf-8")).hexdigest()
    palette_idx = int(digest[:8], 16) % len(PALETTE)
    type_idx = int(digest[8:16], 16) % len(GRADIENT_TYPES)
    seed = int(digest[16:24], 16) % (2**31)
    c0, c1 = PALETTE[palette_idx]
    return c0, c1, GRADIENT_TYPES[type_idx], seed


def generate_procedural_background(duration_seconds: float, out_path: str, topic: str = "") -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    c0, c1, gradient_type, seed = _pick_for_topic(topic)

    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-f", "lavfi",
        "-i",
        f"gradients=size={TARGET_WIDTH}x{TARGET_HEIGHT}:duration={duration_seconds}:rate=25:"
        f"speed=0.03:type={gradient_type}:c0={c0}:c1={c1}:seed={seed}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out_path,
    ]
    logger.info("Generating procedural background (%s, seed=%s) for topic=%r", gradient_type, seed, topic)
    run_ffmpeg(cmd)
    return out_path
