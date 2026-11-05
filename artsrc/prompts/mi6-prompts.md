# RedAlert Project X - MI6 building prompt (England only)

Generate with: `python3 artsrc/prompts/generate_images.py --prompts mi6-prompts.md --only mi6`
(the Construction Yard style image is attached automatically). Then copy
`assets/buildings/mi6.png` to `artsrc/buildings/src/mi6.png` and run `artsrc/buildings/build_all.py`.

## Buildings

### 1. MI6 Headquarters (2x2)
Save as: `mi6.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. MI6 Headquarters: a British secret intelligence headquarters, a stepped, terraced postmodern block of cream-coloured stone and dark green-tinted glass bands, rising in tiers to a flat roof crowded with satellite dishes, radio masts and a small rooftop radar; a secure gated entrance with bollards at the front and a small helipad on one lower terrace. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 2 square-tile footprint (width 2, depth 2). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the roof terrace edges and the helipad ring) in flat pure bright green (#00FF00); the glass is dark blue-grey tinted, not green; use no other green anywhere on the object. Damaged copy: blackened scorch marks, shattered window bands, cracked and broken stone panels, a partly collapsed top tier, bent and broken satellite dishes and masts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no flag, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```
