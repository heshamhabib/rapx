# RedAlert Project X - Monument City painted map prompts (ChatGPT, IDEA-28)

Style frames repaint the same Blender crop (`artsrc/maps/monument/build/styleframe-src.png`, around the Capitol). Output: `assets/maps/monument/`.

    python3 artsrc/prompts/generate_images.py --prompts monument-prompts.md --category maps

All buildings and names are generic or public landmarks; nothing copies an existing game's art.

## Map style frames

### 1. Style frame A - crisp detailed classic
Save as: `monument/style-a.png`
Reference: `artsrc/maps/monument/build/styleframe-src.png`

```
A highly detailed hand-painted 2D game map in the pre-rendered style of classic tactics games from around 2000: sharp, clean, richly textured, every brick, window, cornice and car readable, like a detailed painted diorama. Scene: part of an imaginary American city on a sunny summer day: the US Capitol in white marble with its dome and wings on a green lawn, a stone plaza in front, city blocks of red-brick and brownstone walk-ups with fire escapes and rooftop water tanks, limestone office blocks with ornate cornices, dark asphalt avenues with lane markings, yellow taxis and parked cars, light concrete sidewalks, lamp posts. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: bright midday summer sun from the top-left, crisp shadows to the bottom-right, natural colours. Keep every building, street and the plaza exactly where the attached render has it; keep the open plaza and lawns open. No people, no tanks, no text, no logos, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

### 2. Style frame B - warm golden afternoon
Save as: `monument/style-b.png`
Reference: `artsrc/maps/monument/build/styleframe-src.png`

```
A rich painterly pre-rendered 2D map for a real-time tactics game, warm and inviting, like a lovingly painted miniature city. Scene: part of an imaginary American city on a sunny summer day: the US Capitol in white marble with its dome and wings on a green lawn, a stone plaza in front, city blocks of red-brick and brownstone walk-ups with fire escapes and rooftop water tanks, limestone office blocks with ornate cornices, dark asphalt avenues with lane markings, yellow taxis and parked cars, light concrete sidewalks, lamp posts. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: golden late-afternoon sun from the top-left, long warm shadows to the bottom-right, honey-coloured stone and warm brick. Keep every building, street and the plaza exactly where the attached render has it; keep the open plaza and lawns open. No people, no tanks, no text, no logos, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

### 3. Style frame C - realistic aerial
Save as: `monument/style-c.png`
Reference: `artsrc/maps/monument/build/styleframe-src.png`

```
A photorealistic 2D game map that looks like a crisp aerial photograph of a real American downtown, every detail sharp and believable. Scene: part of an imaginary American city on a sunny summer day: the US Capitol in white marble with its dome and wings on a green lawn, a stone plaza in front, city blocks of red-brick and brownstone walk-ups with fire escapes and rooftop water tanks, limestone office blocks with ornate cornices, dark asphalt avenues with lane markings, yellow taxis and parked cars, light concrete sidewalks, lamp posts. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: clear summer day, sun from the top-left, soft realistic shadows to the bottom-right, true colours. Keep every building, street and the plaza exactly where the attached render has it; keep the open plaza and lawns open. No people, no tanks, no text, no logos, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

### 4. Style frame D - bright stylised
Save as: `monument/style-d.png`
Reference: `artsrc/maps/monument/build/styleframe-src.png`

```
A bright, stylised hand-painted 2D map for a real-time strategy game, clean shapes and saturated cheerful colours, very readable at a glance, like a modern strategy game's city map. Scene: part of an imaginary American city on a sunny summer day: the US Capitol in white marble with its dome and wings on a green lawn, a stone plaza in front, city blocks of red-brick and brownstone walk-ups with fire escapes and rooftop water tanks, limestone office blocks with ornate cornices, dark asphalt avenues with lane markings, yellow taxis and parked cars, light concrete sidewalks, lamp posts. Camera: straight down from above; tall things lean up the picture so the south walls are visible, exactly like the attached render. Light: sunny summer day, sun from the top-left, clean shadows to the bottom-right, vivid blue-green and warm colours. Keep every building, street and the plaza exactly where the attached render has it; keep the open plaza and lawns open. No people, no tanks, no text, no logos, no labels, no UI, no frame, no border, no watermark. Landscape image, aspect ratio 3:2.
```

## Map textures

Rich lawn textures for the build areas (user feedback 2026-11-21: the flat render grass looked poor; references were
detailed tactics/RTS games with tufted, multi-tone grass and wildflowers). Seen from straight above, flat (bases are
built on them), seamless.

### 5. Lush meadow grass
Save as: `monument/tex-grass-lush.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in a rich, realistic HD game style: a lush summer meadow, dense grass made of many small individual tufts and blades in several greens from deep green to fresh yellow-green, each tuft casting a tiny soft shadow to the bottom-right so the grass has depth, a few clover patches, scattered tiny wildflowers (red, yellow and white dots), no paths, no rocks, no trees, no objects. Bright summer sun from the top-left. Even overall brightness, no vignette, no perspective, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 6. Dry summer grass
Save as: `monument/tex-grass-dry.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in a rich, realistic HD game style: sun-dried late-summer grass, dense small tufts and blades in straw yellow, olive and pale green, some greener clumps, a few small bare dusty earth spots, tiny white and yellow wildflowers, each tuft with a tiny soft shadow to the bottom-right. Bright sun from the top-left. Even overall brightness, no vignette, no perspective, no rocks, no paths, no objects, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```

### 7. Short park lawn
Save as: `monument/tex-grass-lawn.png`

```
A seamless, tileable square texture seen from straight above, hand-painted in a rich, realistic HD game style: a healthy short city-park lawn, dense fine grass in varied greens with visible individual blades and small clumps, soft light and dark patches, a little clover, a few daisies, each clump with a tiny soft shadow to the bottom-right. Bright summer sun from the top-left. Even overall brightness, no vignette, no perspective, no mowing stripes, no paths, no objects, edges must tile seamlessly. No text, no frame. Square image, aspect ratio 1:1.
```
