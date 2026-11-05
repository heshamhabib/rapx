#!/usr/bin/env python3
"""Convert any video ffmpeg can read into the .rpv format played by RpvLoader.

Usage: tools/make-video.py input.mp4 output.rpv [--width 1280] [--fps 24] [--quality 3] [--audio mp3|pcm]

MP3 audio is stored as-is (header SampleBits 0) and decoded by the mod's SoundFormats when the video loads;
it keeps the file small enough for GitHub's 100 MB limit.
"""
import argparse
import glob
import os
import struct
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("output")
parser.add_argument("--width", type=int, default=1280)
parser.add_argument("--fps", type=int, default=24)
parser.add_argument("--quality", type=int, default=3, help="JPEG quality, 2 (best) to 31 (worst)")
parser.add_argument("--audio", choices=["mp3", "pcm"], default="mp3")
parser.add_argument("--audio-bitrate", default="256k", help="MP3 bitrate")
args = parser.parse_args()

RATE, CHANNELS, BITS = 44100, 2, 16

with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["ffmpeg", "-v", "error", "-i", args.input,
                    "-vf", f"fps={args.fps},scale={args.width}:-2:flags=lanczos",
                    "-q:v", str(args.quality), os.path.join(tmp, "f%05d.jpg")], check=True)
    if args.audio == "mp3":
        audio = os.path.join(tmp, "audio.mp3")
        codec = ["-c:a", "libmp3lame", "-b:a", args.audio_bitrate, "-f", "mp3"]
    else:
        audio = os.path.join(tmp, "audio.pcm")
        codec = ["-f", "s16le"]
    subprocess.run(["ffmpeg", "-v", "error", "-i", args.input, "-vn", "-map_metadata", "-1", *codec,
                    "-ac", str(CHANNELS), "-ar", str(RATE), audio], check=False)

    frames = sorted(glob.glob(os.path.join(tmp, "f*.jpg")))
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", frames[0]],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    width, height = int(probe[0]), int(probe[1])
    pcm = open(audio, "rb").read() if os.path.exists(audio) else b""

    with open(args.output, "wb") as out:
        out.write(b"RPXV")
        out.write(struct.pack("<HHHBBiBi", width, height, len(frames), args.fps,
                              CHANNELS, RATE, BITS if args.audio == "pcm" else 0, len(pcm)))
        out.write(pcm)
        for f in frames:
            data = open(f, "rb").read()
            out.write(struct.pack("<i", len(data)))
            out.write(data)

print(f"{args.output}: {width}x{height}, {len(frames)} frames @ {args.fps}fps, "
      f"{len(pcm) / 1e6:.1f} MB {args.audio} audio, {os.path.getsize(args.output) / 1e6:.1f} MB")
