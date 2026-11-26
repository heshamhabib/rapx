# Titan sound sources

King Kong's sounds (and the shared titan-smash) are built by `artsrc/audio/make_titan_sounds.py` from these
freesound.org recordings, all **CC0** (no credit required). Fetched as the site's HQ MP3 previews with
`python3 artsrc/audio/fetch_freesound.py kong-gorilla kong-gorilla2 kong-lion kong-tiger kong-bear kong-chest kong-impact kong-whoosh`
into `artsrc/audio/sfx/source/fs<id>.mp3`.

| Freesound id | Title | Author | Used for |
|---|---|---|---|
| 397054 | Gorillaschrei.wav | J0ck0 | kong-roar1 (the ape's voice) |
| 763202 | Monster Gorilla Imitation | mosaichorse | kong-roar2, kong-die |
| 205891 | gorilla audio.aif | kfledman | kong-roar3, chest-beat grunt, throw grunt |
| 469123 | Demon_Lion_Monster_Growl_Roar | Manim8 | kong-roar1, kong-die (the size) |
| 366671 | Monster growl.mp3 | cylon8472 | kong-roar1, kong-roar2 (low layer) |
| 410343 | Roar.wav | waxsocks | kong-roar2 |
| 344903 | Monster - deep growl.wav | Aegersum | kong-roar3, titan-smash |
| 342204 | Beast Snarling | Christopherderp | kong-leap |
| 540985 | Heartbeat (Dumpf-Dumpf) | magnuswaker | kong-chest (low thump) |
| 825964 | UNDERGROUND PROFOUND CAVE BOOM | ROHHSA | titan-smash, kong-leap landing, kong-die |
| 701308 | Hit reverb (dark) | xkeril | titan-smash |
| 237980 | Very Big Whoosh | Paul368 | kong-throw, kong-leap |
| 322250 | Big Punch with whoosh | Paul368 | kong-leap |

Godzilla's sounds are the mod's own CC0 animal calls (elephant, crocodile: see `artsrc/audio/elephant/SOURCE.md`)
and synthesis; no film audio is used.
