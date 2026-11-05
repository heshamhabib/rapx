# RedAlert Project X - Ironward painted map prompts (ChatGPT, IDEA-28)

Art for the Ironward painted map (8-player walled prison-city, moonlit winter night). Output goes to
`assets/maps/ironward/`.

**How to use**

1. Style frames: each one repaints the same Blender crop (`artsrc/maps/ironward/build/styleframe-src.png`: a stepped
   tower with rooftop statues, the round canal, a canal bridge, the elevated railway and two neon signs). Pick one.

       python3 artsrc/prompts/generate_images.py --prompts ironward-prompts.md --category maps --only ironward/style-a,ironward/style-b,ironward/style-c,ironward/style-d

2. Textures: run with the chosen frame as the style reference, e.g.

       python3 artsrc/prompts/generate_images.py --prompts ironward-prompts.md --category maps --from ironward/tex-snow --ref ../../assets/maps/ironward/style-a.png

   `artsrc/maps/ironward/build_backdrop.py` uses `assets/maps/ironward/tex-*.png` instead of the photo textures when
   they exist.

The look is a pre-rendered tactics-game map seen from straight above with heights leaning up the picture and the
moonlight from the top-left, like the rest of the game: a noir gothic city at night, deep blue shadows, warm windows
and lamps, coloured neon. All names, signs and buildings are original; nothing copies an existing game's art.

## Map style frames

### 1. Style frame A - cinematic neon noir
Save as: `ironward/style-a.png`
Reference: `artsrc/maps/ironward/build/styleframe-src.png`

```
A highly detailed pre-rendered 2D map for a real-time tactics game, cinematic neon-noir style: a gothic art-deco city on a snowy winter night. Deep blue-teal moonlit shadows, warm amber lit windows and street lamps, glowing pink, cyan and violet neon shop signs reflecting on wet ploughed streets, fresh snow on roofs, ledges and pavements. Buildings: dark stone and brick gothic tenements and a stepped art-deco tower with rooftop statues and a water tank, black riveted steel elevated railway viaduct on pillars with truss railings, a steel arch bridge over a black canal with ice at its stone quay edges, iron lamp posts, fire escapes. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: cold moonlight from the top-left, soft shadows to the bottom-right, pools of warm and coloured light. Keep every building, street, canal bank, bridge and the railway exactly where the attached render has it; keep the open snowy areas open. No people, no vehicles on the streets, no logos, no labels, no UI, no frame, no border, no watermark; the only words are the small neon shop signs already in the render. Landscape image, aspect ratio 3:2.
```

### 2. Style frame B - gritty realistic
Save as: `ironward/style-b.png`
Reference: `artsrc/maps/ironward/build/styleframe-src.png`

```
A realistic, gritty pre-rendered 2D game map seen from above, like a detailed miniature diorama photographed at night: an old gothic industrial city in deep winter. Soot-stained brick and grey stone tenements with steep slate roofs half covered in snow, pointed pinnacles, chimneys, rusty fire escapes and water tanks, a tall stepped stone tower with weathered copper statues on its roof, a black riveted steel elevated railway viaduct on pillars, a steel arch bridge over a dark icy canal with granite quay walls, slushy ploughed streets with tyre tracks, dirty snow banks, iron street lamps with warm glow, a few small neon shop signs. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: pale blue moonlight from the top-left, soft shadows to the bottom-right, warm lamplight pools. Keep every building, street, canal bank, bridge and the railway exactly where the attached render has it; keep the open snowy areas open. No people, no vehicles on the streets, no logos, no labels, no UI, no frame, no border, no watermark; the only words are the small neon shop signs already in the render. Landscape image, aspect ratio 3:2.
```

### 3. Style frame C - painted graphic novel
Save as: `ironward/style-c.png`
Reference: `artsrc/maps/ironward/build/styleframe-src.png`

```
A hand-painted 2D map for a real-time tactics game in a moody graphic-novel style: bold shapes, strong dark ink-like shadows, visible brush strokes, a limited palette of midnight blue, slate grey and snow white with accents of amber window light and hot pink, cyan and violet neon. Scene: a gothic walled city on a snowy night: stone tenements with steep snowy roofs, pinnacles and gargoyle-like statues, a stepped tower with statues on top, a black steel elevated railway on pillars, a steel arch bridge over a black icy canal, iron lamp posts, glowing shop signs. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: cold moonlight from the top-left, shadows to the bottom-right. Keep every building, street, canal bank, bridge and the railway exactly where the attached render has it; keep the open snowy areas open. No people, no vehicles on the streets, no logos, no labels, no UI, no frame, no border, no watermark; the only words are the small neon shop signs already in the render. Landscape image, aspect ratio 3:2.
```

### 4. Style frame D - crisp detailed classic
Save as: `ironward/style-d.png`
Reference: `artsrc/maps/ironward/build/styleframe-src.png`

```
A highly detailed hand-painted 2D game map in the pre-rendered style of classic tactics games from around 2000: sharp, clean, richly textured, every brick, slate, cobblestone, rivet and window frame readable, like a detailed painted diorama at night. Scene: a gothic art-deco city in winter: dark stone and brick tenements with ornate cornices, steep slate roofs under snow, pinnacles, chimneys and water tanks, a stepped tower with two statues on the roof, a black steel elevated railway viaduct with truss railings on steel pillars, a steel arch bridge over a dark canal with granite quays and ice at the edges, ploughed cobbled streets with snow banks, iron lamp posts, small glowing neon shop signs. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: blue moonlight from the top-left, crisp shadows to the bottom-right, warm windows and lamps. Keep every building, street, canal bank, bridge and the railway exactly where the attached render has it; keep the open snowy areas open. No people, no vehicles on the streets, no logos, no labels, no UI, no frame, no border, no watermark; the only words are the small neon shop signs already in the render. Landscape image, aspect ratio 3:2.
```

## Map textures

### 5. Fresh snow
Save as: `ironward/tex-snow.png`

```
A seamless, tileable square texture seen from straight above, painted in the style of the attached map: fresh trodden snow on the ground at night, soft drifts, a few footprints and tyre ruts, tiny sparkles, cool blue-white moonlit tones. Even lighting from the top-left, no strong shadows, no perspective, no objects, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 6. Ploughed street slush
Save as: `ironward/tex-slush.png`

```
A seamless, tileable square texture seen from straight above, painted in the style of the attached map: a ploughed city street at night, dark wet asphalt and old cobbles showing through grey-brown slush, tyre tracks, puddles reflecting a little warm lamplight, thin streaks of snow. Even lighting, no strong shadows, no perspective, no objects, no road markings, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 7. Snowy cobbled plaza
Save as: `ironward/tex-plaza.png`

```
A seamless, tileable square texture seen from straight above, painted in the style of the attached map: a large old cobbled square at night, grey granite setts swept in patches, snow lying in the joints and in soft drifts, cool blue moonlit tones. Even lighting, no strong shadows, no perspective, no objects, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 8. Canal quay stone
Save as: `ironward/tex-quay.png`

```
A seamless, tileable square texture seen from straight above, painted in the style of the attached map: big dressed granite blocks of an old canal quay, dark and wet, frost and snow in the joints, iron mooring rings. Even lighting, no strong shadows, no perspective, no objects, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 9. Gothic stone facade
Save as: `ironward/tex-facade-stone.png`

```
A seamless, tileable square texture of a building wall seen straight on, painted in the style of the attached map: dark grey gothic stone facade at night, four storeys of tall narrow pointed-arch windows (some glowing warm amber, most dark), carved stone frames, string courses, soot streaks, a little snow on the window ledges. Flat front view, no perspective, edges must tile seamlessly left-right and top-bottom. No text, no frame. Square image, aspect ratio 1:1.
```

### 10. Brick tenement facade
Save as: `ironward/tex-facade-brick.png`

```
A seamless, tileable square texture of a building wall seen straight on, painted in the style of the attached map: soot-darkened red-brown brick tenement facade at night, four storeys of tall sash windows with stone lintels (some glowing warm amber, most dark), a rusty iron fire escape fragment, snow on the ledges. Flat front view, no perspective, edges must tile seamlessly left-right and top-bottom. No text, no frame. Square image, aspect ratio 1:1.
```

### 11. Limestone facade
Save as: `ironward/tex-facade-limestone.png`

```
A seamless, tileable square texture of a building wall seen straight on, painted in the style of the attached map: pale limestone art-deco facade at night, four storeys of tall windows between fluted vertical piers, geometric carved panels, some windows glowing warm amber, snow on the ledges, cool moonlit tones. Flat front view, no perspective, edges must tile seamlessly left-right and top-bottom. No text, no frame. Square image, aspect ratio 1:1.
```

### 12. Snowy slate roof
Save as: `ironward/tex-roof-snow.png`

```
A seamless, tileable square texture seen from straight above, painted in the style of the attached map: a dark slate roof at night mostly covered by snow, rows of slates showing through where the snow has slid or melted, cool blue moonlit tones. Even lighting, no strong shadows, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 13. Riveted steel
Save as: `ironward/tex-steel.png`

```
A seamless, tileable square texture seen straight on, painted in the style of the attached map: black painted riveted steel plates and girders of an old elevated railway, rows of rivets, rust streaks, frost and a little snow on the top edges. Even lighting, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```
