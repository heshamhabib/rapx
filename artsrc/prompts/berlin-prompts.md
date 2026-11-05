# RedAlert Project X - Berlin 1946 painted map prompts (ChatGPT, IDEA-28)

Art for the Berlin 1946 painted map. Output goes to `assets/maps/berlin/`.

**How to use**

1. Style frames: each one repaints the same Blender crop (`artsrc/maps/berlin/build/styleframe-src.png`, made by
   `build_backdrop.py` + a crop around the Brandenburg Gate). Pick the best one.

       python3 artsrc/prompts/generate_images.py --prompts berlin-prompts.md --category maps --only berlin/style-a,berlin/style-b,berlin/style-c,berlin/style-d

2. Textures: run with the chosen frame as the style reference, e.g.

       python3 artsrc/prompts/generate_images.py --prompts berlin-prompts.md --category maps --from berlin/tex-cobbles --ref ../../assets/maps/berlin/style-a.png

   `artsrc/maps/berlin/build_backdrop.py` uses `assets/maps/berlin/tex-*.png` instead of the photo textures when they
   exist.

The look is a hand-painted, pre-rendered tactics-game map from around 2000 (rich, detailed, slightly stylised), seen
from straight above with heights leaning up the picture and the light from the top-left, like the rest of the game.
Nothing in these prompts copies an existing game's art.

## Map style frames

### 1. Style frame A - warm painterly
Save as: `berlin/style-a.png`
Reference: `artsrc/maps/berlin/build/styleframe-src.png`

```
A hand-painted 2D map tile for a real-time tactics game, in the rich pre-rendered painterly style of late-1990s and early-2000s tactics games: every surface painted by hand with fine detail, slightly stylised, crisp and readable. Scene: the centre of Berlin in 1946, a year after the war: the Brandenburg Gate with its six rows of columns and the damaged chariot sculpture on top, an open cobbled square east of it, rows of five-storey plastered apartment houses, some intact with pitched slate and red tile roofs, some burnt-out shells with empty black window holes and soot, some collapsed into heaps of bricks and plaster rubble, bomb craters, wrecked cars, tank traps, puddles, scattered debris, tufts of weeds. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: warm late-afternoon sun from the top-left, soft long shadows to the bottom-right, warm ochre, sand and brick colours with cool grey-blue shadows. Keep the street layout and every building exactly where the attached render has it. No people, no soldiers, no tanks, no text, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

### 2. Style frame B - grey and gritty
Save as: `berlin/style-b.png`
Reference: `artsrc/maps/berlin/build/styleframe-src.png`

```
A hand-painted 2D map tile for a real-time tactics game, in the detailed pre-rendered painterly style of late-1990s and early-2000s tactics games, gritty and realistic. Scene: the centre of Berlin in 1946: the Brandenburg Gate with six rows of columns and its battered chariot sculpture, a cobbled square, five-storey plastered apartment houses, some intact with slate and tile roofs, many burnt-out shells with black window holes and soot streaks, others collapsed into heaps of bricks and plaster, bomb craters with dark scorched rims, wrecked burnt cars, tank traps, puddles of rain water, dust and debris everywhere. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: overcast late-autumn day with a pale sun from the top-left and soft shadows to the bottom-right; muted greys, umber, faded ochre and brick red, wet stone. Keep the street layout and every building exactly where the attached render has it. No people, no soldiers, no tanks, no text, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

### 3. Style frame C - crisp detailed
Save as: `berlin/style-c.png`
Reference: `artsrc/maps/berlin/build/styleframe-src.png`

```
A highly detailed hand-painted 2D game map in the pre-rendered style of classic tactics games from around 2000: sharp, clean, richly textured, every brick, cobblestone, roof tile, window frame and piece of rubble readable, like a detailed painted diorama. Scene: the centre of Berlin in 1946: the Brandenburg Gate (six rows of Doric columns, attic, the damaged quadriga on top), an open cobbled square, perimeter blocks of five-storey apartment houses with ornate plaster facades and slate or red tile roofs with chimneys, burnt-out shells with empty window holes and soot, collapsed houses as rubble heaps with broken walls and timber beams, bomb craters, wrecked cars, tank traps, puddles, weeds. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: clear afternoon sun from the top-left, crisp shadows to the bottom-right, natural colours. Keep the street layout and every building exactly where the attached render has it. No people, no soldiers, no tanks, no text, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

### 4. Style frame D - bold storybook
Save as: `berlin/style-d.png`
Reference: `artsrc/maps/berlin/build/styleframe-src.png`

```
A hand-painted 2D map for a real-time tactics game, painterly and bold like a richly illustrated war-game map: visible brush strokes, strong shapes, deep shadows, saturated but believable colours, very readable at a glance. Scene: Berlin in 1946: the Brandenburg Gate with its columns and damaged chariot statue, a cobbled square, five-storey apartment houses with plaster facades and slate or red tile roofs, burnt-out shells with black window holes, collapsed houses as rubble heaps, bomb craters, wrecked cars, tank traps, puddles. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: golden sun from the top-left, strong shadows to the bottom-right. Keep the street layout and every building exactly where the attached render has it. No people, no soldiers, no tanks, no text, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

## Map textures

### 5. Cobblestone street
Save as: `berlin/tex-cobbles.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: old Berlin granite cobblestone street (rows of small grey and brown granite setts), worn, dusty, a few missing stones, cracks with dirt, scattered small pieces of brick and glass. Even lighting from the top-left, no strong shadows, no perspective, no objects, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 6. Cracked asphalt
Save as: `berlin/tex-asphalt.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: an old dark grey asphalt road surface from the 1940s, cracked, patched, with dust, small potholes, tyre-worn darker strips, oil stains and scattered gravel. Even lighting from the top-left, no perspective, no road markings, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 7. Pavement
Save as: `berlin/tex-pavement.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: a Berlin pavement of large square granite slabs with bands of small mosaic cobbles, dusty, cracked slabs, plaster dust and small debris in the joints. Even lighting from the top-left, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 8. Mud and worn grass
Save as: `berlin/tex-mud.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: a muddy park after its trees were cut down for firewood: brown churned earth, tyre and boot tracks, small puddles, patches of worn yellow-green grass, a few small tree stumps and wood chips. Even lighting from the top-left, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 9. Rubble ground
Save as: `berlin/tex-rubble.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: flat ground covered with bomb debris: broken bricks, plaster chunks, dust, splintered wood, bits of roof tile and twisted metal, grey-ochre dust over everything. Even lighting from the top-left, no tall objects, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 10. Quay stone
Save as: `berlin/tex-quay.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: the top of a river quay wall in Berlin: big pale sandstone and granite blocks in rows, weathered, moss in the joints, a few chips and stains. Even lighting from the top-left, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 11. Worn lawn
Save as: `berlin/tex-lawn.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: a neglected city lawn in autumn 1946: uneven green and yellow grass, bare earth patches, weeds, fallen leaves. Even lighting from the top-left, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 12. Courtyard dirt
Save as: `berlin/tex-courtyard.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: the packed-earth floor of a Berlin back courtyard: grey-brown dirt, old cobbles showing through, coal dust, broken crates, scattered bricks and junk, puddles. Even lighting from the top-left, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 13. Plaster facade, ochre
Save as: `berlin/tex-facade-ochre.png`

```
A seamless, horizontally tileable texture of a building facade seen straight on (front elevation, no perspective), hand-painted in the style of the attached map: a five-storey Berlin apartment house from 1900 with ochre plaster, tall windows with white stone surrounds and small cornices, a cornice between floors, a ground floor with shop windows, damaged by war: bullet pockmarks, missing plaster showing brick, some broken windows. The facade fills the whole image from the pavement to the roof edge. Even lighting, no sky, no ground, edges tile seamlessly left and right. No text, no signs, no frame. Square image, aspect ratio 1:1.
```

### 14. Plaster facade, grey
Save as: `berlin/tex-facade-grey.png`

```
A seamless, horizontally tileable texture of a building facade seen straight on (front elevation, no perspective), hand-painted in the style of the attached map: a five-storey Berlin apartment house from 1900 with grey-beige plaster, ornate window surrounds and balconies, a cornice between floors, a ground floor with a big arched gateway and shop windows, war damage: bullet pockmarks, shrapnel scars, a few boarded-up windows. The facade fills the whole image from the pavement to the roof edge. Even lighting, no sky, no ground, edges tile seamlessly left and right. No text, no signs, no frame. Square image, aspect ratio 1:1.
```

### 15. Burnt-out facade
Save as: `berlin/tex-facade-burnt.png`

```
A seamless, horizontally tileable texture of a burnt-out building facade seen straight on (front elevation, no perspective), hand-painted in the style of the attached map: the standing outer wall of a five-storey Berlin apartment house gutted by fire: empty black window holes, heavy soot streaks above each window, cracked and fallen plaster showing brick, a ragged broken top edge. The facade fills the whole image. Even lighting, edges tile seamlessly left and right. No text, no frame. Square image, aspect ratio 1:1.
```

### 16. Slate roof
Save as: `berlin/tex-roof-slate.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: a dark grey slate roof, rows of overlapping slates, weathered, a few missing or broken slates, some moss and soot. Even lighting from the top-left, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 17. Red tile roof
Save as: `berlin/tex-roof-tile.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in the style of the attached map: a faded red clay tile roof, rows of curved tiles, weathered with dark stains and dust, a few cracked or missing tiles. Even lighting from the top-left, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```
