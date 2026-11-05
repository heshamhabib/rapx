# Mixamo checklist (3D soldiers)

Pilot: **e1** (Rifle Infantry) and **e3** (Rocket Soldier). Upload files are made by `prep_mixamo.py` into
`artsrc/units/soldiers/upload/<id>.fbx`. Downloads go to `artsrc/units/soldiers/anim/<id>/<name>.fbx`.

## 1. Upload and rig (once per soldier)

1. Go to <https://www.mixamo.com> and sign in (free Adobe account).
2. Click **Upload Character** and drop `upload/<id>.fbx`.
3. Mixamo shows the auto-rigger: place the markers on **chin, wrists, elbows, knees, groin**.
   Skeleton LOD: **Standard Skeleton (65)**. Click **Next** until it finishes.

## 2. Download each animation

For every row: search the name, click the animation, set the options, **Download**, and save the file under the
**Save as** name into `artsrc/units/soldiers/anim/<id>/`.

Download options for every animation:

| Option | Value |
|---|---|
| Format | FBX Binary (.fbx) |
| Skin | **With Skin** |
| Frames per Second | 30 |
| Keyframe Reduction | none |

Tick **In Place** whenever the animation has that checkbox (run, crawl). It keeps the soldier on the spot; the
game moves him.

| Save as | Search Mixamo for | Notes |
|---|---|---|
| `idle.fbx` | Rifle Idle | relaxed stand (e3: same) |
| `aim.fbx` | Rifle Aiming Idle | alert / guard stance |
| `run.fbx` | Rifle Run | **In Place** |
| `fire.fbx` | Firing Rifle | e3: try "Shoulder Rifle Fire" / "Standing Aim Overdraw"; any rifle firing pose works, I add the rocket |
| `look.fbx` | Rifle Look Around (or "Idle Looking Around") | fidget idle |
| `toprone.fbx` | Standing To Prone (or "Rifle Prone" / "Prone Start") | dive to the ground |
| `crawl.fbx` | Prone Forward (or "Crawl") | **In Place** |
| `pronefire.fbx` | Prone Fire (or "Prone Idle" if no fire pose) | lying firing |
| `death1.fbx` | Death From The Front (or "Rifle Death") | shot, falls |
| `death2.fbx` | Death From Front Headshot / "Flying Back Death" | blown back |

If a name is missing, pick the closest one; just keep the **Save as** names.

## 3. Tell me when the files are in place

I import them in Blender, colour the model from the concept views, and render all 32 directions.
