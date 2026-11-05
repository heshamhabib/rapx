# RedAlert Project X - AI art prompts (ChatGPT or Gemini)

Prompts for every building, unit and environment object. Paste one prompt per image.

**How to use**

1. Start a new ChatGPT (or Gemini) chat for each object, paste the prompt and generate. ChatGPT follows the two-version building prompt best.
2. If it looks right, download it and rename it to the **Save as** name. Put buildings in `~/Downloads/project_x/buildings/`, units in `~/Downloads/project_x/units/` and environment art in `~/Downloads/project_x/environment/`.
3. Each building prompt makes **one wide image with both versions**: intact on the left, battle-damaged on the right. Reject it if the two copies differ in angle or size, touch each other, or there is a line between them.
4. Reject an image if it changes the camera angle, adds ground or grass, has a non-magenta/white background, or uses green outside the team-colour areas. Just regenerate.
5. Keep everything in one consistent style: attach the approved Construction Yard image (`artsrc/buildings/src/fact-chatgpt.png`, or `Intact and Ruined Industrial Base.png` in Downloads) to each new chat and add: *"Match the style, camera angle, lighting and level of detail of the attached image, but draw the building described below."*
6. File names: name each download after its **Save as** name (for example `weap.png`), or tell me which building each file is.

**What happens next (my side)**

- **Buildings and environment** are used directly: I remove the magenta background, scale them to the footprint, add player colours (the green areas) and make the build-up animation and sidebar icons.
- **Units, aircraft, ships and infantry** turn in 32 directions, so one picture is not enough. Feed each image into a free image-to-3D tool (for example Tripo AI, Meshy or Hunyuan3D) and download the result as `.glb` with the same name. Infantry: also upload the model to Mixamo (free) for a skeleton and walk / shoot / die animations. My Blender pipeline renders every direction and animation from the 3D files.

Team colour: the pure green (#00FF00) areas are replaced with each player's colour in game, so keep green only where the prompt says.

## Buildings

Wide 2:1 images, intact (left) + damaged (right). Footprints are in map cells (width x depth).

### 1. Construction Yard (3x4)
Save as: `fact.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Construction Yard: the main base building, a large fortified assembly plant with a big crane arm, landing pad and folded-down vehicle bay doors. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 4 square-tile footprint (width 3, depth 4). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (roof panels and the crane arm) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the crane arm snapped and hanging, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 2. Power Plant (2x3)
Save as: `powr.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Power Plant: compact generator hall with two smoking cooling stacks, transformers and thick power cables. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 3 square-tile footprint (width 2, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the roof trim and cooling stack bands) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, one cooling stack cracked and leaning, sparking cables, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 3. Advanced Power Plant (3x3)
Save as: `apwr.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. An Advanced Power Plant: larger fusion-style generator complex with three glowing reactor cores visible through vents, cooling towers and transformer yard. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 3 square-tile footprint (width 3, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (roof panels and stack bands) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, one reactor vent blown open with an orange glow, sparking transformers, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 4. Ore Refinery (3x4)
Save as: `proc.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. An Ore Refinery: industrial ore-processing plant with a truck unloading dock at the front, conveyor, crushers and two storage silos. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 4 square-tile footprint (width 3, depth 4). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the roof stripes and silo bands) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, a silo punctured and leaking ore, the conveyor broken, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 5. Silo (1x1)
Save as: `silo.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. An Ore Silo: a single squat armoured storage tank with gauges and a hatch. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (a band around the top) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 6. War Factory (3x3)
Save as: `weap.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A War Factory: large vehicle production hall with a wide armoured roll-up door at the front, gantry cranes and vents on the roof. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 3 square-tile footprint (width 3, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (roof stripes and door frame) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the big vehicle door buckled and half torn off, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 7. Service Depot (3x3)
Save as: `fix.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Service Depot: open repair pad with a central lift platform, robotic repair arms and tool racks around it. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 3 square-tile footprint (width 3, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the corner posts of the pad) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 8. Radar Dome (2x3)
Save as: `dome.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Radar Dome: radar station with a large white geodesic radome on a fortified bunker base, antennas and satellite dishes. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 3 square-tile footprint (width 2, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the base trim) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the radome shell holed and cracked open, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 9. Helipad (2x3)
Save as: `hpad.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Helipad: raised armoured helicopter landing pad with an H marking, lights and a small control booth. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 3 square-tile footprint (width 2, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the landing circle markings) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the landing pad cracked and lights smashed, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 10. Airfield (3x2)
Save as: `afld.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. An Airfield: short runway with an arched aircraft hangar, fuel tanks and a radio mast. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 2 square-tile footprint (width 3, depth 2). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (runway markings and hangar roof stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the hangar roof caved in, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 11. Allied Barracks (2x3)
Save as: `tent.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. Allied Barracks: modern military training barracks, modular prefab buildings with a flagpole and sandbag entrance. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 3 square-tile footprint (width 2, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the roof stripes and flag) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 12. Soviet Barracks (2x3)
Save as: `barr.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. Soviet Barracks: heavy concrete barracks bunker with a watchtower, banner and barbed wire. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 3 square-tile footprint (width 2, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the roof stripes and banner) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 13. Kennel (1x1)
Save as: `kenn.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Kennel: small reinforced dog kennel with a fenced run. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the roof) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 14. Naval Yard (3x3)
Save as: `syrd.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Naval Yard: floating shipyard dock with gantry cranes, built over water (draw the water area inside the dock in dark blue). View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 3 square-tile footprint (width 3, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (dock edge markings and crane) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, a gantry crane collapsed, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 15. Sub Pen (3x3)
Save as: `spen.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Sub Pen: armoured submarine pen with a covered bay opening onto water (draw water inside the pen in dark blue). View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 3 square-tile footprint (width 3, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the pen roof stripes) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the pen roof partly collapsed, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 16. Allied Tech Center (2x3)
Save as: `atek.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. An Allied Tech Center: futuristic research laboratory with glass domes, satellite uplink and server towers. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 3 square-tile footprint (width 2, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (roof panels) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 17. Soviet Tech Center (3x3)
Save as: `stek.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Soviet Tech Center: massive secret research institute with reactor towers, Tesla antennas and thick armoured walls. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 3 x 3 square-tile footprint (width 3, depth 3). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (roof panels) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 18. Chronosphere (2x2)
Save as: `pdox.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Chronosphere: superweapon with a glowing blue time-distortion sphere held by curved metal arms above a high-tech platform. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 2 square-tile footprint (width 2, depth 2). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the base ring) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the sphere flickering with cracked emitter arms, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 19. Iron Curtain (2x2)
Save as: `iron.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. An Iron Curtain: superweapon with a huge red-glowing energy emitter dish on a massive armoured pylon. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 2 square-tile footprint (width 2, depth 2). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the base ring) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the emitter dish cracked and sparking, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 20. Missile Silo (2x1)
Save as: `mslo.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Strategic Launch Facility for a fictional sci-fi strategy game: a low armoured concrete bunker with two large sliding hatch doors set into its flat roof, slightly open, a glowing sci-fi rocket nose cone (sleek, white, futuristic) peeking out, warning lights and antenna masts around it. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 1 square-tile footprint (width 2, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the hatch rim) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 21. Gap Generator (1x1)
Save as: `gap.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Gap Generator: tall slim tower with a rotating cloaking-field emitter at the top. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the base) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 22. Pillbox (1x1)
Save as: `pbox.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Pillbox: small round concrete bunker with a machine-gun slit. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the roof) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 23. Camo Pillbox (1x1)
Save as: `hbox.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Camouflaged Pillbox: low bunker covered in camouflage netting and foliage (use brown and khaki, not green). View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (a small roof hatch) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 24. Turret (1x1)
Save as: `gun.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Turret: armoured gun emplacement with a rotating cannon turret on a concrete base, cannon pointing toward the bottom-right. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (turret top plate) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the cannon barrel bent, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 25. AA Gun (1x1)
Save as: `agun.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. An AA Gun: anti-aircraft emplacement with twin rapid-fire cannons angled up toward the sky. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the gun base) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, one cannon barrel snapped, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 26. Flame Tower (1x1)
Save as: `ftur.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Flame Tower: squat armoured tower with a flamethrower nozzle and fuel tanks. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the tower band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 27. Tesla Coil (1x1)
Save as: `tsla.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A Tesla Coil: tall metal coil tower with crackling blue electric arcs at the top. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 1 x 1 square-tile footprint (width 1, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (the base ring) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, the coil sparking erratically with broken rings, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```

### 28. SAM Site (2x1)
Save as: `sam.png`

```
Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. A SAM Site: surface-to-air missile launcher with four missiles on a rotating rail, in a sandbagged pit. View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, the front of the building faces the bottom of the image, no perspective distortion. The building's base covers a 2 x 1 square-tile footprint (width 2, depth 1). Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. Paint the team-colour areas (launcher rails) in flat pure bright green (#00FF00); use no other green anywhere on the object. Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts, one missile missing and the rail bent, exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; its surviving team-colour areas stay green. Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. Wide image, aspect ratio 2:1.
```


## Vehicles

Model reference images for image-to-3D. Save the 3D result as `<name>.glb`.

### 29. Light Tank
Save as: `1tnk.png  ->  1tnk.glb`

```
3D model reference image of a single tank for a real-time strategy game. A fast light tank with a small turret and slim 90mm gun. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole tank visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (side skirt stripes and turret band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 30. Medium Tank
Save as: `2tnk.png  ->  2tnk.glb`

```
3D model reference image of a single tank for a real-time strategy game. A modern main battle tank (Leopard 2 / Abrams class) with an angular turret and 120mm gun. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole tank visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (side skirt stripes and turret band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 31. Heavy Tank
Save as: `3tnk.png  ->  3tnk.glb`

```
3D model reference image of a single tank for a real-time strategy game. A heavy Soviet tank with a large rounded turret and twin 105mm cannons. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole tank visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (side skirt stripes and turret band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 32. Mammoth Tank
Save as: `4tnk.png  ->  4tnk.glb`

```
3D model reference image of a single tank for a real-time strategy game. A huge Mammoth Tank: four tracks, twin heavy cannons and twin missile pods on the turret. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole tank visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (side skirt stripes and turret band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 33. Artillery
Save as: `arty.png  ->  arty.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A self-propelled artillery vehicle with a long-range howitzer. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (barrel band and hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 34. V2 Rocket Launcher
Save as: `v2rl.png  ->  v2rl.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A truck-mounted ballistic rocket launcher carrying one large rocket on an erector. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (rocket fins and cab stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 35. Ore Truck
Save as: `harv.png  ->  harv.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A large armoured ore harvester truck with a front scoop and a big ore bin. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (cab roof and bin stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 36. Mobile Construction Vehicle
Save as: `mcv.png  ->  mcv.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A Mobile Construction Vehicle: big multi-axle armoured truck carrying a folded construction yard and crane. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (roof panels) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 37. Ranger
Save as: `jeep.png  ->  jeep.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A fast armoured 4x4 scout vehicle with a roof-mounted machine gun. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hood stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 38. Armored Personnel Carrier
Save as: `apc.png  ->  apc.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A tracked armoured personnel carrier with a small machine-gun turret and rear troop door. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull side stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 39. Minelayer
Save as: `mnly.png  ->  mnly.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A tracked minelaying vehicle with a mine-dispensing chute at the back. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 40. Supply Truck
Save as: `truk.png  ->  truk.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A military supply truck with a covered cargo bed full of crates. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (cargo cover stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 41. Mobile Gap Generator
Save as: `mgg.png  ->  mgg.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A tracked vehicle carrying a tall rotating cloaking-field emitter. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 42. Mobile Radar Jammer
Save as: `mrj.png  ->  mrj.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A tracked electronic-warfare vehicle with a large jamming antenna array. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 43. Tesla Tank
Save as: `ttnk.png  ->  ttnk.glb`

```
3D model reference image of a single tank for a real-time strategy game. A tank with a Tesla coil weapon instead of a cannon, blue electric glow. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole tank visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 44. Mobile Flak
Save as: `ftrk.png  ->  ftrk.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A truck with a rapid-fire anti-aircraft flak cannon on the back. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (cab stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 45. Demolition Truck
Save as: `dtrk.png  ->  dtrk.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A heavy armoured truck carrying a large sealed sci-fi energy core container with hazard-stripe warning markings and blinking lights. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (cab stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 46. Chrono Tank
Save as: `ctnk.png  ->  ctnk.glb`

```
3D model reference image of a single tank for a real-time strategy game. A futuristic hover-style tank with missile pods and blue chrono-shift emitters. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole tank visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 47. MAD Tank
Save as: `qtnk.png  ->  qtnk.glb`

```
3D model reference image of a single tank for a real-time strategy game. A tank carrying a big seismic shockwave generator instead of a turret. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole tank visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 48. Phase Transport
Save as: `stnk.png  ->  stnk.glb`

```
3D model reference image of a single vehicle for a real-time strategy game. A stealth armoured transport with angular faceted panels and a missile launcher. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole vehicle visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (hull stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```


## Aircraft

### 49. MiG Attack Plane
Save as: `mig.png  ->  mig.glb`

```
3D model reference image of a single jet aircraft for a real-time strategy game. A Soviet MiG-style ground-attack jet with missiles under the wings, top view emphasised. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole jet aircraft visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (tail fin and wing tips) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 50. Yak Attack Plane
Save as: `yak.png  ->  yak.glb`

```
3D model reference image of a single propeller aircraft for a real-time strategy game. A Yak-style propeller ground-attack plane with wing machine guns. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole propeller aircraft visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (tail fin and wing tips) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 51. Chinook
Save as: `tran.png  ->  tran.glb`

```
3D model reference image of a single transport helicopter for a real-time strategy game. A twin-rotor Chinook-style transport helicopter. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole transport helicopter visible and centred, orthographic, no perspective distortion. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (tail band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 52. Longbow
Save as: `heli.png  ->  heli.glb`

```
3D model reference image of a single attack helicopter for a real-time strategy game. An Apache Longbow-style attack helicopter with Hellfire missiles. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole attack helicopter visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (tail band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 53. Black Hawk
Save as: `mh60.png  ->  mh60.glb`

```
3D model reference image of a single helicopter for a real-time strategy game. A Black Hawk-style utility helicopter with door guns. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole helicopter visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (tail band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```


## Ships

The game shows ships on water from above; the reference image only needs the ship itself.

### 54. Submarine
Save as: `ss.png  ->  ss.glb`

```
3D model reference image of a single submarine for a real-time strategy game. A Soviet attack submarine, surfaced, long dark hull. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole submarine visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (conning tower band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 55. Missile Submarine
Save as: `msub.png  ->  msub.glb`

```
3D model reference image of a single submarine for a real-time strategy game. A large Soviet missile submarine with vertical launch hatches on the deck. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole submarine visible and centred, orthographic, no perspective distortion. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (conning tower band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 56. Destroyer
Save as: `dd.png  ->  dd.glb`

```
3D model reference image of a single warship for a real-time strategy game. A modern destroyer warship with a forward gun turret and anti-sub launchers. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole warship visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (funnel band and deck stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 57. Cruiser
Save as: `ca.png  ->  ca.glb`

```
3D model reference image of a single warship for a real-time strategy game. A large cruiser warship with two heavy gun turrets. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole warship visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (funnel band and deck stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 58. Transport
Save as: `lst.png  ->  lst.glb`

```
3D model reference image of a single landing craft for a real-time strategy game. An amphibious landing ship with a front ramp. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole landing craft visible and centred, orthographic, no perspective distortion. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (deck stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```

### 59. Gunboat
Save as: `pt.png  ->  pt.glb`

```
3D model reference image of a single patrol boat for a real-time strategy game. A fast patrol gunboat with a deck cannon. View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole patrol boat visible and centred, orthographic, no perspective distortion. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. Neutral even studio lighting, no dramatic shadows. Paint the team-colour areas (deck stripe) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image.
```


## Infantry

Character reference images (A-pose) for image-to-3D and Mixamo rigging.

### 60. Rifle Infantry
Save as: `e1.png  ->  e1.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A modern rifleman with assault rifle, helmet and body armour. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (shoulder patches and helmet band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 61. Grenadier
Save as: `e2.png  ->  e2.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A Soviet grenadier with a bag of hand grenades and a heavy coat. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (shoulder patches and helmet band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 62. Rocket Soldier
Save as: `e3.png  ->  e3.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A soldier carrying a shoulder-fired rocket launcher. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (shoulder patches and helmet band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 63. Flame Infantry
Save as: `e4.png  ->  e4.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A flamethrower trooper with fuel tanks on the back and a fire-resistant suit. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (shoulder patches and tank straps) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 64. Engineer
Save as: `e6.png  ->  e6.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A combat engineer with a tool bag, hard hat and utility vest. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (vest panels and helmet band) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 65. Tanya
Save as: `e7.png  ->  e7.glb`

```
3D character reference image of a single soldier for a real-time strategy game. Tanya, an elite female commando with dual pistols, tactical gear, confident pose. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (armband) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 66. Medic
Save as: `medi.png  ->  medi.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A field medic with a medical backpack (red cross on white). Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (armband) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 67. Mechanic
Save as: `mech.png  ->  mech.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A field mechanic with a wrench and tool belt. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (armband) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 68. Thief
Save as: `thf.png  ->  thf.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A stealthy thief in dark clothing with a loot bag. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (armband) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 69. Shock Trooper
Save as: `shok.png  ->  shok.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A Soviet shock trooper in heavy armour with a backpack Tesla gun, blue electric glow. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (shoulder pads) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 70. Spy
Save as: `spy.png  ->  spy.glb`

```
3D character reference image of a single soldier for a real-time strategy game. A spy in a dark suit and trench coat. Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. Neutral even studio lighting. Paint the team-colour areas (tie) in flat pure bright green (#00FF00); use no other green anywhere on the object. Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4).
```

### 71. Attack Dog
Save as: `dog.png  ->  dog.glb`

```
3D model reference image of a single animal for a real-time strategy game. A muscular military attack dog (German shepherd) in a tactical harness, standing side view. Whole animal visible, orthographic, neutral even studio lighting. Isolated on a flat plain white background, no ground shadow, no text, no watermark. Square image.
```


## Environment

Sheets with four variants each; I cut them apart.

### 72. Pine trees (set of 4)
Save as: `tree-pine.png`

```
Game asset for a top-down real-time strategy game. A sheet of four different single pine trees, evenly spaced in a 2x2 grid, each tree isolated. View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees, centred, whole object visible. Photorealistic, highly detailed, natural colours. Lighting: sun from the top-left, short soft shadow to the bottom-right. Isolated on a flat, solid magenta (#FF00FF) background: no ground, no text, no watermark. Square image.
```

### 73. Broadleaf trees (set of 4)
Save as: `tree-oak.png`

```
Game asset for a top-down real-time strategy game. A sheet of four different single broadleaf (oak / maple) trees, evenly spaced in a 2x2 grid, each tree isolated. View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees, centred, whole object visible. Photorealistic, highly detailed, natural colours. Lighting: sun from the top-left, short soft shadow to the bottom-right. Isolated on a flat, solid magenta (#FF00FF) background: no ground, no text, no watermark. Square image.
```

### 74. Dead trees (set of 4)
Save as: `tree-dead.png`

```
Game asset for a top-down real-time strategy game. A sheet of four different dead, leafless trees, evenly spaced in a 2x2 grid. View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees, centred, whole object visible. Photorealistic, highly detailed, natural colours. Lighting: sun from the top-left, short soft shadow to the bottom-right. Isolated on a flat, solid magenta (#FF00FF) background: no ground, no text, no watermark. Square image.
```

### 75. Gold ore (4 sizes)
Save as: `ore.png`

```
Game asset for a top-down real-time strategy game. A sheet of four patches of glittering gold ore crystals on the ground, from a small sparse patch to a large dense pile, evenly spaced in a 2x2 grid. View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees, centred, whole object visible. Photorealistic, highly detailed, natural colours. Lighting: sun from the top-left, short soft shadow to the bottom-right. Isolated on a flat, solid magenta (#FF00FF) background: no ground, no text, no watermark. Square image.
```

### 76. Gems (4 sizes)
Save as: `gems.png`

```
Game asset for a top-down real-time strategy game. A sheet of four patches of sparkling multicoloured gem crystals, from a small sparse patch to a large dense cluster, evenly spaced in a 2x2 grid. View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees, centred, whole object visible. Photorealistic, highly detailed, natural colours. Lighting: sun from the top-left, short soft shadow to the bottom-right. Isolated on a flat, solid magenta (#FF00FF) background: no ground, no text, no watermark. Square image.
```

### 77. Boulders (set of 4)
Save as: `rocks.png`

```
Game asset for a top-down real-time strategy game. A sheet of four different large boulders / rock outcrops, evenly spaced in a 2x2 grid. View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees, centred, whole object visible. Photorealistic, highly detailed, natural colours. Lighting: sun from the top-left, short soft shadow to the bottom-right. Isolated on a flat, solid magenta (#FF00FF) background: no ground, no text, no watermark. Square image.
```


## Not included (on purpose)

- **Walls and fences** (sandbags, wire, concrete) join up in 16 shapes; I'll build those from textures.
- **Civilian buildings, campaign-only units (ants, zombies)** and **sidebar icons**: icons are rendered from the art above; the rest can come later.

