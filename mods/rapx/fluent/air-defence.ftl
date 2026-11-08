## air-defence.yaml (IDEA-26 layered air defence)
actor-msam =
    .name = Medium SAM
    .description =
    Medium-range air defence: shoots down aircraft,
    cruise missiles, drones and some rockets.
    Needs a Radar Dome for full range.
      Strong vs Aircraft, Cruise missiles and Drones
      Weak vs Ground units; cannot stop ballistic missiles

actor-lsam =
    .name = Long-range SAM
    .description =
    Long-range air defence (Patriot / S-400 class):
    stops aircraft, cruise and tactical ballistic missiles.
    Needs a Radar Dome for full range.
      Strong vs Aircraft and Missiles
      Weak vs Ground units

actor-bmd =
    .name = Missile Shield
    .description =
    Ballistic missile defence (THAAD class): intercepts
    ballistic and hypersonic missiles far out.
    Needs a Radar Dome for full range.
      Strong vs Ballistic and Hypersonic missiles
      Cannot shoot aircraft, drones or rockets

actor-flak =
    .name = Flak Cannon
    .description =
    Heavy twin anti-aircraft gun. Its bursts damage
    every aircraft nearby and can knock down drones
    and cruise missiles.
      Strong vs Aircraft and Drones
      Weak vs Ground units
