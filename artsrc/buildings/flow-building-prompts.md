# Google Flow prompts: buildings taking damage and collapsing

Each building gets two clips, both made in Flow's **Frames** mode from the building's own art, so every state stays
exactly the same building:

1. **damage**: the healthy building is hit and ends exactly on its damaged look (first and last frame given).
2. **collapse**: the damaged building collapses into a heap of rubble, and the dust settles completely (first frame given).

The building's normal (healthy) look stays the current still art with its live lights, smoke and steam, which keeps it
perfectly stable on screen.

**Start and end frames** are made for you by `python3 artsrc/buildings/make_flow_frames.py <id>` into
`~/Movies/explosion/buildings/` (`<id>-intact.png`, `<id>-damaged.png`): the building on flat magenta, the same size and
place in both, with room around it for debris and dust. Magenta, not green, because the bright green bands on the
buildings are the team colour and must stay green.

**What I check when a clip arrives** (and send back if it fails): the building never moves, grows or changes shape
outside the damage; the background stays flat magenta; the green bands stay pure bright green; nothing touches the frame
edge; the damage clip ends on the given last frame; the collapse clip ends still, with all dust gone.

---

## Pilot: Power Plant (powr)

### powr-damage.mp4 — **720p**, 8 s, **Frames**

**Flow settings:** Video · 16:9 · **720p** · **8 seconds** · Frames · first frame = `powr-intact.png` · last frame = `powr-damaged.png` · x2 if credits allow

The camera, framing, lighting and background stay exactly as in the first frame for the whole shot: locked-off camera, no movement, no zoom, no cuts; the building does not move, turn or change size, and the flat magenta background stays flat magenta with no ground, no shadows added and no environment. The power plant comes under attack: artillery shells and rockets slam into it one after another, each with a sharp flash, a burst of fire and flying concrete and metal debris; the top of the right cooling tower is blown apart and crumbles, the wall and roof beside it crack and cave in, fires break out inside the gap and sparks fly from torn electrical gear. The dust and smoke of the hits thin out so that the shot ends exactly on the damaged building of the last frame, still burning in the same places. The bright green bands stay exactly the same pure bright green. Real-time speed, no slow motion. Photorealistic, like real military footage and high-end film visual effects, high detail, 16:9 landscape, highest resolution.

### powr-collapse.mp4 — **720p**, 8 s, **Frames**

**Flow settings:** Video · 16:9 · **720p** · **8 seconds** · Frames · first frame = `powr-damaged.png` · no last frame · x2 if credits allow

The camera, framing, lighting and background stay exactly as in the first frame for the whole shot: locked-off camera, no movement, no zoom, no cuts; the flat magenta background stays flat magenta with no ground, no shadows added and no environment. The damaged power plant is destroyed for good: a final explosion bursts inside it, both cooling towers crack, lean and fall in on themselves, the walls fold inward, the roof caves in and the whole structure collapses straight down into its own footprint; a thick wave of grey-brown concrete dust bursts out low along the ground and billows up, fire flickers through the dust. Then the dust slowly settles and clears completely, leaving a low flat heap of broken concrete, twisted steel beams, pipes and scorched rubble on the same footprint, with a few small fires that die out. The last second is completely still: only the rubble heap on the flat magenta background, no smoke, no dust, no fire. Nothing ever leaves the frame. Real-time speed, no slow motion. Photorealistic, like real military footage and high-end film visual effects, high detail, 16:9 landscape, highest resolution.

---

## Any other building (after the pilot is approved)

Run `python3 artsrc/buildings/make_flow_frames.py <id>` (I can do it for every building at once), then make the two
clips with the same settings, replacing **BUILDING** with a short description of the building (for example "the war
factory", "the barracks", "the radar dome") and **DAMAGE** with what its damaged frame shows (for example "the roof is
torn open and the left wall is cracked").

### <id>-damage.mp4 — **720p**, 8 s, **Frames**

**Flow settings:** Video · 16:9 · **720p** · **8 seconds** · Frames · first frame = `<id>-intact.png` · last frame = `<id>-damaged.png` · x2 if credits allow

The camera, framing, lighting and background stay exactly as in the first frame for the whole shot: locked-off camera, no movement, no zoom, no cuts; the building does not move, turn or change size, and the flat magenta background stays flat magenta with no ground, no shadows added and no environment. BUILDING comes under attack: artillery shells and rockets slam into it one after another, each with a sharp flash, a burst of fire and flying concrete and metal debris, until DAMAGE, with fires burning inside the breaches. The dust and smoke of the hits thin out so that the shot ends exactly on the damaged building of the last frame, still burning in the same places. The bright green bands stay exactly the same pure bright green. Real-time speed, no slow motion. Photorealistic, like real military footage and high-end film visual effects, high detail, 16:9 landscape, highest resolution.

### <id>-collapse.mp4 — **720p**, 8 s, **Frames**

**Flow settings:** Video · 16:9 · **720p** · **8 seconds** · Frames · first frame = `<id>-damaged.png` · no last frame · x2 if credits allow

The camera, framing, lighting and background stay exactly as in the first frame for the whole shot: locked-off camera, no movement, no zoom, no cuts; the flat magenta background stays flat magenta with no ground, no shadows added and no environment. BUILDING is destroyed for good: a final explosion bursts inside it, its walls fold inward, its roof caves in and the whole structure collapses straight down into its own footprint; a thick wave of grey-brown concrete dust bursts out low along the ground and billows up, fire flickers through the dust. Then the dust slowly settles and clears completely, leaving a low flat heap of broken concrete, twisted steel and scorched rubble on the same footprint, with a few small fires that die out. The last second is completely still: only the rubble heap on the flat magenta background, no smoke, no dust, no fire. Nothing ever leaves the frame. Real-time speed, no slow motion. Photorealistic, like real military footage and high-end film visual effects, high detail, 16:9 landscape, highest resolution.

---

## How the game will use them

- **Taking damage:** when the building drops to its damaged state, the damage clip plays once on the spot, then the
  building stays on the clip's last frame (which is its damaged art), with the filmed fires and smoke on top as now.
- **Destroyed:** the collapse clip plays in place of the current sink-into-the-ground animation, and its last frame
  (this building's own rubble) stays as the ruin, instead of the shared HD ruins.
- **Healthy:** unchanged, the still art with live lights, smoke and steam.
