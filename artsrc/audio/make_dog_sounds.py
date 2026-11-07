#!/usr/bin/env python3
"""
Cuts the attack dog's sounds (IDEA-31) from CC0 Freesound recordings in artsrc/audio/dog/source/ (list and links in
artsrc/audio/dog/SOURCE.md). Same names as the original voice files, written to mods/rapx/audio/dog/<name>.ogg.
Cut points were picked by loudness/brightness analysis (one bark, yelp or whine per cut), so check by ear.

  python3 artsrc/audio/make_dog_sounds.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "dog", "source")
OUT = os.path.join(HERE, "..", "..", "mods", "rapx", "audio", "dog")
sys.path.insert(0, HERE)
import ogg  # noqa: E402

# name -> list of (source file, start s, length s); several cuts are joined in order
CUTS = {
    "dogw3px": [("fs231762.mp3", 0.06, 0.30)],                                 # select: one deep alert bark
    "dogy1": [("fs9032.mp3", 0.05, 0.26)],                                     # move: short eager yip
    "dogg5p": [("fs122183.mp3", 4.42, 0.48), ("fs332176.mp3", 0.13, 0.48)],    # attack: snarl, then two barks
    "dogw5": [("fs160478.mp3", 3.08, 0.62)],                                   # death: sharp pained yelp
    "dogw7": [("fs184808.mp3", 0.08, 0.62)],                                   # death: whimper fading out
    "dogw6": [("fs160478.mp3", 7.28, 1.14)],                                   # burned / zapped: frantic yelps
}


def cut(src, start, length, path):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(start), "-t", str(length),
                    "-i", os.path.join(SRC, src), "-ac", "1", "-ar", "44100",
                    "-af", f"highpass=f=80,afade=t=in:d=0.005,afade=t=out:st={length - 0.1:.3f}:d=0.1", path],
                   check=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, parts in CUTS.items():
            files = []
            for i, (src, start, length) in enumerate(parts):
                files.append(os.path.join(tmp, f"{name}{i}.wav"))
                cut(src, start, length, files[-1])
            ins = sum((["-i", f] for f in files), [])
            mix = "".join(f"[{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=0:a=1,loudnorm=I=-14:TP=-1.5"
            joined = os.path.join(tmp, name + ".wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", mix, "-ar", "44100",
                            joined], check=True)
            ogg.encode(joined, os.path.join(OUT, name + ".ogg"))
            print(f"{name}.ogg")


if __name__ == "__main__":
    main()
