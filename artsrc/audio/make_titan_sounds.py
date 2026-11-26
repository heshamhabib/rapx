#!/usr/bin/env python3
"""
Titan sounds (rules/titans.yaml) -> mods/rapx/audio/titans/. Original sounds, not film recordings: the roars are the
mod's own CC0 animal calls (elephant, crocodile, dog: see their SOURCE.md files) slowed and pitched far down, layered
and given a long echo, so they sound like something the size of a building. Footfalls, the breath charge, the chest
beat and the impacts are synthesised with ffmpeg.

  python3 artsrc/audio/make_titan_sounds.py

To use other recordings, drop Ogg files with the same names into mods/rapx/audio/titans/ (they must be Ogg: see ogg.py).
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ogg  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
AUDIO = os.path.join(ROOT, "mods", "rapx", "audio")
OUT = os.path.join(AUDIO, "titans")
SR = 44100


def src(rel):
    return os.path.join(AUDIO, rel)


def down(rate):
    """Slower and lower: a big animal's call."""
    return f"aresample={SR},asetrate={SR}*{rate},aresample={SR}"


# Long echo off distant hills, then one level for every sound
# (no loudnorm: its dynamic mode ramps the gain up over the first seconds and flattens the attacks; mix() peak-normalises)
TAIL = "acompressor=threshold=0.15:ratio=3:attack=10:release=250,aecho=0.8:0.6:180|420:0.35|0.2,highpass=f=28"


def mix(name, inputs, chains, extra="", seconds=None, tail=None):
    """inputs: files (or lavfi sources prefixed 'lavfi:'); chains: one filter per input; mixed, then TAIL (or tail)."""
    args = ["ffmpeg", "-loglevel", "error", "-y"]
    for i in inputs:
        if i.startswith("lavfi:"):
            args += ["-f", "lavfi", "-i", i[6:]]
        else:
            args += ["-i", i]
    parts = [f"[{k}:a]aformat=channel_layouts=mono,{c}[a{k}]" for k, c in enumerate(chains)]
    labels = "".join(f"[a{k}]" for k in range(len(chains)))
    graph = ";".join(parts) + f";{labels}amix=inputs={len(chains)}:normalize=0:duration=longest{extra},{tail or TAIL}[out]"
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    try:
        cmd = args + ["-filter_complex", graph, "-map", "[out]", "-ac", "1", "-ar", str(SR)]
        if seconds:
            cmd += ["-t", str(seconds)]
        subprocess.run(cmd + [wav], check=True)
        # Two-pass peak normalisation to -1 dBFS (keeps every attack)
        probe = subprocess.run(["ffmpeg", "-i", wav, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
        peak = float(probe.split("max_volume:")[1].split("dB")[0])
        ogg.encode(wav, os.path.join(OUT, name + ".ogg"), ["-af", f"volume={-1.0 - peak:.2f}dB"])
    finally:
        os.remove(wav)
    print(name)


def thump(freq=38, decay=6, length=1.2):
    """A deep footfall / impact: a falling sine plus a short low rumble of noise."""
    return [f"lavfi:sine=f={freq}:d={length}:sample_rate={SR}",
            f"lavfi:anoisesrc=d={length}:c=brown:a=0.9:r={SR}"], \
           [f"volume=2.2,afade=t=out:st=0:d={length / decay * 3}",
            f"lowpass=f=160,volume=1.4,afade=t=out:st=0:d={length / decay * 2}"]


def main():
    os.makedirs(OUT, exist_ok=True)
    trumpet = [src(f"elephant/eleph-trumpet{i}.ogg") for i in (1, 2, 3)]
    bellow = [src(f"croc/croc-bellow{i}.ogg") for i in (1, 2)]
    growl = [src(f"croc/croc-growl{i}.ogg") for i in (1, 2)]
    rumble = [src(f"elephant/eleph-rumble{i}.ogg") for i in (1, 2)]

    # Godzilla: a shrieking trumpet over a bellow, both a full octave or more down
    for n, (t, b) in enumerate(((trumpet[0], bellow[0]), (trumpet[1], bellow[1]), (trumpet[2], bellow[0])), 1):
        mix(f"godz-roar{n}", [t, b], [f"{down(0.52)},volume=1.0", f"{down(0.45)},volume=0.9"])
    mix("godz-die", [trumpet[1], rumble[0]], [f"{down(0.4)},afade=t=out:st=2:d=3", f"{down(0.5)},volume=1.2"])

    # Atomic breath (PxAttackPrepareSound: starts with the attack, the beam fires 1.2 s later, FireDelay 30).
    # Charge, 0-1.2 s: a deep thrum that swells and pulses ever faster, crackling clicks that speed up as the plates
    # light up from the tail to the head, a rising whine. Blast, 1.2-3.6 s: a distorted, fluttering roar of energy
    # with an electric sizzle on top and a sub-bass punch.
    clicks = "+".join(f"exp(-70*(t-{1.2 * (1 - (1 - k / 10) ** 1.7):.3f}))*gte(t,{1.2 * (1 - (1 - k / 10) ** 1.7):.3f})*{0.3 + 0.07 * k:.2f}"
                      for k in range(10))
    mix("godz-breath",
        [f"lavfi:aevalsrc='0.7*sin(2*PI*42*t)*(0.25+0.75*t/1.2)*(0.6+0.4*sin(2*PI*(5*t+7*t*t)))':d=1.25:s={SR}",
         f"lavfi:aevalsrc='(random(0)*2-1)*({clicks})':d=1.25:s={SR}",
         f"lavfi:aevalsrc='0.12*sin(2*PI*(300*t+400*t*t))*t/1.2':d=1.2:s={SR}",
         f"lavfi:anoisesrc=d=2.6:c=brown:a=0.9:r={SR}",
         f"lavfi:anoisesrc=d=2.6:c=pink:a=0.7:r={SR}",
         f"lavfi:anoisesrc=d=2.6:c=white:a=0.5:r={SR}",
         f"lavfi:aevalsrc='sin(2*PI*38*t)*exp(-1.2*t)':d=2.6:s={SR}"],
        ["afade=t=out:st=1.15:d=0.1",
         "highpass=f=1800,volume=1.6",
         "afade=t=out:st=1.15:d=0.05",
         "adelay=1200,lowpass=f=1400,volume=4,asoftclip=type=atan,tremolo=f=27:d=0.35,afade=t=in:st=1.2:d=0.05,afade=t=out:st=3.0:d=0.8",
         "adelay=1200,bandpass=f=900:w=1200,volume=2.5,asoftclip=type=atan,afade=t=in:st=1.2:d=0.05,afade=t=out:st=3.0:d=0.8",
         "adelay=1200,highpass=f=4000,flanger=delay=3:depth=5:speed=2,volume=0.5,afade=t=in:st=1.2:d=0.1,afade=t=out:st=2.8:d=0.8",
         "adelay=1200,volume=1.8"])

    # Footfalls (one step; the walking loop is two steps per 1.6 s gait cycle)
    i, c = thump(36, 6, 1.4)
    mix("titan-step", i, c)
    mix("titan-steps",
        [f"lavfi:aevalsrc='sin(2*PI*36*mod(t,0.8))*exp(-7*mod(t,0.8))':d=1.6:s={SR}",
         f"lavfi:anoisesrc=d=1.6:c=brown:a=0.6:r={SR}"],
        ["volume=1.8", "lowpass=f=140,volume='if(lt(mod(t,0.8),0.15),1.2,0)':eval=frame"], seconds=1.6)

    # Godzilla swimming: deep churning water, a loop as long as one swim stroke cycle (1.6 s)
    mix("godz-wake",
        [f"lavfi:anoisesrc=d=1.6:c=brown:a=0.8:r={SR}", f"lavfi:anoisesrc=d=1.6:c=pink:a=0.5:r={SR}"],
        ["lowpass=f=300,volume='0.7+0.5*sin(2*PI*t/0.8)':eval=frame",
         "bandpass=f=1200:w=900,volume='0.25+0.25*sin(2*PI*t/0.8+1)':eval=frame"], seconds=1.6)


    kong()


# King Kong: real CC0 recordings from freesound.org (artsrc/audio/fetch_freesound.py kong-*; sources and authors in
# artsrc/audio/titans-SOURCE.md), layered and mastered like a film creature: a real gorilla's scream for the ape's
# voice, a deep lion roar and a monster growl for the size, a sub-bass swell under it, then compression, a low shelf,
# a presence lift and a big hall. Previews land in artsrc/audio/sfx/source/fs<id>.mp3.
FS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfx", "source")
KONG_TAIL = ("acompressor=threshold=0.12:ratio=4:attack=8:release=250:makeup=2,"
             "equalizer=f=90:t=q:w=0.9:g=5,equalizer=f=2600:t=q:w=1.2:g=3,equalizer=f=7000:t=q:w=1:g=-4,"
             "aecho=0.85:0.75:70|160|330|620:0.42|0.32|0.22|0.12,highpass=f=24")


def fs(i):
    return os.path.join(FS, f"fs{i}.mp3")


def start(gate="-38dB"):
    """Trim silence before the sound starts, so layers line up on their attacks."""
    return f"silenceremove=start_periods=1:start_threshold={gate}"


def kong():
    gorilla, gorilla2, mimic = fs(397054), fs(205891), fs(763202)
    lion, growl, tiger, snarl, deep = fs(469123), fs(366671), fs(410343), fs(342204), fs(344903)
    boom, hit, whoosh, punch, thump_ = fs(825964), fs(701308), fs(237980), fs(322250), fs(540985)
    sub = lambda d, f0=42: f"lavfi:aevalsrc='sin(2*PI*{f0}*t)*min(1,t*6)*exp(-0.9*t)':d={d}:s={SR}"

    # Roars: the ape's voice on top, the size underneath
    mix("kong-roar1", [gorilla, lion, growl, sub(3.4)],
        [f"{start()},{down(0.66)},volume=1.6", f"{start()},{down(0.82)},atrim=0:3.2,volume=1.0",
         f"{start()},{down(0.74)},atrim=0:3.0,lowpass=f=900,volume=0.55,afade=t=out:st=2.2:d=0.8", "volume=0.9"],
        tail=KONG_TAIL)
    mix("kong-roar2", [mimic, tiger, growl, sub(3.6, 38)],
        [f"{start()},{down(0.72)},atrim=0:3.4,volume=1.5,afade=t=out:st=2.7:d=0.7", f"{start()},{down(0.78)},atrim=0:3.2,volume=0.9",
         f"{start()},{down(0.7)},atrim=1.5:4.5,lowpass=f=700,volume=0.5,afade=t=out:st=2.4:d=0.6", "volume=0.8"],
        tail=KONG_TAIL)
    # A shorter, grunting call (select)
    mix("kong-roar3", [gorilla2, deep, sub(1.8, 50)],
        [f"{start()},{down(0.7)},atrim=0:1.8,volume=1.6", f"{start()},{down(0.85)},atrim=0:1.6,volume=0.8", "volume=0.6"],
        tail=KONG_TAIL)

    # Chest beat: eight blows, alternating hands (two drum pitches), each a hollow body boom with a skin slap and a
    # fur rustle, the real low thump under every other blow; ends with a short grunt
    hits = [k * 0.17 for k in range(8)]
    body = "+".join(f"{0.95 if k % 2 else 0.8}*sin(2*PI*({78 if k % 2 else 66}-25*(t-{t0:.2f}))*(t-{t0:.2f}))*exp(-11*(t-{t0:.2f}))*gte(t,{t0:.2f})"
                    for k, t0 in enumerate(hits))
    slap = "+".join(f"exp(-90*(t-{t0:.2f}))*gte(t,{t0:.2f})" for t0 in hits)
    mix("kong-chest", [f"lavfi:aevalsrc='{body}':d=2.6:s={SR}", f"lavfi:aevalsrc='(random(0)*2-1)*({slap})':d=2.6:s={SR}",
                       thump_, gorilla2],
        ["lowpass=f=420,volume=1.8", "bandpass=f=700:w=900,volume=0.9",
         f"{down(0.8)},aloop=loop=3:size={int(0.34 * SR)},volume=0.7",
         f"adelay=1450,{start()},{down(0.72)},atrim=0:1.0,volume=0.9,afade=t=out:st=0.7:d=0.3"],
        tail=KONG_TAIL)

    # Hammer blow / stomp: the cave boom and a dark hit, cracking rock on top, a grunt of effort
    mix("titan-smash", [boom, hit, f"lavfi:anoisesrc=d=1.2:c=white:a=0.6:r={SR}", deep, sub(2.4, 34)],
        [f"{start()},{down(0.8)},volume=1.4", f"{start()},{down(0.7)},volume=0.8",
         "highpass=f=1500,volume='if(lt(mod(t*23,1),0.18),1,0.15)':eval=frame,afade=t=out:st=0.1:d=0.9,volume=0.35",
         f"{start()},{down(0.75)},atrim=0:0.9,volume=0.45", "volume=1.1"],
        tail=KONG_TAIL, seconds=3.5)

    # Boulder throw: effort grunt, a huge swing of air
    mix("kong-throw", [whoosh, gorilla2],
        [f"atrim=0.35,asetpts=PTS-STARTPTS,{down(0.75)},atrim=0:1.4,volume=1.3", f"{start()},{down(0.75)},atrim=0:0.7,volume=0.9"],
        tail=KONG_TAIL)

    # Leap swat: launch grunt, the whoosh of the swing and the punch, a snarl at the top, the landing boom
    mix("kong-leap", [punch, whoosh, snarl, boom, sub(2.6, 36)],
        [f"atrim=0.5,asetpts=PTS-STARTPTS,{down(0.7)},volume=1.2", f"atrim=0.4,asetpts=PTS-STARTPTS,{down(0.85)},atrim=0:0.9,volume=0.9",
         f"{start('-50dB')},{down(0.75)},atrim=0:1.0,volume=6.0", f"adelay=380,{start()},{down(0.8)},volume=1.2",
         "adelay=380,volume=1.0"],
        tail=KONG_TAIL, seconds=3.0)

    # Death: a long, failing roar falling in pitch, then the body hitting the ground
    mix("kong-die", [mimic, lion, boom],
        [f"{start()},{down(0.55)},atrim=0:4.0,volume=1.5,afade=t=out:st=2.6:d=1.4",
         f"{start()},{down(0.62)},atrim=0:3.6,volume=0.8,afade=t=out:st=2.4:d=1.2",
         f"adelay=3200,{start()},{down(0.7)},volume=1.3"],
        tail=KONG_TAIL)


if __name__ == "__main__":
    main()
