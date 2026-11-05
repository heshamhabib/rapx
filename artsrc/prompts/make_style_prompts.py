#!/usr/bin/env python3
"""
Generates artsrc/prompts/style-prompts.md: one ChatGPT image prompt per nation and "skyline" building for the
national architecture styles of IDEA-01 (docs/DESIGN-IDEAS.md), plus USA (IDEA-13) and Iran (IDEA-15).

Every prompt uses the same render rules as the classic buildings in gemini-prompts.md (camera, footprint,
two versions side by side, magenta background, green team colour), so the results go through
artsrc/buildings/build_all.py like the existing renders. What changes is the architecture: the nation's
design for that building comes first, and the building's functional cue (IDEA-01 section 2) must stay visible.

  python3 artsrc/prompts/make_style_prompts.py
  python3 artsrc/prompts/browser_helper.py --prompts style-prompts.md --category styles --downloads ../../assets/inbox

Images are saved as assets/styles/<nation>/<building>.png.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_prompts import BUILDING, BUILDINGS, DAMAGE_EXTRA, TEAM  # noqa: E402

OUT = os.path.join(HERE, "style-prompts.md")

# The rollout's phase 1-2 "skyline" buildings. The barracks is TENT for Allied nations and BARR for Soviet ones.
SKYLINE = ["fact", "powr", "proc", "barracks", "weap", "dome"]

# Functional cue that must stay readable (IDEA-01 section 2).
CUE = {
    "fact": "a big construction crane or gantry",
    "powr": "cooling stacks or towers and a glowing power core",
    "proc": "a wide ore intake dock at the front where the harvester truck parks",
    "barracks": "an entry door or gate plus a flag or banner",
    "weap": "a very large vehicle bay door at the front",
    "dome": "a large radar dish or antenna array on top",
}

# Team-colour areas that exist in every national design.
TEAM_AREAS = {
    "fact": "the crane arm and roof trims",
    "powr": "roof trims and bands around the stacks",
    "proc": "roof trims and bands around the silos",
    "barracks": "the banners and roof trims",
    "weap": "the frame around the vehicle door and roof trims",
    "dome": "banners and the trim around the base",
}

# nation: (label, side, style name, landscape and materials, signature motifs, palette)
# No green anywhere except team colour: green surfaces would be recoloured to the player's colour, so the
# greens of the IDEA-01 palettes (Pakistan's green tile, England's racing green, jade, olive, Ukraine's
# green cupolas) are swapped for the nearest non-green colour.
NATIONS = {
    "egypt": ("Egypt", "soviet", "Pharaonic Desert", "desert and Nile stone; sandstone, limestone and gold",
              "pyramids and stepped pyramids, obelisks, pylon gateways, slanted walls, hieroglyph-style bands, gold capstones",
              "sand, ochre, lapis blue, gold"),
    "england": ("England", "allied", "Victorian Industrial", "rainy island; red brick, slate and cast iron",
                "clock towers, tall brick chimney stacks, glass-and-iron halls like the Crystal Palace, castle crenellations",
                "brick red, slate grey, dark navy trims"),
    "france": ("France", "allied", "Beaux-Arts Iron", "river cities; cream limestone, blue-grey zinc and wrought iron",
               "mansard roofs, wrought-iron lattice towers like the Eiffel Tower, arched windows, ornate cornices",
               "cream, blue-grey zinc, gilt"),
    "germany": ("Germany", "allied", "Bauhaus Bunker", "forests and the Rhine; concrete, steel and half-timbering",
                "flat roofs, strict geometry, massive flak-tower blocks, ribbon windows, half-timbering on small buildings",
                "concrete grey, black, white"),
    "italy": ("Italy", "allied", "Roman Renaissance", "Mediterranean hills; travertine, terracotta and marble",
              "columns and porticos, round arches, coffered domes like the Pantheon, aqueduct arcades, cypress trees",
              "terracotta, travertine, warm ochre"),
    "turkey": ("Turkey", "allied", "Ottoman Citadel", "Anatolian plateau and the Bosphorus; stone, lead domes and Iznik tile",
               "shallow lead domes, slender stone watchtowers, pointed arches, blue tile bands, fortress walls like Rumeli Hisari",
               "turquoise, cobalt, white stone"),
    "pakistan": ("Pakistan", "allied", "Mughal Fortress (white and teal)", "Indus plains and the Karakoram; white marble and deep teal-blue tile",
                 "fort gates like the Lahore Fort, carved lattice screens, geometric tile patterns, chhatri kiosks on the corners",
                 "white, deep teal-blue, gold"),
    "japan": ("Japan", "allied", "Edo Castle Tech", "mountains and coast; timber, white plaster, grey tile and glass",
              "tiered curved roofs, sloped castle stone bases like Himeji Castle, torii-style gate frames, sleek modern glass on tech parts",
              "white, charcoal, vermilion"),
    "southkorea": ("South Korea", "allied", "Hanok Hi-Tech", "mountains and the Han river; timber, tile, steel and glass",
                   "hanok curved tile roofs, dancheong painted beams, Seoul glass towers for tech and power",
                   "deep blue, red, cobalt, chrome"),
    "usa": ("USA", "allied", "Liberty Modern", "Great Plains, Rockies and the south-west desert; concrete, steel and glass",
            "Art Deco towers and setbacks, curved dam-style concrete like the Hoover Dam, white neoclassical domes and columns like the Capitol",
            "steel grey, white, navy blue, red trims"),
    "russia": ("Russia", "soviet", "Kremlin Stalinist", "taiga and snow; red brick, granite and steel",
               "Kremlin towers with red stars, Stalinist 'wedding cake' spires, heavy granite blocks",
               "brick red, granite, gold star"),
    "ukraine": ("Ukraine", "soviet", "Steppe Industrial", "wheat steppe and the Dnipro; concrete, steel and pastel plaster",
                "large industrial halls, grain-silo shapes, Kyiv-style pastel facades with small blue-and-gold cupolas on civic buildings",
                "wheat gold, sky blue, pastel"),
    "cuba": ("Cuba", "soviet", "Havana Colonial", "tropical island; pastel stucco, red tile and palm trees",
             "arcades, balconies, Spanish colonial stone forts like El Morro, Art Deco accents, palm trees",
             "pastel pink, turquoise, sun yellow"),
    "india": ("India", "soviet", "Red Fort Mughal", "plains and monsoon; red sandstone and white marble",
              "red sandstone fort walls like the Red Fort, onion-arch gateways, chhatri kiosks, stepwell geometry",
              "red sandstone, white, saffron"),
    "china": ("China", "soviet", "Imperial Great Wall", "rivers and mountains; red lacquer, yellow glazed tile and rammed earth",
              "Forbidden City roofs with upturned eaves, Great Wall walls and watchtowers, guardian lion statues at gates",
              "imperial red, golden yellow, deep blue"),
    "iran": ("Iran", "soviet", "Persian Desert Citadel", "high desert plateau, Alborz and Zagros mountains; mud-brick adobe and glazed tile",
             "adobe citadel walls like the Bam citadel, windcatcher towers (badgirs), Persepolis-style columns with griffin capitals, turquoise and cobalt tile bands, qanat water channels",
             "sand, adobe brown, turquoise, cobalt"),
}

# nation: designs for fact, powr, proc, barracks, weap, dome (Egypt from IDEA-01 section 3)
DESIGNS = {
    "egypt": (
        "a stepped pyramid under construction, with the crane standing on its top level",
        "two obelisks with glowing capstones linked by power arcs, with the reactor inside a sandstone pylon gateway between them",
        "a temple-like pylon gateway whose ore dock is flanked by sphinx-style statues, with sandstone silos with gold bands behind",
        "a sandstone courtyard behind a pylon gate, with tall banners on poles",
        "a long colonnade hall with a huge vehicle door set between two massive pylons",
        "an obelisk-shaped tower on a sandstone platform with the radar dish mounted on top",
    ),
    "england": (
        "a red-brick Victorian factory with a glass-and-iron roof, a cast-iron gantry crane and a small clock tower on one corner",
        "a red-brick power station with two tall brick chimney stacks like Battersea Power Station and a slate roof",
        "a brick mill with a cast-iron conveyor, the ore dock under an iron canopy and riveted iron storage tanks",
        "castle-style brick barracks with crenellated walls, an arched gate and a flagpole",
        "a long glass-and-iron hall like the Crystal Palace on a brick base, with a huge arched vehicle door",
        "a Victorian brick clock tower with the radar dish and antennas on top",
    ),
    "france": (
        "a cream limestone building with a blue-grey zinc mansard roof and a wrought-iron lattice crane",
        "a Beaux-Arts limestone hall with arched windows and two wrought-iron lattice cooling towers",
        "a limestone industrial hall with an iron-and-glass canopy over the ore dock and ornate silos with gilt bands",
        "limestone barracks with a mansard roof, an arched doorway, gilded cornices and a flagpole",
        "a long limestone hall like a grand railway station, with an ornate arched iron vehicle door and a zinc roof",
        "a wrought-iron lattice tower in the style of the Eiffel Tower carrying the radar dish at its top",
    ),
    "germany": (
        "a flat-roofed concrete Bauhaus block with ribbon windows and a steel gantry crane, strictly geometric",
        "a massive flak-tower-style concrete block with two square concrete cooling stacks",
        "a geometric concrete-and-steel plant with ribbon windows, cylindrical concrete silos and the ore dock under a flat cantilever roof",
        "small half-timbered barracks on a concrete bunker base with a steep roof and a flagpole",
        "a huge flat-roofed concrete bunker hall with ribbon windows and a wide steel blast door",
        "a round concrete flak tower with the radar dish on its flat roof",
    ),
    "italy": (
        "a travertine courtyard building with a columned portico, terracotta roofs, dark cypress trees and a construction crane",
        "a hall with a coffered dome like the Pantheon, two tall column-shaped cooling towers and aqueduct arches carrying the cables",
        "an ore dock under a row of aqueduct arcades, a terracotta-roofed warehouse and round travertine silos",
        "Roman-style barracks with an arched gate, a terracotta roof and a banner on a column",
        "a long basilica-style civic hall with columns along its sides and a huge round-arched vehicle door",
        "a tall stone civic watchtower like the tower of the Palazzo Vecchio with the radar dish on top",
    ),
    "turkey": (
        "a fortress courtyard with stone walls and a round corner tower like Rumeli Hisari, with a crane rising above the walls",
        "a stone hall with shallow lead domes, blue tile bands and two slender stone watchtowers as cooling stacks",
        "a caravanserai-style stone courtyard with pointed arches, the ore dock through a big arched gate and domed stone silos",
        "fortress barracks with crenellated walls, a pointed-arch gate and banners",
        "a long vaulted stone hall with a big pointed-arch vehicle door and a blue Iznik tile band",
        "a slender round stone watchtower like the Galata Tower with a conical roof and the radar dish",
    ),
    "pakistan": (
        "a white marble fort courtyard with chhatri kiosks on its corners and a construction crane",
        "a white marble hall with carved lattice screens, teal-blue tile and two kiosk-topped towers as cooling stacks",
        "a fort gate like the Lahore Fort as the ore dock, with white marble silos with teal-blue tile bands",
        "white marble fort barracks with a gate, lattice screens, chhatri kiosks and banners",
        "a long white marble hall with a huge scalloped-arch vehicle gate and teal-blue tile borders",
        "a tall white marble tower with a chhatri kiosk on top carrying the radar dish",
    ),
    "japan": (
        "a white plaster building with tiered curved grey tile roofs on a sloped castle stone base, with a modern crane",
        "a tiered-roof pavilion on a stone base in front of a sleek glass reactor hall, with two stacks under curved roof caps",
        "a white plaster warehouse with curved tile roofs, the ore dock under a torii-style gate frame and glass silos",
        "small castle-keep-style barracks with tiered curved roofs on a stone base and a vermilion banner",
        "a long hall with a curved tile roof on a castle stone base, its large vehicle door framed by a torii-style gate frame",
        "a tiered castle tower (tenshu) with a modern glass top carrying the radar dish",
    ),
    "southkorea": (
        "a hanok hall with curved tile roofs and painted dancheong beams next to a steel-and-glass assembly block with a crane",
        "a sleek glass tower power plant with a hanok curved-roof entrance pavilion and two chrome stacks",
        "a steel-and-glass plant with the ore dock under a hanok gate roof and chrome silos",
        "hanok courtyard barracks with curved tile roofs, red painted beams and banners",
        "a modern glass-and-steel hall with a big vehicle door under a curved hanok roof",
        "a slim glass tower like N Seoul Tower carrying the radar dish",
    ),
    "usa": (
        "a small five-sided concrete building shaped like the Pentagon, with the crane standing in its inner courtyard",
        "a curved Art Deco concrete power hall like the Hoover Dam powerhouse, with two stacks",
        "a streamlined Art Deco concrete plant with a long ore dock and steel silos",
        "white neoclassical barracks with columns and a small white dome like the Capitol, with a flagpole",
        "a streamlined Art Deco hall with a big vehicle door, steel panels and navy-blue trims",
        "a tall Art Deco tower with stepped setbacks and a spire crown like the Empire State Building, carrying the radar dish",
    ),
    "russia": (
        "a red-brick Kremlin wall section with a tower topped by a red star, the crane rising above the wall",
        "a granite Stalinist hall with two red-brick Kremlin-style towers as cooling stacks",
        "a heavy granite plant with a stepped 'wedding cake' facade, the ore dock under a brick arch and granite silos",
        "red-brick fortress barracks with a Kremlin-tower gate and red banners",
        "a massive granite hall with columns and a huge vehicle door under a gold star",
        "a Stalinist 'wedding cake' spire building with the radar dish on top",
    ),
    "ukraine": (
        "a large concrete industrial hall with a pastel plaster front and a steel crane",
        "a concrete hall with two cooling towers shaped like grain silos",
        "grain-elevator-style silos and conveyors with the ore dock at the front and a pastel facade",
        "pastel Kyiv-style plaster barracks with a small blue-and-gold cupola on the gatehouse and banners",
        "a big steel-and-concrete industrial hall with sky-blue panels and a wide vehicle door",
        "a tall concrete grain-elevator tower with the radar dish on top",
    ),
    "cuba": (
        "a pastel stucco courtyard with arcades, red tile roofs, palm trees and a crane",
        "a pastel Art Deco power hall with two stacks and palm trees",
        "a colonial warehouse with arcades and a red tile roof, the ore dock under an arched arcade",
        "stone fort barracks like El Morro with a small corner sentry box, a watchtower and banners",
        "a pastel Art Deco hall with balconies and a big vehicle door",
        "a colonial stone fort lighthouse tower like El Morro carrying the radar dish",
    ),
    "india": (
        "a red sandstone fort courtyard with chhatri kiosks on its corners and a crane",
        "a red sandstone hall with terraced stepwell-shaped cooling pits and two kiosk-topped stacks",
        "a Red Fort-style gateway as the ore dock, with red sandstone silos with white marble bands",
        "red sandstone fort barracks with an onion-arch gate and saffron banners",
        "a long red sandstone hall with a huge onion-arch vehicle gate",
        "a tall fluted red sandstone victory tower with the radar dish on top",
    ),
    "china": (
        "a Great Wall section with a watchtower and yellow-glazed roofs, the crane rising behind it",
        "a hall with Forbidden City upturned-eave roofs and two stacks with tiered roof caps",
        "a rammed-earth fort whose ore dock passes under a red lacquer gateway, with round silos",
        "courtyard barracks behind a red gate with guardian lion statues and yellow-tiled roofs",
        "a long imperial hall with a yellow-glazed roof, red columns and a huge vehicle door",
        "a Great Wall watchtower with the radar dish on top",
    ),
    "iran": (
        "an adobe citadel like the Bam citadel with windcatcher towers and a crane rising above its walls",
        "an adobe hall that uses two tall windcatcher towers as its cooling towers, with turquoise tile bands",
        "an adobe caravanserai with a qanat water channel, the ore dock through a tall tiled arch and beehive-shaped adobe storage domes",
        "adobe fortress barracks with Persepolis-style columns and griffin capitals at the gate, and banners",
        "a long adobe hall with a tall arched vehicle door framed by turquoise and cobalt tiles",
        "a windcatcher-style adobe tower with the radar dish on top",
    ),
}

STYLE = (
    "Architecture: the {style} national style of {nation}. Materials and landscape: {materials}. Signature motifs: {motifs}. "
    "Colour palette: {palette}. It is still a fortified military base building: civic, palace, fortress and industrial "
    "architecture only, no religious buildings"
)


def main():
    by_id = {b[0]: b for b in BUILDINGS}
    lines = [
        "# RedAlert Project X - national building style prompts (ChatGPT)",
        "",
        "Generated by `make_style_prompts.py` from IDEA-01 (national architecture styles) in `docs/DESIGN-IDEAS.md`, plus",
        "USA (IDEA-13) and Iran (IDEA-15). Do not edit by hand: edit the script and re-run it.",
        "",
        "**How to use**",
        "",
        "1. `python3 artsrc/prompts/browser_helper.py --prompts style-prompts.md --category styles --downloads ../../assets/inbox`",
        "   (or `generate_images.py` with the same arguments). Add `--only egypt` for one nation, or `--only egypt/fact` for one image.",
        "   Images are saved as `assets/styles/<nation>/<building>.png`.",
        "2. Start a new ChatGPT chat for every prompt. Don't attach the classic Construction Yard as a style reference: it pulls",
        "   the result back to the generic military look.",
        "3. Reject an image if the building's role is not obvious (crane, stacks, ore dock, door + banner, vehicle door, radar),",
        "   if it shows a religious building, if the two halves differ in camera or size, or if green appears outside team-colour areas.",
        "4. Then: copy the approved images to `artsrc/buildings/src/styles/<nation>/<id>.png` (IDEA-01 section 7).",
        "",
        "Each nation covers the six skyline buildings of rollout phases 1-2: Construction Yard, Power Plant, Ore Refinery,",
        "Barracks (Allied TENT or Soviet BARR), War Factory and Radar Dome.",
        "",
        "## Building styles",
        "",
    ]
    n = 0
    for nation, (label, side, style, materials, motifs, palette) in NATIONS.items():
        for key, design in zip(SKYLINE, DESIGNS[nation]):
            bid = key if key != "barracks" else ("tent" if side == "allied" else "barr")
            _, name, (w, h), _, _, _ = by_id[bid]
            n += 1
            desc = (f"A {name} for {label}, designed as {design}. Its role must stay obvious at a glance: keep {CUE[key]} "
                    f"clearly visible. Keep the overall height close to a classic RTS {name.lower()}.")
            prompt = BUILDING.format(
                desc=desc, w=w, h=h,
                style=STYLE.format(style=style, nation=label, materials=materials, motifs=motifs, palette=palette),
                team=TEAM.format(areas=TEAM_AREAS[key]), extra=DAMAGE_EXTRA.get(bid, ""))
            lines += [f"### {n}. {label} - {name}",
                      f"Style: {style} · {label} ({side})",
                      f"Save as: `{nation}/{bid}.png`", "", "```", prompt, "```", ""]

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT}: {len(NATIONS)} nations, {n} prompts")


if __name__ == "__main__":
    main()
