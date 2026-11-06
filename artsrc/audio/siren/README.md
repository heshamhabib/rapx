# Nuclear launch siren

`mods/rapx/audio/superweapons/nuke-siren.wav` (8.2 s) is cut from **"Sirens and Alarm Noise" by aquinn**
(https://opengameart.org/node/41407, CC0 / public domain, no attribution required):
the two quick wails at 21.45-25.15 s, then the long rising wail at 26.2-30.95 s, crossfaded, faded in and out,
loudness-normalised to -14 LUFS, mono 44.1 kHz:

    ffmpeg -i aquinn-sirens-cc0.mp3 -filter_complex "[0:a]atrim=21.45:25.15,asetpts=PTS-STARTPTS[a];\
    [0:a]atrim=26.2:30.95,asetpts=PTS-STARTPTS[b];[a][b]acrossfade=d=0.25:c1=tri:c2=tri,afade=t=in:d=0.08,\
    afade=t=out:st=7.9:d=0.5,loudnorm=I=-14:TP=-1.5:LRA=7,aresample=44100" -ac 1 -c:a pcm_s16le nuke-siren.wav

`fivebros-facility-breach-siren-ccby4.wav` ("Facility Breach Siren" by FiveBrosStopMosYT, CC-BY 4.0,
https://opengameart.org/node/138430) is a spare two-tone alarm; it is not used in the game (it would need credit).
