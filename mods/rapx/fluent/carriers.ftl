## Aircraft carriers (rules/carriers.yaml, docs/DESIGN-IDEAS.md IDEA-08 2a)

actor-cv1 =
    .name = Fleet Carrier
    .description =
    Essex-class carrier from the Second World War.
    A floating airbase with SAM launchers for defence.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cv2 =
    .name = Battle Carrier
    .description =
    The first nuclear-powered carrier (Enterprise class).
    Bigger deck, tougher hull, more SAM launchers.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cv3 =
    .name = Supercarrier
    .description =
    Nimitz-class nuclear supercarrier.
    Heavily armoured flagship of the fleet.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cv4 =
    .name = Future Carrier
    .description =
    Gerald R. Ford-class carrier with the latest
    defences. The most powerful ship afloat.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

## National carriers: each nation builds only its own

actor-cvgb =
    .name = Queen Elizabeth Carrier
    .description =
    Royal Navy carrier with a ski-jump bow
    and twin islands.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvfr =
    .name = Charles de Gaulle Carrier
    .description =
    France's nuclear-powered carrier,
    the pride of the Marine nationale.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvjp =
    .name = Kaga Carrier
    .description =
    Helicopter destroyer rebuilt as a light
    carrier for jump-jet fighters.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvit =
    .name = Cavour Light Carrier
    .description =
    Italian light carrier for jump jets
    and helicopters.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cveg =
    .name = Mistral Helicopter Carrier
    .description =
    Egyptian amphibious helicopter carrier.
    Cheap and quick to build.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvsu =
    .name = Kiev Aviation Cruiser
    .description =
    Half carrier, half cruiser: a flight deck
    aft and missile launchers forward.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvru =
    .name = Kuznetsov Carrier
    .description =
    Heavy aircraft-carrying cruiser with
    a ski-jump bow and strong SAM defences.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvin =
    .name = Vikrant Carrier
    .description =
    India's home-built carrier with
    a ski-jump bow.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvcn =
    .name = Fujian Carrier
    .description =
    China's newest supercarrier with
    electromagnetic catapults.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvtr =
    .name = Anadolu Drone Carrier
    .description =
    Amphibious ship turned drone carrier.
    Launches swarms of attack drones.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

actor-cvir =
    .name = Bagheri Drone Carrier
    .description =
    A converted merchant ship with a flight
    deck for drones. Cheap, but fragile.
      Strong vs Aircraft, Missiles
      Weak vs Ships, Submarines

## Flight deck (IDEA-08 2c A1): HUD above the selected carrier, deploy key cycles the mode
label-carrier-deck-title = FLIGHT DECK
label-carrier-deck-launch = LAUNCH
label-carrier-deck-recover = RECOVER
label-carrier-deck-mixed = MIXED
notification-carrier-deck-mode = Flight deck: { $mode }
