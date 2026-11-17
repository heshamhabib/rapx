#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is free software. It is made
 * available to you under the terms of the GNU General Public License
 * as published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version. For more
 * information, see COPYING.
 */
#endregion

using System;
using System.Collections.Generic;
using System.Linq;
using OpenRA.GameRules;
using OpenRA.Mods.Common.Projectiles;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Warheads;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Mods.RAPX.Warheads;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Everything the Extras catalogue shows, read from the live rules so it never goes stale: the nations,
	/// what each nation can build (prerequisite closure from the Construction Yard), stats, weapons and features.
	/// Hand-written texts live in fluent/catalogue.ftl as catalogue-&lt;actor&gt; with .role and .lore attributes.
	/// </summary>
	public sealed class PxCatalogueData
	{
		public const int Ticks = 25;

		public static readonly string[] Categories = { "Building", "Defense", "Infantry", "Vehicle", "Aircraft", "Ship" };

		// Damage classes for the "effective against" grades: label, armour type(s) and target types that reach them
		public static readonly (string Label, string[] Armor, string[] Targets)[] Classes =
		{
			("INFANTRY", new[] { "None" }, new[] { "Ground", "GroundActor", "Infantry" }),
			("LIGHT ARMOUR", new[] { "Light" }, new[] { "Ground", "GroundActor", "Vehicle" }),
			("HEAVY ARMOUR", new[] { "Heavy" }, new[] { "Ground", "GroundActor", "Vehicle" }),
			("STRUCTURES", new[] { "Wood", "Concrete" }, new[] { "Ground", "GroundActor", "Structure" }),
			("AIRCRAFT", new[] { "Light" }, new[] { "Air", "AirborneActor" }),
			("NAVAL", new[] { "Light", "Heavy" }, new[] { "Water", "WaterActor", "Underwater", "Ship", "Submarine" }),
		};

		public sealed class Nation
		{
			public string Id;
			public string Name;
			public string Side;
			public string Motto;
			public string[] Specials;
			public string Lore;
			public HashSet<string> Available = new();
		}

		public sealed class Weapon
		{
			public string Name;
			public string Kind;

			/// <summary>One line on what a support weapon does (catalogue-weapon-note-&lt;id&gt;), or null.</summary>
			public string Note;
			public int Damage;
			public int Burst;
			public float Range;
			public float MinRange;
			public float Reload;
			public float Dps;
			public bool Air;
			public bool Ground;
			public bool Naval;
			public bool Support;
			public int[] Versus;
		}

		public sealed class Entry
		{
			public ActorInfo Actor;
			public string Name;
			public string Category;
			public string Role;
			public string Lore;
			public string[] Notes;
			public int Order;
			public int Cost;
			public int BuildTicks;
			public int Power;
			public int HP;
			public string Armor;
			public float Speed;
			public float Sight;
			public float Range;
			public float Dps;
			public bool Rotates;
			public string[] Prerequisites;
			public readonly List<Weapon> Weapons = new();
			public readonly List<string> Features = new();
			public float[] Effect;
			public HashSet<string> Nations = new();
		}

		public readonly List<Nation> Nations = new();
		public readonly List<Entry> Entries = new();
		public readonly Dictionary<string, float> CategoryMax = new();
		readonly Ruleset rules;
		readonly Dictionary<string, List<ActorInfo>> providers = new();

		public PxCatalogueData(Ruleset rules, string seedActor)
		{
			this.rules = rules;
			var buildables = rules.Actors.Values
				.Where(a => !a.Name.StartsWith('^') && a.HasTraitInfo<BuildableInfo>() && a.HasTraitInfo<TooltipInfo>() &&
					a.TraitInfo<BuildableInfo>().Queue.Any(q => Categories.Contains(q)))
				.ToList();

			foreach (var a in rules.Actors.Values)
				foreach (var p in a.TraitInfos<ProvidesPrerequisiteInfo>())
					providers.GetOrAdd(p.Prerequisite ?? a.Name).Add(a);

			LoadNations();
			foreach (var n in Nations)
				n.Available = Closure(n.Id, buildables, seedActor);

			foreach (var a in buildables)
			{
				var e = CreateEntry(a);
				e.Nations = Nations.Where(n => n.Available.Contains(a.Name)).Select(n => n.Id).ToHashSet();
				if (e.Nations.Count > 0)
					Entries.Add(e);
			}

			Entries.Sort((a, b) => a.Order != b.Order ? a.Order.CompareTo(b.Order) : a.Cost.CompareTo(b.Cost));
			Grade();
		}

		void LoadNations()
		{
			foreach (var f in rules.Actors[SystemActors.World].TraitInfos<FactionInfo>())
			{
				if (!f.Selectable || f.InternalName == null || f.InternalName.StartsWith("Random", StringComparison.Ordinal) ||
					Nations.Any(n => n.Id == f.InternalName))
					continue;

				var lines = f.Description != null ? FluentProvider.GetMessage(f.Description).Split('\n') : Array.Empty<string>();
				var first = lines.Length > 0 ? lines[0].Trim() : "";
				var colon = first.IndexOf(':');
				Nations.Add(new Nation
				{
					Id = f.InternalName,
					Name = FluentProvider.GetMessage(f.Name),
					Side = f.Side ?? "",
					Motto = colon >= 0 ? first[(colon + 1)..].Trim() : first,
					Specials = lines.Skip(1).Select(l => l.Trim()).Where(l => l.Length > 0).ToArray(),
					Lore = Text($"catalogue-nation-{f.InternalName}.lore"),
				});
			}
		}

		/// <summary>Everything a nation can reach from its Construction Yard, following the same prerequisites the sidebar uses.</summary>
		HashSet<string> Closure(string faction, List<ActorInfo> buildables, string seedActor)
		{
			var tokens = new HashSet<string>();
			var built = new HashSet<string>();

			// RequiresPrerequisites can be met later (e.g. War Factory + captured enemy Construction Yard), so this re-runs every pass
			bool Provide(ActorInfo a)
			{
				var added = false;
				foreach (var p in a.TraitInfos<ProvidesPrerequisiteInfo>())
					if ((p.Factions.Count == 0 || p.Factions.Contains(faction)) && p.RequiresPrerequisites.All(r => tokens.Contains(r.TrimStart('~'))))
						added |= tokens.Add(p.Prerequisite ?? a.Name);

				return added;
			}

			var player = rules.Actors[SystemActors.Player];
			foreach (var t in player.TraitInfos<ProvidesTechPrerequisiteInfo>())
				tokens.UnionWith(t.Prerequisites);
			foreach (var c in player.TraitInfos<LobbyPrerequisiteCheckboxInfo>())
				tokens.UnionWith(c.Prerequisites);

			Provide(player);
			if (rules.Actors.TryGetValue(seedActor, out var seed))
			{
				built.Add(seed.Name);
				Provide(seed);
			}

			bool Met(string p)
			{
				p = p.TrimStart('~');
				return p.StartsWith('!') || tokens.Contains(p);
			}

			var changed = true;
			while (changed)
			{
				changed = false;
				foreach (var name in built)
					changed |= Provide(rules.Actors[name]);

				foreach (var a in buildables)
				{
					if (built.Contains(a.Name))
						continue;

					var bi = a.TraitInfo<BuildableInfo>();
					var national = a.TraitInfoOrDefault<PxNationalUnitInfo>();
					if ((national != null && !national.Factions.Contains(faction)) || !bi.Prerequisites.All(Met))
						continue;

					built.Add(a.Name);
					Provide(a);
					changed = true;
				}
			}

			return built;
		}

		static string Text(string key) => FluentProvider.TryGetMessage(key, out var s) ? s : null;

		public static string ActorName(ActorInfo a)
		{
			var t = a.TraitInfos<TooltipInfo>().FirstOrDefault(i => i.EnabledByDefault) ?? a.TraitInfos<TooltipInfo>().FirstOrDefault();
			return t != null ? FluentProvider.GetMessage(t.Name) : a.Name.ToUpperInvariant();
		}

		/// <summary>Names of the buildings behind each prerequisite that this nation can build.</summary>
		public IEnumerable<string> Requires(Entry e, Nation nation)
		{
			foreach (var p in e.Prerequisites)
			{
				var options = providers.TryGetValue(p, out var list) ? list.Where(a => nation.Available.Contains(a.Name)).ToList() : new List<ActorInfo>();
				if (options.Count == 0 && rules.Actors.TryGetValue(p, out var direct))
					options.Add(direct);

				var names = options.Select(ActorName).Distinct().ToList();
				if (names.Count > 0)
					yield return string.Join(" / ", names.Take(2));
			}
		}

		Entry CreateEntry(ActorInfo a)
		{
			var bi = a.TraitInfo<BuildableInfo>();
			var id = a.Name.Replace('.', '-').ToLowerInvariant();
			var e = new Entry
			{
				Actor = a,
				Name = ActorName(a),
				Category = Categories.First(c => bi.Queue.Contains(c)),
				Order = bi.BuildPaletteOrder,
				Cost = a.TraitInfoOrDefault<ValuedInfo>()?.Cost ?? 0,
				Power = a.TraitInfos<PowerInfo>().Where(i => i.EnabledByDefault).Sum(i => i.Amount),
				HP = a.TraitInfoOrDefault<HealthInfo>()?.HP ?? 0,
				Armor = a.TraitInfos<ArmorInfo>().FirstOrDefault()?.Type,
				Sight = a.TraitInfos<RevealsShroudInfo>().Select(r => r.Range.Length / 1024f).DefaultIfEmpty(0).Max(),
				Rotates = a.HasTraitInfo<IFacingInfo>() && !a.HasTraitInfo<BuildingInfo>(),
				Role = Text($"catalogue-{id}.role"),
				Lore = Text($"catalogue-{id}.lore"),
				Prerequisites = bi.Prerequisites.Select(p => p.TrimStart('~'))
					.Where(p => !p.StartsWith('!') && !p.StartsWith("techlevel", StringComparison.Ordinal)).ToArray(),
			};

			var time = bi.BuildDuration == -1 ? e.Cost : bi.BuildDuration;
			var queue = rules.Actors[SystemActors.Player].TraitInfos<ProductionQueueInfo>().FirstOrDefault(q => bi.Queue.Contains(q.Type));
			e.BuildTicks = time * bi.BuildDurationModifier * (queue?.BuildDurationModifier ?? 100) / 10000;

			var mobile = a.TraitInfoOrDefault<MobileInfo>();
			var aircraft = a.TraitInfoOrDefault<AircraftInfo>();
			var speed = aircraft?.Speed ?? mobile?.Speed ?? 0;
			e.Speed = speed * (float)Ticks / 1024;

			if (bi.Description != null)
			{
				var notes = FluentProvider.GetMessage(bi.Description).Split('\n').Select(l => l.Trim()).Where(l => l.Length > 0).ToArray();
				e.Notes = notes;
			}

			e.Role ??= DefaultRole(e, aircraft);

			foreach (var arm in a.TraitInfos<ArmamentInfo>())
			{
				if (arm.WeaponInfo == null || e.Weapons.Any(w => w.Name == Pretty(arm.Weapon)))
					continue;

				e.Weapons.Add(CreateWeapon(arm.Weapon, arm.WeaponInfo, rules));
			}

			// The Fatman bomber's bomb (PxStrategicBomber) is no armament: it falls once per Fatman Strike, so it shows the
			// strike's charge time as its reload and stays out of the damage-per-second grades
			var bomber = a.TraitInfoOrDefault<PxStrategicBomberInfo>();
			if (bomber?.WeaponInfo != null)
			{
				var bomb = CreateWeapon(bomber.Weapon, bomber.WeaponInfo);
				var charge = rules.Actors.Values.SelectMany(r => r.TraitInfos<PxFatmanStrikePowerInfo>())
					.FirstOrDefault(p => p.Bombers.Contains(a.Name))?.ChargeInterval ?? 0;
				bomb.Reload = charge / (float)Ticks;
				bomb.Dps = 0;
				e.Weapons.Add(bomb);
			}

			e.Dps = e.Weapons.Where(w => !w.Support).Select(w => w.Dps).DefaultIfEmpty(0).Max();
			e.Range = e.Weapons.Where(w => !w.Support).Select(w => w.Range).DefaultIfEmpty(0).Max();
			AddFeatures(e, aircraft, mobile);
			AddAirliftFeatures(e);
			return e;
		}

		static string DefaultRole(Entry e, AircraftInfo aircraft)
		{
			switch (e.Category)
			{
				case "Building": return "Base structure";
				case "Defense": return e.HP > 0 && e.Actor.HasTraitInfo<ArmamentInfo>() ? "Base defence" : "Fortification";
				case "Infantry": return "Infantry";
				case "Vehicle": return "Ground vehicle";
				case "Aircraft": return aircraft != null && aircraft.VTOL ? "Rotary-wing aircraft" : "Fixed-wing aircraft";
				default: return "Naval vessel";
			}
		}

		static string Pretty(string weapon)
		{
			var s = weapon.Replace('_', ' ').Replace('.', ' ');
			var r = new System.Text.StringBuilder();
			for (var i = 0; i < s.Length; i++)
			{
				if (i > 0 && char.IsUpper(s[i]) && char.IsLower(s[i - 1]))
					r.Append(' ');
				r.Append(s[i]);
			}

			return r.ToString();
		}

		static string ProjectileKind(WeaponInfo w)
		{
			var name = w.Projectile?.GetType().Name ?? "";
			if (name.Contains("GravityBomb") && w.Warheads.Any(h => h is PxRadiationWarhead))
				return "Atomic bomb";
			if (name.Contains("Laser") || name.Contains("Railgun"))
				return "Energy beam";
			if (name.Contains("Tesla") || name.Contains("Lightning"))
				return "Tesla arc";
			if (name.Contains("Flame"))
				return "Flamethrower";
			if (name.Contains("Missile") || name.Contains("Rocket"))
				return "Guided missile";
			if (name.Contains("Torpedo"))
				return "Torpedo";
			if (name.Contains("GravityBomb"))
				return "Bombs";
			if (name.Contains("InstantHit") || name.Contains("Tracer"))
				return "Small arms";
			if (name.Contains("AreaBeam"))
				return "Beam";
			if (name.Contains("Nuke"))
				return "Nuclear warhead";

			// Lobbed rounds: long-range artillery, or a grenade thrown by hand
			if (w.Projectile is BulletInfo bullet && bullet.LaunchAngle.Any(a => a.Angle > 0))
				return w.Range.Length >= 7168 ? "Artillery shell" : "Grenade";

			return "Cannon shell";
		}

		/// <summary>Damage warheads a shot delivers, with how many times each goes off: its own, the bomblets a
		/// FireCluster warhead throws (cluster bombs, cluster rockets) and the pulses of burning ground (PxBurn).</summary>
		static void CollectDamage(WeaponInfo w, Ruleset rules, int times, List<(DamageWarhead Warhead, int Times)> into, ref string kind, int depth = 0)
		{
			foreach (var d in w.Warheads.OfType<DamageWarhead>())
				into.Add((d, times));

			if (rules == null || depth > 2)
				return;

			foreach (var c in w.Warheads.OfType<FireClusterWarhead>())
			{
				if (!rules.Weapons.TryGetValue(c.Weapon.ToLowerInvariant(), out var sub))
					continue;

				var cells = c.Footprint.Count(ch => ch == 'x' || ch == 'X');
				var count = c.RandomClusterCount > 0 ? c.RandomClusterCount + c.Footprint.Count(ch => ch == 'X') : cells;
				kind ??= "Cluster munition";
				CollectDamage(sub, rules, times * Math.Max(1, count), into, ref kind, depth + 1);
			}

			foreach (var b in w.Warheads.OfType<PxBurnWarhead>())
			{
				if (!rules.Weapons.TryGetValue(b.Weapon.ToLowerInvariant(), out var burn))
					continue;

				kind = "Incendiary";
				CollectDamage(burn, rules, times * Math.Max(1, b.Duration / Math.Max(1, b.Interval)), into, ref kind, depth + 1);
			}
		}

		public static Weapon CreateWeapon(string key, WeaponInfo w, Ruleset rules = null)
		{
			var hits = new List<(DamageWarhead Warhead, int Times)>();
			string special = null;
			CollectDamage(w, rules, 1, hits, ref special);
			var damage = hits.Select(h => h.Warhead).ToList();
			var perShot = hits.Sum(h => h.Warhead.Damage * h.Times);
			var burstDelay = w.BurstDelays.Length == 1 ? w.BurstDelays[0] * (w.Burst - 1) : w.BurstDelays.Take(w.Burst - 1).Sum();
			var cycle = Math.Max(1, w.ReloadDelay + burstDelay);
			var id = key.Replace('.', '-').ToLowerInvariant();
			var label = Text($"catalogue-weapon-{id}");

			// A jet's .Pair / .Ripple variant is the same weapon as its family
			foreach (var suffix in new[] { "-pair", "-ripple" })
				if (label == null && id.EndsWith(suffix, StringComparison.Ordinal))
					label = Text($"catalogue-weapon-{id[..^suffix.Length]}");

			label ??= Pretty(key);

			bool Hits(params string[] types) => types.Any(t => w.ValidTargets.Contains(t)) && !types.All(t => w.InvalidTargets.Contains(t));

			var weapon = new Weapon
			{
				Name = label,
				Kind = special ?? (perShot <= 0 && w.Warheads.Any(h => h is PxSpawnActorWarhead) ? "Target marker" : ProjectileKind(w)),
				Note = Text($"catalogue-weapon-note-{id}"),
				Damage = perShot,
				Burst = w.Burst,
				Range = w.Range.Length / 1024f,
				MinRange = w.MinRange.Length / 1024f,
				Reload = cycle / (float)Ticks,
				Dps = Math.Max(0, perShot) * w.Burst * Ticks / (float)cycle,
				Air = Hits("Air", "AirborneActor"),
				Ground = Hits("Ground", "GroundActor", "Infantry", "Vehicle", "Structure"),
				Naval = Hits("Water", "WaterActor", "Underwater", "Submarine", "Ship"),
				Support = perShot <= 0 || Hits("Heal", "Repair"),
			};

			weapon.Versus = Classes.Select(c =>
			{
				if (weapon.Support || perShot <= 0)
					return 0;

				var reach = c.Targets.Any(t => w.ValidTargets.Contains(t));
				if (!reach)
					return 0;

				var pct = c.Armor.Select(armor => damage.Select(d => d.Versus.TryGetValue(armor, out var v) ? v : 100).DefaultIfEmpty(100).Max()).Average();
				return (int)pct;
			}).ToArray();

			return weapon;
		}

		/// <summary>Airborne Base and transports (IDEA-42): the troops a transport drops are no armament, so they are listed here.</summary>
		void AddAirliftFeatures(Entry e)
		{
			var airlift = e.Actor.TraitInfoOrDefault<PxAirliftInfo>();
			if (airlift != null)
			{
				var total = airlift.Troops.Values.Sum();
				var troops = string.Join(", ", airlift.Troops.Select(kv =>
					$"{kv.Value} {(rules.Actors.TryGetValue(kv.Key.ToLowerInvariant(), out var t) ? ActorName(t) : kv.Key)}"));
				e.Features.Add($"Airborne drop: {total} paratroopers ({troops})");

				var pool = e.Actor.TraitInfos<AmmoPoolInfo>().FirstOrDefault(p => p.Name == airlift.AmmoPool);
				if (pool != null)
				{
					var seconds = pool.Ammo * pool.ReloadDelay / pool.ReloadCount / Ticks;
					e.Features.Add($"Reloads its paratroopers on its pad in {seconds} s, paying their price");
				}
			}

			if (e.Actor.HasTraitInfo<PxAirliftBaseInfo>())
			{
				var pads = e.Actor.TraitInfoOrDefault<ReservableInfo>()?.SlotOffsets.Length ?? 0;
				e.Features.Add($"{pads} transport pads: builds and reloads airborne transports only");
			}
		}

		static void AddFeatures(Entry e, AircraftInfo aircraft, MobileInfo mobile)
		{
			var f = e.Features;
			void Add(string s)
			{
				if (!f.Contains(s))
					f.Add(s);
			}

			if (e.Weapons.Any(w => w.Air && !w.Support))
				Add(e.Weapons.All(w => w.Air && !w.Ground) ? "Dedicated anti-air" : "Can engage aircraft");
			if (e.Weapons.Any(w => w.Naval && !w.Support && w.Kind == "Torpedo"))
				Add("Anti-ship torpedoes");
			if (e.Weapons.Any(w => w.Support && w.Name.Contains("Heal", StringComparison.OrdinalIgnoreCase)))
				Add("Heals nearby infantry");
			if (e.Weapons.Any(w => w.Support && w.Name.Contains("Repair", StringComparison.OrdinalIgnoreCase)))
				Add("Field-repairs vehicles");
			if (e.Power > 0)
				Add($"Generates {e.Power} power");

			if (aircraft != null)
				Add(aircraft.VTOL ? "VTOL: hovers and lands anywhere" : "Fast jet: strikes, then returns to rearm");
			if (mobile?.Locomotor != null && mobile.Locomotor.Contains("amph", StringComparison.OrdinalIgnoreCase))
				Add("Amphibious");
			if (mobile?.Locomotor == "crocodile")
				Add("Swims, faster in water than on land");

			foreach (var t in e.Actor.TraitInfos<TraitInfo>())
			{
				switch (t)
				{
					case DetectCloakedInfo: Add("Detects stealth units"); break;
					case CloakInfo when mobile?.Locomotor == "crocodile": Add("Lurks unseen in water when still"); break;
					case CloakInfo: Add(mobile?.Locomotor == "naval" ? "Submerges out of sight" : "Stealth: invisible when idle"); break;
					case CargoInfo c when c.MaxWeight > 0: Add($"Transports {c.MaxWeight} soldiers"); break;
					case CapturesInfo: Add("Captures enemy buildings"); break;
					case RepairsUnitsInfo: Add("Repairs docked vehicles"); break;
					case RepairsBridgesInfo: Add("Repairs bridges"); break;
					case HarvesterInfo: Add("Harvests ore and gems"); break;
					case RefineryInfo: Add("Refines ore into credits"); break;
					case StoresPlayerResourcesInfo: Add("Stores credits"); break;
					case ProductionInfo p: Add("Produces " + string.Join(", ", p.Produces.Select(x => x.ToLowerInvariant()))); break;
					case CreatesShroudInfo: Add("Hides your base in a shroud field"); break;
					case SupportPowerInfo s when s.Name != null: Add("Support power: " + FluentProvider.GetMessage(s.Name)); break;
					case MinelayerInfo: Add("Lays minefields"); break;
					case PxCivilianDisguiseInfo: Add("Disguises as a civilian car"); break;
					case PxInterceptorInfo: Add("Intercepts incoming missiles"); break;
					case PxPointDefenseInfo: Add("Point defence vs missiles"); break;
					case PxFlareDispenserInfo fd when fd.Style == Effects.PxFlareStyle.Angel:
						Add($"Angel flares: {fd.Salvos} huge salvos fool {fd.DecoyChance}% of guided missiles");
						break;
					case PxFlareDispenserInfo fd: Add($"Flares: {fd.Salvos} salvos fool {fd.DecoyChance}% of guided missiles"); break;
					case JamsMissilesInfo: Add("Jams guided missiles"); break;
					case PxShootAndScootInfo: Add("Shoot and scoot"); break;
					case PxTrampleInfo: Add("Tramples infantry underfoot: they cannot dodge"); break;
					case PxCarrierDeckInfo: Add("Flight deck: launches and rearms jets"); break;
					case PxPrismRelayInfo: Add("Relays and amplifies prism beams"); break;
					case CashTricklerInfo: Add("Generates steady income"); break;
					case BaseProviderInfo: Add("Extends the build radius"); break;
					case GainsExperienceInfo: Add("Earns veterancy ranks"); break;
					case ParaDropInfo: Add("Drops paratroopers"); break;
				}

				// Traits from OpenRA.Mods.Cnc (not referenced) or not public
				switch (t.GetType().Name)
				{
					case "ChangesHealthInfo": Add("Self-repairs over time"); break;
					case "ProvidesRadarInfo": Add("Provides the radar minimap"); break;
					case "DemolitionInfo": Add("Plants demolition charges"); break;
					case "DisguiseInfo": Add("Disguises as enemy soldiers"); break;
					case "InfiltratesInfo": Add("Infiltrates enemy buildings"); break;
					case "MadTankInfo": Add("Seismic shockwave (self-destructs)"); break;
					case "AttackLeapInfo": Add("Leaps at its prey"); break;
					case "PortableChronoInfo": Add("Teleports short distances"); break;
				}
			}
		}

		void Grade()
		{
			foreach (var c in Categories)
			{
				var list = Entries.Where(e => e.Category == c).ToList();
				CategoryMax["hp-" + c] = Percentile(list.Select(e => (float)e.HP), 0.95f);
				CategoryMax["dps-" + c] = Percentile(list.Select(e => e.Dps), 0.95f);
				CategoryMax["range-" + c] = Percentile(list.Select(e => e.Range), 1f);
				CategoryMax["speed-" + c] = Percentile(list.Select(e => e.Speed), 1f);
				CategoryMax["sight-" + c] = Percentile(list.Select(e => e.Sight), 1f);
			}

			// Damage output against each class, graded against the strongest units in the whole catalogue
			var raw = Entries.ToDictionary(e => e, e => Classes.Select((_, i) =>
				e.Weapons.Select(w => w.Dps * w.Versus[i] / 100f).DefaultIfEmpty(0).Max()).ToArray());
			var top = Enumerable.Range(0, Classes.Length).Select(i => Percentile(raw.Values.Select(v => v[i]), 0.9f)).ToArray();
			foreach (var e in Entries)
				e.Effect = raw[e].Select((v, i) => top[i] > 0 ? Math.Min(1f, (float)Math.Sqrt(v / top[i])) : 0).ToArray();
		}

		static float Percentile(IEnumerable<float> values, float p)
		{
			var v = values.Where(x => x > 0).OrderBy(x => x).ToList();
			if (v.Count == 0)
				return 1;

			return Math.Max(0.001f, v[Math.Min(v.Count - 1, (int)(p * (v.Count - 1) + 0.5f))]);
		}

		public static string GradeLetter(float f) => f <= 0 ? "-" : f >= 0.85f ? "S" : f >= 0.65f ? "A" : f >= 0.45f ? "B" : f >= 0.25f ? "C" : "D";
	}
}
