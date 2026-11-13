#!/usr/bin/env python3
"""Generates mods/rapx/rules/ai.yaml: the skirmish AI's build lists, squads and support power use.

The AI only builds and uses what its bot modules list by name, so every new unit, building or support power used to
need a hand edit in four copies of the lists. This script reads the merged rules of the mod instead, puts every
buildable actor into a role (ground army, artillery, anti-air, jets, helicopters, ships, engineers, spies, airborne
transports...) and writes the lists for each AI personality from the role weights below. Actors a nation can't build
are listed for everyone: the AI skips what it can't build, so one list serves all factions.

Rerun after adding units or buildings:  python3 tools/make_ai.py
Unknown actors are printed as warnings and left out: give them a role in ROLE_OVERRIDES.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, 'mods', 'rapx')
OUT = os.path.join(MOD, 'rules', 'ai.yaml')

# --- MiniYaml (just enough for the rules: tabs, Inherits, -Trait removals) -----------------------------------------


def parse(path):
	root = []
	stack = [(-1, root)]
	for line in open(path, encoding='utf-8-sig'):
		s = line.rstrip('\n')
		if s.lstrip().startswith('#'):
			continue
		s = s.split('#', 1)[0]
		if not s.strip():
			continue
		indent = len(s) - len(s.lstrip('\t'))
		key, _, value = s.strip().partition(':')
		node = [key.strip(), value.strip(), []]
		while stack[-1][0] >= indent:
			stack.pop()
		stack[-1][1].append(node)
		stack.append((indent, node[2]))
	return root


def merge(a, b):
	nodes = {n[0]: [n[0], n[1], list(n[2])] for n in a}
	order = [n[0] for n in a]
	for n in b:
		if n[0].startswith('-'):
			nodes.pop(n[0][1:], None)
			continue
		if n[0] in nodes:
			old = nodes[n[0]]
			nodes[n[0]] = [n[0], n[1] or old[1], merge(old[2], n[2])]
		else:
			nodes[n[0]] = [n[0], n[1], list(n[2])]
			order.append(n[0])
	return [nodes[k] for k in dict.fromkeys(order) if k in nodes]


def load_actors():
	text = open(os.path.join(MOD, 'mod.yaml'), encoding='utf-8').read()
	files = []
	for line in text.split('\nRules:\n', 1)[1].splitlines():
		if not line.startswith('\t'):
			break
		line = line.strip()
		if line and not line.startswith('#'):
			files.append(line.split('|', 1)[-1])
	actors = {}
	for f in files:
		if f == 'rules/ai.yaml':
			continue
		for n in parse(os.path.join(MOD, f)):
			actors[n[0]] = merge(actors.get(n[0], []), n[2])
	return actors


def resolve(actors, name):
	out = []
	for n in actors.get(name, []):
		if n[0].startswith('Inherits'):
			out = merge(out, resolve(actors, n[1]))
	return merge(out, [n for n in actors.get(name, []) if not n[0].startswith('Inherits')])


def child(nodes, key):
	for n in nodes:
		if n[0] == key:
			return n
	return None


def value(nodes, key, default=''):
	n = child(nodes, key)
	return n[1] if n else default


def traits(nodes):
	return {n[0].split('@')[0] for n in nodes}

# --- Roles ---------------------------------------------------------------------------------------------------------


# Actors the rules alone don't classify well. 'skip' = the AI never builds it.
ROLE_OVERRIDES = {
	# Economy and base: handled by their own bot modules
	'harv': 'harvester', 'mcv': 'skip',
	# Units with one job, ordered by PxSpecialVehiclesBotModule / PxTransportBotModule
	'truk': 'supplytruck', 'qtnk': 'madtank', 'mtrk': 'crusher', 'mnly': 'minelayer', 'mi17': 'transport',
	# Units the AI has no use for (yet)
	'lst': 'skip',
	# Support vehicles that follow the army
	'mrj': 'support', 'mgg': 'support', 'jet.gapgen': 'support',
	# Anti-air vehicles
	'ftrk': 'aa', 'm16': 'aa', 'gurz': 'aa', 'meads': 'aa', 'spyd': 'aa',
	# Artillery (long range, rocket launchers are found by their RL_ weapons)
	'arty': 'arty', 'v2rl': 'arty', 'mlrs': 'arty', 'hlfr': 'arty', 'zolf': 'arty',
	# Heavy hitters
	'4tnk': 'heavy', 'xr85': 'heavy', 'ctnk': 'heavy', 'ptnk': 'heavy', 'ttnk': 'heavy', 'spdr': 'heavy',
	'strd': 'heavy', 'sfng': 'heavy', 'enfw': 'heavy',
	# One-off or limited specials
	'e7': 'hero', 'dtrk': 'hero', 'stnk': 'hero', 'dog': 'dog', 'medi': 'medic', 'mech': 'mechanic',
	'scar': 'spycar', 'scr2': 'spycar',
	'lsat': 'satellite',
}

# Buildings: role per building. Variants a nation can't build are skipped by the AI.
BUILDINGS = {
	'powr': 'power', 'apwr': 'power', 'proc': 'refinery', 'silo': 'silo', 'oilr': 'oil',
	'barr': 'barracks', 'tent': 'barracks', 'kenn': 'kennel', 'weap': 'factory', 'fix': 'repair',
	'dome': 'radar', 'hpad': 'helipad', 'afld': 'airfield', 'afld.ukraine': 'airfield',
	'abas': 'bigairfield', 'afbs': 'bigairfield', 'sacm': 'hugeairfield', 'abrn': 'airborne',
	'spen': 'naval', 'syrd': 'naval',
	'atek': 'tech', 'stek': 'tech', 'mi6': 'intel', 'gap': 'gapgen',
	'supl': 'uplink', 'lnch': 'launch',
	'iron': 'superweapon', 'mslo': 'superweapon', 'bmbf': 'superweapon', 'sbmb': 'superweapon',
	'pbox': 'defence', 'hbox': 'defence', 'gun': 'defence', 'ftur': 'defence', 'tsla': 'defence-strong',
	'ptwr': 'defence-strong', 'agun': 'antiair', 'sam': 'antiair', 'flak': 'antiair', 'msam': 'antiair-mid',
	'lsam': 'antiair-long', 'bmd': 'missile-shield', 'asat': 'asat',
	'sbag': 'wall', 'fenc': 'wall', 'brik': 'wall',
}


def classify(name, r):
	if name in ROLE_OVERRIDES:
		return ROLE_OVERRIDES[name]
	b = child(r, 'Buildable')
	queue = value(b[2], 'Queue')
	t = traits(r)
	weapons = [value(n[2], 'Weapon') for n in r if n[0].split('@')[0] == 'Armament']
	armed = any(weapons)
	aircraft = child(r, 'Aircraft')
	if queue == 'Infantry':
		if 'Captures' in t and not armed:
			return 'engineer'
		if 'Disguise' in t and 'Infiltrates' in t:
			return 'spy'
		return 'infantry' if armed else None
	if queue == 'Vehicle':
		if not armed:
			return None
		if any(w.startswith('RL_') for w in weapons):
			return 'arty'
		return 'vehicle'
	if queue == 'Aircraft':
		if 'PxAirlift' in t:
			return 'airlift'
		if 'PxStrategicBomber' in t:
			return 'bomber'
		if not armed:
			return 'transport' if 'Cargo' in t else None
		return 'heli' if value(aircraft[2], 'CanHover') == 'True' else 'jet'
	if queue == 'Ship':
		if 'PxCarrierDeck' in t or name.startswith('cv'):
			return 'carrier'
		return 'ship' if armed else None
	return None

# --- Personalities -------------------------------------------------------------------------------------------------


# Unit share (UnitsToBuild: the wanted share of the army, in %) and limit per unit of each role.
# Each nation only builds a few of the units of a role, so shares are per unit, not split across the role.
UNIT_ROLES = {
	#              share per personality                 limit
	'infantry':   ({'rush': 40, 'normal': 30, 'turtle': 30, 'naval': 10}, None),
	'dog':        ({'rush': 10, 'normal': 8, 'turtle': 8, 'naval': 0}, 4),
	'medic':      ({'rush': 4, 'normal': 4, 'turtle': 4, 'naval': 0}, 3),
	'mechanic':   ({'rush': 3, 'normal': 3, 'turtle': 3, 'naval': 0}, 2),
	'engineer':   ({'rush': 5, 'normal': 5, 'turtle': 3, 'naval': 3}, 3),
	'spy':        ({'rush': 3, 'normal': 4, 'turtle': 3, 'naval': 2}, 2),
	'hero':       ({'rush': 5, 'normal': 5, 'turtle': 4, 'naval': 0}, 2),
	'harvester':  ({'rush': 10, 'normal': 15, 'turtle': 15, 'naval': 10}, 8),
	'vehicle':    ({'rush': 45, 'normal': 40, 'turtle': 40, 'naval': 5}, None),
	'heavy':      ({'rush': 25, 'normal': 30, 'turtle': 30, 'naval': 0}, None),
	'arty':       ({'rush': 20, 'normal': 25, 'turtle': 25, 'naval': 30}, 6),
	'aa':         ({'rush': 12, 'normal': 15, 'turtle': 20, 'naval': 20}, 4),
	'support':    ({'rush': 3, 'normal': 3, 'turtle': 3, 'naval': 3}, 1),
	'spycar':     ({'rush': 3, 'normal': 3, 'turtle': 3, 'naval': 0}, 2),
	'minelayer':  ({'rush': 0, 'normal': 0, 'turtle': 2, 'naval': 0}, 2),
	'jet':        ({'rush': 12, 'normal': 20, 'turtle': 20, 'naval': 30}, None),
	'heli':       ({'rush': 12, 'normal': 20, 'turtle': 20, 'naval': 30}, None),
	'satellite':  ({'rush': 8, 'normal': 10, 'turtle': 10, 'naval': 10}, 4),
	'airlift':    ({'rush': 6, 'normal': 6, 'turtle': 4, 'naval': 6}, 2),
	'bomber':     ({'rush': 5, 'normal': 5, 'turtle': 5, 'naval': 5}, 1),
	'ship':       ({'rush': 10, 'normal': 12, 'turtle': 12, 'naval': 40}, None),
	'carrier':    ({'rush': 5, 'normal': 5, 'turtle': 5, 'naval': 20}, 1),
	'transport':  ({'rush': 4, 'normal': 5, 'turtle': 4, 'naval': 8}, 2),
	'madtank':    ({'rush': 3, 'normal': 3, 'turtle': 2, 'naval': 0}, 1),
	'supplytruck': ({'rush': 2, 'normal': 2, 'turtle': 2, 'naval': 2}, 1),
	'crusher':    ({'rush': 3, 'normal': 3, 'turtle': 3, 'naval': 0}, 2),
}

# Building fraction (BuildingFractions: share of the base, in %) and limit per building of each role.
BUILDING_ROLES = {
	#                   fraction per personality                    limit
	'power':          ({'rush': 0, 'normal': 0, 'turtle': 0, 'naval': 0}, None),
	'refinery':       ({'rush': 30, 'normal': 15, 'turtle': 30, 'naval': 25}, 4),
	'silo':           ({'rush': 0, 'normal': 0, 'turtle': 0, 'naval': 0}, None),
	'oil':            ({'rush': 2, 'normal': 3, 'turtle': 3, 'naval': 3}, 2),
	'barracks':       ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'kennel':         ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 0}, 1),
	'factory':        ({'rush': 2, 'normal': 6, 'turtle': 3, 'naval': 1}, 2),
	'repair':         ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'radar':          ({'rush': 10, 'normal': 1, 'turtle': 10, 'naval': 1}, 1),
	'helipad':        ({'rush': 2, 'normal': 4, 'turtle': 2, 'naval': 8}, 3),
	'airfield':       ({'rush': 2, 'normal': 4, 'turtle': 2, 'naval': 8}, 2),
	'bigairfield':    ({'rush': 1, 'normal': 2, 'turtle': 1, 'naval': 2}, 1),
	'hugeairfield':   ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'airborne':       ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'naval':          ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'tech':           ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'intel':          ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'gapgen':         ({'rush': 2, 'normal': 2, 'turtle': 3, 'naval': 2}, 2),
	'uplink':         ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'launch':         ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'superweapon':    ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'defence':        ({'rush': 7, 'normal': 7, 'turtle': 10, 'naval': 2}, None),
	'defence-strong': ({'rush': 5, 'normal': 5, 'turtle': 7, 'naval': 1}, None),
	'antiair':        ({'rush': 5, 'normal': 3, 'turtle': 5, 'naval': 5}, None),
	'antiair-mid':    ({'rush': 3, 'normal': 3, 'turtle': 3, 'naval': 3}, 3),
	'antiair-long':   ({'rush': 2, 'normal': 2, 'turtle': 2, 'naval': 2}, 2),
	'missile-shield': ({'rush': 1, 'normal': 1, 'turtle': 1, 'naval': 1}, 1),
	'asat':           ({'rush': 1, 'normal': 1, 'turtle': 2, 'naval': 1}, 2),
	'wall':           ({'rush': 0, 'normal': 0, 'turtle': 0, 'naval': 0}, None),
}

# Ticks before the AI starts on a building (radar first comes in early otherwise)
BUILDING_DELAYS = {
	'rush': {'dome': 4500},
	'normal': {'dome': 3000},
	'turtle': {'dome': 3000},
	'naval': {'dome': 3000, 'fix': 20000, 'tsla': 21000},
}

PERSONALITIES = {
	# condition, base builder power settings, squad size
	'rush': dict(condition='enable-rush-ai', power=(60, 160, 40), squad=20),
	'normal': dict(condition='enable-normal-ai', power=(60, 200, 40), squad=40),
	'turtle': dict(condition='enable-turtle-ai', power=(60, 250, 50), squad=10),
	'naval': dict(condition='enable-naval-ai', power=(60, 400, 40), squad=1),
}

ANY_AI = 'enable-rush-ai || enable-normal-ai || enable-turtle-ai || enable-naval-ai'

# --- Output --------------------------------------------------------------------------------------------------------

HEADER = """# GENERATED by tools/make_ai.py - edit that script, not this file.
# Skirmish AI: what it builds, how it fights and which support powers it fires. The lists cover every buildable actor
# of the mod, so every nation's units, jets, ships and buildings are in; the AI skips what its nation can't build.
Player:
	ModularBot@EasyAI:
		Name: bot-easy-ai.name
		Type: easy
	ModularBot@NormalAI:
		Name: bot-normal-ai.name
		Type: normal
	ModularBot@HardAI:
		Name: bot-hard-ai.name
		Type: hard
	ModularBot@BrutalAI:
		Name: bot-brutal-ai.name
		Type: brutal
	# Naval AI: builds a fleet, carriers and an air force, little ground army (for maps with lots of water)
	ModularBot@NavalAI:
		Name: bot-naval-ai.name
		Type: naval
	# Difficulty levels reuse the classic personalities: Easy = defensive turtle with a weaker economy,
	# Normal = normal, Hard = rush, Brutal = rush with a stronger economy (refinery income, see structures.yaml).
	GrantConditionOnBotOwner@rush:
		Condition: enable-rush-ai
		Bots: hard, brutal
	GrantConditionOnBotOwner@normal:
		Condition: enable-normal-ai
		Bots: normal
	GrantConditionOnBotOwner@turtle:
		Condition: enable-turtle-ai
		Bots: easy
	GrantConditionOnBotOwner@naval:
		Condition: enable-naval-ai
		Bots: naval
"""

# Target types (Targetable.TargetTypes) of the rules: GroundActor, AirborneActor, WaterActor, Structure...
SUPPORT_POWERS = """	SupportPowerBotModule:
		RequiresCondition: ({any}) && !treaty
		Decisions:
			spyplane:
				OrderName: SovietSpyPlane
				MinimumAttractiveness: 1
				Consideration@1:
					Against: Enemy
					Types: Structure
					Attractiveness: 1
					TargetMetric: None
					CheckRadius: 5c0
			paratroopers:
				OrderName: SovietParatroopers
				MinimumAttractiveness: 5
				Consideration@1:
					Against: Enemy
					Types: Structure
					Attractiveness: 1
					TargetMetric: None
					CheckRadius: 8c0
				Consideration@2:
					Against: Enemy
					Types: WaterActor
					Attractiveness: -5
					TargetMetric: None
					CheckRadius: 8c0
			parabombs:
				OrderName: UkraineParabombs
				MinimumAttractiveness: 1
				Consideration@1:
					Against: Enemy
					Types: Structure
					Attractiveness: 1
					TargetMetric: None
					CheckRadius: 5c0
			gps:
				OrderName: GpsPowerInfoOrder
				MinimumAttractiveness: 1
				Consideration@1:
					Against: Enemy
					Types: Structure
					Attractiveness: 1
					TargetMetric: None
					CheckRadius: 10c0
			nukepower:
				OrderName: NukePowerInfoOrder
				MinimumAttractiveness: 3000
				Consideration@1:
					Against: Enemy
					Types: Structure
					Attractiveness: 1
					TargetMetric: Value
					CheckRadius: 5c0
				Consideration@2:
					Against: Ally
					Types: GroundActor, AirborneActor, WaterActor
					Attractiveness: -10
					TargetMetric: Value
					CheckRadius: 7c0
			fatman:
				OrderName: UsaFatmanStrike
				MinimumAttractiveness: 2000
				Consideration@1:
					Against: Enemy
					Types: Structure
					Attractiveness: 1
					TargetMetric: Value
					CheckRadius: 4c0
				Consideration@2:
					Against: Ally
					Types: GroundActor, AirborneActor, WaterActor
					Attractiveness: -10
					TargetMetric: Value
					CheckRadius: 6c0
			rds37:
				OrderName: RussiaThermonuclearStrike
				MinimumAttractiveness: 2500
				Consideration@1:
					Against: Enemy
					Types: Structure
					Attractiveness: 1
					TargetMetric: Value
					CheckRadius: 5c0
				Consideration@2:
					Against: Ally
					Types: GroundActor, AirborneActor, WaterActor
					Attractiveness: -10
					TargetMetric: Value
					CheckRadius: 7c0
			# Iron Curtain: on a group of own tanks that is fighting enemies
			ironcurtain:
				OrderName: GrantExternalConditionPowerInfoOrder
				MinimumAttractiveness: 4000
				FineScanRadius: 1
				Consideration@1:
					Against: Ally
					Types: Vehicle
					Attractiveness: 1
					TargetMetric: Value
					CheckRadius: 2c0
				Consideration@2:
					Against: Enemy
					Types: GroundActor
					Attractiveness: 1
					TargetMetric: Value
					CheckRadius: 6c0
""".replace('{any}', ANY_AI)


def yaml_list(items):
	return ', '.join(items)


def dict_block(indent, title, d):
	if not d:
		return []
	lines = [f'{indent}{title}:']
	for k, v in d.items():
		lines.append(f'{indent}\t{k}: {v}')
	return lines


def main():
	actors = load_actors()
	units = {}
	buildings = []
	unknown = []
	for raw in actors:
		if raw.startswith('^'):
			continue
		r = resolve(actors, raw)
		b = child(r, 'Buildable')
		if not b:
			continue
		prereqs = value(b[2], 'Prerequisites')
		if '~disabled' in prereqs:
			continue
		name = raw.lower()
		queue = value(b[2], 'Queue')
		if queue in ('Building', 'Defense'):
			if name in BUILDINGS:
				buildings.append(name)
			elif name != 'fact':
				unknown.append(f'{name} ({queue})')
			continue
		role = classify(name, r)
		if role is None:
			unknown.append(f'{name} ({queue})')
		elif role != 'skip':
			units.setdefault(role, []).append(name)

	for u in unknown:
		print(f'warning: no AI role for {u}: add it to ROLE_OVERRIDES or BUILDINGS in {os.path.basename(__file__)}',
			file=sys.stderr)
	for role in units:
		units[role].sort()
	buildings.sort()

	def by_role(role):
		return units.get(role, [])

	air = by_role('jet') + by_role('heli') + by_role('satellite')
	naval = by_role('ship') + by_role('carrier')
	# Units that never join an attack squad: their own bot modules (or nobody) give their orders
	excluded = ['harv', 'mcv'] + by_role('engineer') + by_role('spy') + by_role('airlift') + by_role('bomber') \
		+ by_role('minelayer') + by_role('transport') + by_role('madtank') + by_role('supplytruck') + by_role('crusher') \
		+ ['jet.gapgen']
	defences = [b for b in buildings if BUILDINGS[b].startswith(('defence', 'antiair', 'missile', 'asat'))]
	production = [b for b in buildings if BUILDINGS[b] in ('barracks', 'kennel', 'factory', 'helipad', 'airfield')]
	protection = ['harv', 'mcv', 'fact'] + [b for b in buildings if BUILDINGS[b] != 'wall']

	out = [HEADER.rstrip('\n'), SUPPORT_POWERS.rstrip('\n')]
	out.append(f"""	HarvesterBotModule:
		RequiresCondition: {ANY_AI}
		HarvesterTypes: harv
		RefineryTypes: proc
	BuildingRepairBotModule:
		RequiresCondition: {ANY_AI}
	McvManagerBotModule:
		RequiresCondition: {ANY_AI}
		McvTypes: mcv
		ConstructionYardTypes: fact
		McvFactoryTypes: weap
	# Engineers capture enemy and neutral buildings (oil derricks, tech buildings)
	CaptureManagerBotModule:
		RequiresCondition: ({ANY_AI}) && !treaty
		CapturingActorTypes: {yaml_list(by_role('engineer'))}
	# RAPX: airborne transports drop their troops on weakly defended enemy buildings, spies infiltrate
	PxAirliftBotModule:
		RequiresCondition: ({ANY_AI}) && !treaty
	PxSpyBotModule:
		RequiresCondition: ({ANY_AI}) && !treaty
		SpyTypes: {yaml_list(by_role('spy'))}
	# RAPX: jets that can use a carrier deck are rebased on the bot's carriers
	PxCarrierBotModule:
		RequiresCondition: ({ANY_AI}) && !treaty
	# RAPX: transport helicopters fly infantry from the base next to weakly defended enemy buildings
	PxTransportBotModule:
		RequiresCondition: ({ANY_AI}) && !treaty
		TransportTypes: {yaml_list(by_role('transport'))}
		PassengerTypes: {yaml_list(by_role('infantry') + by_role('medic'))}
	# RAPX: MAD Tanks, Supply Trucks, Monster Trucks
	PxSpecialVehiclesBotModule:
		RequiresCondition: ({ANY_AI}) && !treaty
		MadTankTypes: {yaml_list(by_role('madtank'))}
		SupplyTruckTypes: {yaml_list(by_role('supplytruck'))}
		CrusherTypes: {yaml_list(by_role('crusher'))}""")

	for p, cfg in PERSONALITIES.items():
		mn, mx, inc = cfg['power']
		fractions = {}
		limits = {}
		for b in buildings:
			share, limit = BUILDING_ROLES[BUILDINGS[b]]
			if share[p] > 0:
				fractions[b] = share[p]
			if limit is not None and share[p] > 0:
				limits[b] = limit
		lines = [f'\tBaseBuilderBotModule@{p}:',
			f'\t\tRequiresCondition: {cfg["condition"]}',
			f'\t\tMinimumExcessPower: {mn}',
			f'\t\tMaximumExcessPower: {mx}',
			f'\t\tExcessPowerIncrement: {inc}',
			'\t\tExcessPowerIncreaseThreshold: 4',
			'\t\tConstructionYardTypes: fact',
			'\t\tRefineryTypes: proc',
			'\t\tPowerTypes: powr, apwr',
			'\t\tBarracksTypes: barr, tent',
			'\t\tVehiclesFactoryTypes: weap',
			f'\t\tProductionTypes: {yaml_list(production)}',
			'\t\tNavalProductionTypes: spen, syrd',
			'\t\tSiloTypes: silo',
			f'\t\tDefenseTypes: {yaml_list(defences)}']
		lines += dict_block('\t\t', 'BuildingLimits', limits)
		lines += dict_block('\t\t', 'BuildingFractions', fractions)
		lines += dict_block('\t\t', 'BuildingDelays', BUILDING_DELAYS[p])

		lines += [f'\tSquadManagerBotModule@{p}:',
			f'\t\tRequiresCondition: {cfg["condition"]} && !treaty',
			f'\t\tSquadSize: {cfg["squad"]}',
			f'\t\tNavalUnitsTypes: {yaml_list(naval)}',
			f'\t\tExcludeFromSquadsTypes: {yaml_list(excluded)}',
			'\t\tConstructionYardTypes: fact',
			'\t\tNavalProductionTypes: spen, syrd',
			f'\t\tAirUnitsTypes: {yaml_list(air)}',
			'\t\tAircraftTargetType: AirborneActor',
			f'\t\tProtectionTypes: {yaml_list(protection)}',
			'\t\tIgnoredEnemyTargetTypes: AirborneActor']

		to_build = {}
		unit_limits = {}
		for role, (share, limit) in UNIT_ROLES.items():
			if share[p] <= 0:
				continue
			for u in by_role(role):
				to_build[u] = share[p]
				if limit is not None:
					unit_limits[u] = limit
		lines += [f'\tUnitBuilderBotModule@{p}:', f'\t\tRequiresCondition: {cfg["condition"]}']
		lines += dict_block('\t\t', 'UnitsToBuild', to_build)
		lines += dict_block('\t\t', 'UnitLimits', unit_limits)
		out.append('\n'.join(lines))

	out.append(f"""	MinelayerBotModule@turtle:
		RequiresCondition: enable-turtle-ai
		MinelayingActorTypes: {yaml_list(by_role('minelayer'))}
		IgnoredEnemyTargetTypes: Structure, Defense, AirborneActor
		UseEnemyLocationTargetTypes: Structure, Defense, AirborneActor
		AwayFromAlliedTargetTypes: Structure, Defense
		AwayFromEnemyTargetTypes: Structure, Defense""")

	with open(OUT, 'w', encoding='utf-8') as f:
		f.write('\n'.join(out) + '\n')

	total = sum(len(v) for v in units.values())
	print(f'{OUT}: {total} units in {len(units)} roles, {len(buildings)} buildings')
	for role in sorted(units):
		print(f'  {role:10} {" ".join(units[role])}')


if __name__ == '__main__':
	main()
