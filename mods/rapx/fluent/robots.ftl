## IDEA-29 robot units (rules/robots.yaml)

actor-enfw =
    .name = Enforcer Walker
    .description =
    Heavy two-legged Union assault walker.
    Twin arm autocannons shred infantry, a shoulder
    rocket pod cracks armour.
      Strong vs Infantry, Vehicles
      Weak vs Aircraft

actor-cybt =
    .name = Cyborg Trooper
    .description =
    Armoured Union cyborg with a heavy auto-pistol.
    Can't be crushed and never takes cover.
      Strong vs Infantry
      Weak vs Vehicles, Aircraft

actor-bdrd =
    .name = Battle Droid
    .description =
    Cheap Union combat droid with a blaster rifle.
    Built in numbers.
      Strong vs Infantry
      Weak vs Vehicles, Aircraft

actor-rgun =
    .name = Railgun Robot
    .description =
    Long-range Union anti-armour robot.
    Its railgun hits hard but recharges slowly.
      Strong vs Vehicles, Robots
      Weak vs Infantry, Aircraft

actor-strd =
    .name = Strider
    .description =
    Slow four-legged Vanguard assault walker
    with a heavy cannon and a machine gun.
      Strong vs Vehicles, Infantry
      Weak vs Aircraft

actor-irgd =
    .name = Iron Guard
    .description =
    Vanguard soldier in a powered exosuit with
    a belt-fed heavy machine gun.
    Can't be crushed and never takes cover.
      Strong vs Infantry
      Weak vs Vehicles, Aircraft

actor-sdrn =
    .name = Spider Drone
    .description =
    Fast, cheap Vanguard bomb drone. Runs at its
    target and detonates.
      Strong vs Vehicles, Robots
      Weak vs Infantry, Buildings

actor-taut =
    .name = Tesla Automaton
    .description =
    Heavy Vanguard robot that throws Tesla
    lightning from its hands.
      Strong vs Infantry, Robots
      Weak vs Vehicles, Aircraft

## Spy Cars (rules/spycar.yaml), built once MI6 Headquarters exists

actor-scar =
    .name = Spy Car 1
    .disguise-name = Civilian Car
    .description =
    Fast luxury car for the Spy with hidden machine
    guns and pop-up rockets. Carries one Spy.
    Requires MI6 Headquarters.
    Enemies see a harmless civilian car until it
    is shot at or opens fire.
      Strong vs Infantry, Vehicles
      Weak vs Aircraft

## MI6 Headquarters (rules/mi6.yaml)

actor-mi6 =
    .name = MI6 Headquarters
    .description =
    British secret intelligence headquarters.
    Unlocks the Spy and the Spy Cars. England only.
    Maximum of one can be built.
    Requires power to operate.

actor-scr2 =
    .name = Spy Car 2
    .description =
    Classic grand tourer with hidden twin machine
    guns. Tougher and cheaper than Spy Car 1.
    Carries one Spy. Requires MI6 Headquarters.
    Enemies see a harmless civilian car until it
    is shot at or opens fire.
      Strong vs Infantry
      Weak vs Tanks, Aircraft

## AE-2 Shroud Hawk (rules/gapjet.yaml)

actor-jet-gapgen =
    .name = AE-2 Shroud Hawk
    .description =
    Flying Gap Generator: an unarmed radar plane
    that hides the ground under it from the enemy.
    Order it over an area and it circles there.
      Requires Tech Center
      Unarmed, weak vs Anti-Air

## Vanguard Medium Tank (rules/vehicles.yaml MTNK)

actor-mtnk =
    .name = Medium Tank
    .description =
    Vanguard battle tank: cheaper and quicker
    than the Heavy Tank, with a lighter gun.
      Strong vs Vehicles
      Weak vs Infantry, Aircraft
actor-mtnk-husk-name = Husk (Medium Tank)

actor-xr85 =
    .name = XR-85 Tank Droid
    .description =
    French heavy gun platform. Very slow, but
    its cannon out-ranges every tank and hits
    harder than any other gun.
      Strong vs Vehicles, Buildings
      Weak vs Infantry up close, Aircraft
actor-xr85-husk-name = Husk (XR-85 Tank Droid)

actor-spdr =
    .name = Spider Tank
    .description =
    Vanguard eight-legged missile tank: heavy
    top-attack missiles, anti-aircraft missiles
    and interceptors that shoot down rockets.
      Strong vs Vehicles, Aircraft
      Weak vs Infantry
actor-spdr-husk-name = Husk (Spider Tank)
