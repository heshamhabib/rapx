"""
Shared encoder for the game's sound effects and voices (IDEA-31): Ogg Vorbis via oggenc (`brew install vorbis-tools`).
Not MP3: the engine loads short sounds fully into memory, and MP3Sharp hangs on that path (it froze the lobby on
the "player joined" bleep, 2026-11-07) and reports mono files as mono while returning stereo data. The engine's Ogg
loader (NVorbis) reads to the real end of the data and handles mono. Music stays MP3 (it is streamed).
"""
import os
import subprocess
import tempfile

QUALITY = "3"  # ~80-110 kbit/s; voices and effects are band-limited anyway


def encode(src, out, ffmpeg_args=()):
    """Any audio file -> Ogg Vorbis at `out`; ffmpeg_args (e.g. ["-af", ..., "-ac", "1"]) are applied on the way."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    try:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, *ffmpeg_args, "-map_metadata", "-1", "-bitexact", "-c:a", "pcm_s16le", wav],
                       check=True)
        subprocess.run(["oggenc", "-Q", "-q", QUALITY, "-o", out, wav], check=True)
    finally:
        os.remove(wav)
