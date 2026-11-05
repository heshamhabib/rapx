#!/usr/bin/env python3
"""
Writes infantry-anim-prompts.md: ChatGPT prompts for every animation frame an infantry sprite needs
(stand, guard, run, shoot, dive/get up, crawl, prone shoot, idles, deaths, parachute).
Trimmed 2026-10-27 to cut generation cost: no hurt (needs a new trait) or corpse sheets, 2 drawn
deaths per soldier (reused for the other death sequences), parachute for the Rifle Infantry only.

Each prompt attaches the soldier's approved concept image (assets/units/<id>.png) so every sheet shows
the same soldier. Moving animations are drawn in 5 directions (S, SW, W, NW, N); SE, E and NE are the
mirror images of SW, W and NW. Still poses are one 3-frame sheet per direction.

  python3 make_infantry_anim_prompts.py            # -> infantry-anim-prompts.md
  python3 generate_images.py --prompts infantry-anim-prompts.md --category units --only e1/

Frames come out as a grid on one image, read left to right, top to bottom; each sheet's "Grid:" note
says how many columns x rows to cut it into.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "infantry-anim-prompts.md")

# id, name, concept description, attack (None = unarmed), prone attack, extra action sheet (or None)
SOLDIERS = [
    ("e1", "Rifle Infantry", "a modern rifleman with an assault rifle, helmet and body armour",
     "raises the assault rifle to the shoulder, fires a short burst with a bright muzzle flash and "
     "ejecting brass casings, the rifle kicks back with recoil, then settles back on aim",
     "lying flat, fires the assault rifle in short bursts with muzzle flash and recoil", None),
    ("e2", "Grenadier", "a Soviet grenadier with a bag of hand grenades and a heavy coat",
     "pulls a grenade from the bag, winds up with the throwing arm far back, hurls it overarm in a "
     "big throwing motion (the grenade leaves the hand in the 4th frame), follows through, then "
     "recovers to a ready stance",
     "lying flat, rolls slightly on the side and lobs a grenade with a short underarm throw", None),
    ("e3", "Rocket Soldier", "a soldier carrying a shoulder-fired rocket launcher",
     "kneels, shoulders the rocket launcher and aims, fires with a bright flash at the muzzle and a "
     "big puff of back-blast smoke behind, the launcher jolts with recoil, then lowers it",
     "lying flat with the launcher on the shoulder, fires with flash and back-blast smoke", None),
    ("e4", "Flame Infantry", "a flamethrower trooper with fuel tanks on the back and a fire-resistant suit",
     "braces, points the flamethrower nozzle forward and sprays a long roaring stream of orange fire "
     "that grows then shrinks, small pilot flame at the end",
     "lying flat, sprays a shorter stream of orange fire from the flamethrower", None),
    ("e6", "Engineer", "a combat engineer with a tool bag, hard hat and utility vest",
     None, None, None),
    ("e7", "Tanya", "an elite female commando with dual pistols and tactical gear",
     "aims both pistols forward and fires them alternately, left then right, with muzzle flashes "
     "and recoil, in a confident action-hero stance",
     "lying flat, fires both pistols forward alternately with muzzle flashes", None),
    ("medi", "Medic", "a field medic with a medical backpack (red cross on white)",
     None, None,
     ("heal", "kneels down, opens the medical kit, applies a bandage and a syringe to an unseen "
      "wounded soldier on the ground in front, then stands back up")),
    ("mech", "Mechanic", "a field mechanic with a wrench and tool belt",
     None, None,
     ("repair", "crouches and works on an unseen vehicle in front: swings the wrench, then "
      "uses a small welding torch with bright sparks, then stands back up")),
    ("thf", "Thief", "a stealthy thief in dark clothing with a loot bag", None, None, None),
    ("shok", "Shock Trooper", "a Soviet shock trooper in heavy armour with a backpack Tesla gun and blue electric glow",
     "braces and fires the Tesla gun: the coils charge with blue glow, a jagged bright blue-white "
     "lightning bolt shoots forward, crackles, then fades",
     "lying flat, fires a short blue lightning bolt from the Tesla gun", None),
    ("spy", "Spy", "a spy in a dark suit and trench coat", None, None, None),
]

DOG = ("dog", "Attack Dog", "a muscular military attack dog (German shepherd) in a tactical harness")

DIRS5 = [
    ("s", "south: straight toward the viewer, toward the bottom of the image"),
    ("sw", "south-west: toward the bottom-left of the image"),
    ("w", "west: toward the left edge of the image, seen from the side"),
    ("nw", "north-west: toward the top-left of the image, mostly seen from behind"),
    ("n", "north: straight away from the viewer, toward the top of the image, seen from behind"),
]
DIRS8 = ("north (top of image, seen from behind), north-east, east, south-east / "
         "bottom row: south (toward the viewer), south-west, west, north-west")

REF = ("Draw exactly the same {who} as in the attached reference image ({body}): same face, uniform, "
       "colours, gear{weapon} and the same pure bright green (#00FF00) team-colour patches. ")
CAMERA = ("Camera: classic real-time strategy game view, orthographic, looking down at about 50 degrees, "
          "no perspective distortion; this camera never changes between frames. ")
SHEET = ("Sprite sheet: {n} frames laid out in a grid of "
         "{c} columns x {r} rows, read left to right then top to bottom. ")
CELLS = ("Every frame has exactly the same size and scale, the {who} is centred in its cell with the feet "
         "on the same ground line, with a wide clear gap of background between cells; nothing touches "
         "or crosses a cell border; the whole {who} is visible in every frame. ")
STYLE = ("Highly detailed realistic 3D game render, modern 2026 military gear, physically based materials, "
         "crisp and sharp. Lighting: soft sun from the top-left, identical in every frame. No cast "
         "shadow on the ground. Use no green anywhere except the team-colour patches. Isolated on a flat, "
         "solid magenta (#FF00FF) background across the whole image: no ground, no terrain, no text, no "
         "numbers, no labels, no grid lines, no border, no watermark. Wide image, aspect ratio 3:2.")

# Robots (IDEA-29): no dive / crawl / prone (they don't take cover). (id, name, who, concept description, walk, attack)
ROBOTS = [
    ("enfw", "Enforcer Walker", "walker",
     "a large two-legged Union assault walker with twin arm autocannons and a shoulder rocket pod",
     "heavy stomping walk cycle, the torso rocking slightly with each heavy step",
     "fires both arm autocannons in alternating bursts with big muzzle flashes and ejected shells, then "
     "launches a rocket from the shoulder pod with a puff of smoke"),
    ("cybt", "Cyborg Trooper", "cyborg",
     "an armoured Union cyborg trooper with a glowing visor and a heavy automatic pistol",
     "steady, slightly mechanical marching walk cycle, upright and unstoppable",
     "raises the heavy pistol in one hand and fires a rapid burst with muzzle flashes and recoil, "
     "perfectly steady, then lowers it"),
    ("bdrd", "Battle Droid", "droid",
     "a tall bulky Union battle droid with a huge armoured chest, a small sensor head and a forearm blaster",
     "heavy, slightly clumsy robotic walk cycle, the big chest swaying",
     "raises the forearm blaster and fires glowing blue energy bolts with bright flashes, "
     "with a small recoil of the arm"),
    ("rgun", "Railgun Robot", "robot",
     "a lean Union robot with a very long two-handed railgun lit by blue coils",
     "lean, purposeful robotic walk cycle, the railgun held across the body",
     "braces the legs, raises the railgun to the shoulder, the coils charge up glowing brighter blue, "
     "fires a straight bright blue-white beam with a shock ring at the muzzle, the robot recoils, then "
     "the coils cool down"),
    ("strd", "Strider", "walker",
     "a big four-legged riveted Vanguard walker with a cannon turret and a smoking diesel exhaust stack",
     "slow heavy four-legged walk cycle, legs moving in alternating diagonal pairs, black exhaust puffs",
     "fires the turret cannon with a big muzzle blast and a recoil jolt of the whole hull, smoke, then "
     "short bursts from the front twin machine gun"),
    ("irgd", "Iron Guard", "soldier",
     "a Vanguard soldier in a heavy riveted hydraulic exosuit with a belt-fed heavy machine gun",
     "heavy stomping walk cycle in the exosuit, hydraulic pistons pumping",
     "braces and fires the belt-fed heavy machine gun in a long burst, big muzzle flashes, spent "
     "casings and links flying, the whole suit shaking with recoil"),
    ("taut", "Tesla Automaton", "robot",
     "a clanking riveted Vanguard robot with a Tesla coil for a head and copper electrode claws",
     "heavy clanking walk cycle, small blue sparks around the head coil",
     "raises both electrode claws, the head coil glows bright blue, and a jagged bright blue-white "
     "lightning bolt arcs forward from the claws, crackles, then fades"),
]
SPIDER = ("sdrn", "Spider Drone", "drone",
          "a small round riveted Vanguard bomb drone on six spider legs with one red sensor eye")


# Robots are drawn front-on by default, so the directions facing away say plainly that the front is hidden
ROBOT_DIRS = [(d, t) for d, t in DIRS5 if d not in ("nw", "n")] + [
    ("nw", "north-west: moving away from the viewer toward the top-left of the image; we see its BACK and "
           "left side, its front, face and visor are hidden"),
    ("n", "north: moving straight away from the viewer toward the top of the image; we see only its BACK "
          "(the rear armour, the back of the head and the backs of the legs); its front, face and visor are "
          "completely hidden"),
]


def add_robots(add, out):
    for uid, title, who, body, walk, attack in ROBOTS:
        out.append("**%s (`%s`)**\n" % (title, uid))
        a = lambda anim, n, motion, facing: add(uid, title, anim, n, motion, facing, who, body, ", same weapons")
        a("idle1", 8, "Idle while standing still: scans left and right with its sensors, small mechanical "
          "adjustments of the arms and weapons, returns to the starting pose (first and last frame match).",
          "Facing south, toward the viewer.")
        for d, facing in ROBOT_DIRS:
            f = "The %s faces %s, the same direction in every frame." % (who, facing)
            a("poses-" + d, 3, "Three still poses side by side (not an animation): 1) standing at rest, weapons "
              "lowered; 2) alert combat stance, weapons raised and ready; 3) braced low firing stance.", f)
            a("run-" + d, 6, "Walk cycle: " + walk + "; the last frame flows back into the first.", f)
            a("shoot-" + d, 6, "Attack: the %s %s." % (who, attack), f)
        side = "Seen from the south-west, three-quarter view."
        a("die1", 8, "Destroyed: sparks burst from its joints, it jerks, powers down (the lights go dark), "
          "the legs buckle and it collapses into a smoking wreck lying still in the last two frames.", side)
        a("die2", 8, "Destroyed by an explosion: blown apart in a fireball, armour plates and parts fly off, "
          "it ends as a burning, smoking pile of scrap.", side)

    uid, title, who, body = SPIDER
    out.append("**%s (`%s`)**\n" % (title, uid))
    a = lambda anim, n, motion, facing: add(uid, title, anim, n, motion, facing, who, body, "")
    a("idle1", 8, "Idle: crouches, twitches its legs, turns its red eye left and right, returns to the "
      "starting pose (first and last frame match).", "Facing south-west, three-quarter view.")
    for d, facing in ROBOT_DIRS:
        f = "The drone faces %s, the same direction in every frame." % facing
        a("poses-" + d, 3, "Three still poses side by side (not an animation): 1) standing on its legs; "
          "2) crouched low, ready to pounce; 3) legs folded, resting low.", f)
        a("run-" + d, 6, "Fast scuttling cycle: the six legs move in alternating sets of three, the body "
          "bobbing slightly; the last frame flows into the first.", f)
        a("shoot-" + d, 6, "Attack: crouches, leaps forward with the legs spread, the red eye flashes, and it "
          "explodes in a bright fireball with flying fragments; the last two frames are the fireball and smoke.", f)
    side = "Seen from the south-west, three-quarter view."
    a("die1", 8, "Destroyed: sparks fly, the legs collapse, the body cracks open and it burns out as a "
      "smoking wreck.", side)


def grid_for(n):
    return {1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (2, 2), 6: (3, 2), 8: (4, 2)}[n]


def prompt(who, body, weapon, n, motion, facing):
    c, r = grid_for(n)
    p = REF.format(who=who, body=body, weapon=weapon)
    if n > 1:
        p += SHEET.format(n=n, c=c, r=r)
    p += motion + " "
    p += facing + " "
    p += CAMERA + CELLS.format(who=who) + STYLE
    return p, c, r


def main():
    out, num = [], [0]

    def add(uid, title, anim, n, motion, facing, who, body, weapon):
        num[0] += 1
        p, c, r = prompt(who, body, weapon, n, motion, facing)
        out.append("### %d. %s - %s\nSave as: `%s/%s.png`\nReference: `assets/units/%s.png`\n"
                   "Grid: %dx%d frames\n\n```\n%s\n```\n" % (num[0], title, anim, uid, anim, uid, c, r, p))

    out.append(open(os.path.join(HERE, "infantry-anim-header.md")).read()
               if os.path.exists(os.path.join(HERE, "infantry-anim-header.md")) else HEADER)
    out.append("## Infantry Animations\n")

    for uid, title, body, attack, prone_attack, extra in SOLDIERS:
        who, weapon = "soldier", "" if attack is None else ", same weapon"
        out.append("**%s (`%s`)**\n" % (title, uid))
        a = lambda anim, n, motion, facing: add(uid, title, anim, n, motion, facing, who, body, weapon)
        a("idle1", 8, "Idle fidget while standing still: looks left, looks right, checks the weapon / "
          "gear, adjusts the helmet, returns to the starting pose (first and last frame match).",
          "Facing south, toward the viewer.")
        a("idle2", 8, "Second idle fidget: shifts weight, rolls the shoulders, wipes the brow, glances "
          "at the sky, returns to the starting pose (first and last frame match).",
          "Facing south, toward the viewer.")
        for d, facing in DIRS5:
            f = "The soldier faces " + facing + ", the same direction in every frame."
            a("poses-" + d, 3, "Three still poses side by side (not an animation): 1) standing relaxed, "
              "weapon held low, at ease; 2) alert combat stance, slightly crouched, weapon raised and ready; "
              "3) lying flat on the stomach, head up, weapon forward, taking cover.", f)
            a("run-" + d, 6, "Run cycle: a full running stride (contact, down, passing, up, contact, "
              "passing with the other leg), arms and weapon swinging naturally, leaning forward; the "
              "last frame flows back into the first.", f)
            a("dive-" + d, 4, "Hit the dirt: from standing, bends the knees, drops to one knee, dives "
              "forward, lands lying flat on the stomach (played backwards for getting up).", f)
            a("crawl-" + d, 4, "Prone crawl cycle: lying flat, elbows and knees alternate pulling forward, "
              "weapon cradled in the arms, head low; the last frame flows into the first.", f)
            if attack:
                a("shoot-" + d, 6, "Attack: the soldier " + attack + ".", f)
                a("prone-shoot-" + d, 4, "Prone attack: " + prone_attack + ".", f)
            if extra:
                a(extra[0] + "-" + d, 6, "Action: the soldier " + extra[1] + ".", f)
        side = "Seen from the south-west, three-quarter view."
        a("die1", 8, "Death, shot: hit by bullets, jerks, knees buckle, crumples and falls forward, "
          "lying still on the ground in the last two frames.", side)
        a("die2", 8, "Death, explosion: thrown off the feet backwards by a blast with dust and debris, "
          "flies through the air, lands hard and lies still, dusty and scorched.", side)
        # Only riflemen paradrop (paratroopers / Parabombs drop e1)
        if uid != "e1":
            continue
        a("parachute", 4, "Floating down under an open round military parachute (green team-colour "
          "panels on the canopy), legs together, slight sway left and right; the last frame flows into "
          "the first.", "Facing south, toward the viewer, the whole parachute visible.")

    # The attack dog has its own, simpler set.
    uid, title, body = DOG
    who, weapon = "dog", ""
    out.append("**%s (`%s`)**\n" % (title, uid))
    a = lambda anim, n, motion, facing: add(uid, title, anim, n, motion, facing, who, body, weapon)
    a("idle1", 8, "Idle: sniffs the ground, looks around, scratches an ear, returns to the starting "
      "pose (first and last frame match).", "Facing south-west, three-quarter view.")
    for d, facing in DIRS5:
        f = "The dog faces " + facing + ", the same direction in every frame."
        a("stand-" + d, 2, "Two still poses side by side (not an animation): 1) standing alert, ears up; "
          "2) sitting.", f)
        a("run-" + d, 6, "Gallop cycle: a full galloping stride, legs stretching and gathering, "
          "the last frame flows into the first.", f)
        a("attack-" + d, 6, "Attack: crouches, leaps forward with jaws open and front paws out, "
          "bites down, lands and recovers.", f)
        side = "Seen from the south-west, three-quarter view."
    a("die1", 8, "Death: yelps, staggers, collapses on its side and lies still.", side)
    a("die2", 8, "Death, explosion: thrown through the air by a blast, lands and lies still, dusty.", side)

    out.append("## Robot Animations\n")
    add_robots(add, out)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("wrote %s (%d prompts)" % (OUT, num[0]))


HEADER = """# RedAlert Project X - infantry animation prompts (ChatGPT)

Generated by `make_infantry_anim_prompts.py` - edit the script, not this file.

**How to use (by hand)**

1. Start a new ChatGPT chat per sheet. **Attach the soldier's concept image** (the `Reference:` file,
   e.g. `assets/units/e1.png`) and paste the prompt.
2. Reject a sheet if the soldier changes (different gear, colours or weapon), the frame count or grid is
   wrong, figures touch each other, the camera angle changes between frames, or the background is not magenta.
3. Save it under the **Save as** name, e.g. `assets/units/e1/run-sw.png`.
4. Start with one soldier (`e1`) and test it in game before doing the rest.

**Automatic:** `python3 generate_images.py --prompts infantry-anim-prompts.md --category units --only e1/`
attaches the reference image itself.

**Directions:** moving animations are drawn in 5 directions (S, SW, W, NW, N). SE, E and NE are mirrored
from SW, W and NW in game. Still poses (stand, guard, prone) are one 3-frame `poses-<dir>` sheet per direction.

**What each sheet becomes in game**

| Sheet | Game sequence |
|---|---|
| poses-* (frames 1 / 2 / 3) | `stand` / `stand2` / `prone-stand` |
| run-* | `run` (6 frames) |
| shoot-* | `shoot` |
| dive-* | `liedown` (played backwards = `standup`) |
| crawl-* | `prone-run` |
| prone-shoot-* | `prone-shoot` |
| heal-* / repair-* | medic heal / mechanic repair |
| idle1, idle2 | `idle1`, `idle2` |
| die1, die2 | `die1`, `die2`; reused for `die3`-`die5` (die6 electro and die-crushed stay classic) |
| parachute (Rifle Infantry only) | `parachute` |

"""

if __name__ == "__main__":
    main()
