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
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Scripting;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.RAPX.Widgets;
using OpenRA.Network;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Loads only the art a match can show: other nations' units, aircraft, ships and building styles stay unloaded",
		"and load the moment something asks for them. The menu's map loads no art up front; it fills the shared sprite store",
		"in the background instead (art every match needs first, then the nations picked in the lobby).")]
	public class PxSpriteLoadPolicyInfo : TraitInfo, ISpriteLoadPolicyInfo
	{
		[Desc("Actor every nation starts from, for working out what each nation can build.")]
		public readonly string SeedActor = "fact";

		[Desc("Background threads decoding art while the menu is up.")]
		public readonly int PrefetchThreads = 4;

		[Desc("Milliseconds per tick the menu spends packing prefetched art into sprite sheets.")]
		public readonly int PrefetchBudget = 6;

		// RAPX_LOAD_ALL_SPRITES=1 loads every image when a map loads, as before, for comparisons
		static readonly bool LoadAll = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_LOAD_ALL_SPRITES"));

		public override object Create(ActorInitializer init) { return new PxSpriteLoadPolicy(init.World, this); }

		Func<string, bool> ISpriteLoadPolicyInfo.DeferredImages(ModData modData, Map map, WorldType type, Session lobbyInfo)
		{
			if (LoadAll || Game.Renderer == null)
				return null;

			// The menu's map shows no units: everything loads on first use or in the background
			if (type == WorldType.Shellmap)
				return _ => true;

			if (type != WorldType.Regular || lobbyInfo == null)
				return null;

			// Scripted maps can create any unit for any nation at any moment
			if (map.Rules.Actors[SystemActors.World].TraitInfos<LuaScriptInfo>().Any(l => l.Scripts.Count > 0))
				return null;

			var present = PresentNations(map.Rules, lobbyInfo);
			if (present.Count == 0)
				return null;

			var scope = PxSpriteScope.For(map.Rules, SeedActor);
			var deferred = scope.Restricted.Where(kv => !kv.Value.Overlaps(present)).Select(kv => kv.Key).ToHashSet();

			// Actors placed on the map are there from the start, whoever owns them
			var factions = map.Rules.Actors[SystemActors.World].TraitInfos<FactionInfo>().Select(f => f.InternalName).ToList();
			foreach (var node in map.ActorDefinitions)
			{
				if (node.Value.Value == null || !map.Rules.Actors.TryGetValue(node.Value.Value.ToLowerInvariant(), out var actor))
					continue;

				var rs = actor.TraitInfoOrDefault<RenderSpritesInfo>();
				if (rs == null)
					continue;

				deferred.Remove(rs.GetImage(actor, null));
				foreach (var f in factions)
					deferred.Remove(rs.GetImage(actor, f));
			}

			return deferred.Contains;
		}

		/// <summary>The nations in a match: every non-spectator's faction, random picks standing for all they can become.</summary>
		public static HashSet<string> PresentNations(Ruleset rules, Session lobby)
		{
			var factions = new Dictionary<string, FactionInfo>();
			foreach (var f in rules.Actors[SystemActors.World].TraitInfos<FactionInfo>())
				if (f.InternalName != null)
					factions.TryAdd(f.InternalName, f);

			var result = new HashSet<string>();
			void Add(string name, int depth)
			{
				if (name == null || depth > 4 || !factions.TryGetValue(name, out var faction))
					return;

				if (faction.RandomFactionMembers.Count == 0)
					result.Add(name);
				else
					foreach (var member in faction.RandomFactionMembers)
						Add(member, depth + 1);
			}

			foreach (var c in lobby.Clients)
				if (!c.IsObserver)
					Add(c.Faction, 0);

			return result;
		}
	}

	/// <summary>Drives the background prefetch on the menu's map.</summary>
	public class PxSpriteLoadPolicy : ITick
	{
		readonly PxSpriteLoadPolicyInfo info;
		readonly World world;
		readonly HashSet<string> prefetchedNations = new();
		long started = -1;
		bool reported;

		public PxSpriteLoadPolicy(World world, PxSpriteLoadPolicyInfo info)
		{
			this.world = world;
			this.info = info;
		}

		void ITick.Tick(Actor self)
		{
			if (world.Type != WorldType.Shellmap)
				return;

			var sequences = world.Map.Sequences;
			if (sequences.DeferredImages.Count == 0)
				return;

			// The intro video plays over the menu: leave the processors to it
			if (Ui.Root.GetOrNull("INTRO_VIDEO") != null)
				return;

			var scope = PxSpriteScope.For(world.Map.Rules, info.SeedActor);
			if (started < 0)
			{
				// Art every match needs first, then whatever the lobby's nations need
				started = Game.RunTime;
				sequences.Prefetch(sequences.DeferredImages.Where(i => !scope.Restricted.ContainsKey(i)).ToList(), info.PrefetchThreads);
			}

			var lobby = PxLobbyState.OrderManager?.LobbyInfo;
			if (lobby != null)
			{
				var nations = PxSpriteLoadPolicyInfo.PresentNations(world.Map.Rules, lobby);
				if (!nations.IsSubsetOf(prefetchedNations))
				{
					prefetchedNations.UnionWith(nations);
					sequences.Prefetch(scope.Restricted.Where(kv => kv.Value.Overlaps(nations)).Select(kv => kv.Key).ToList(),
						info.PrefetchThreads);
					reported = false;
				}
			}

			if (!sequences.PrefetchStep(info.PrefetchBudget) && !reported)
			{
				reported = true;
				var (packed, queued) = sequences.PrefetchProgress;
				Log.Write("perf", $"PxSpriteLoadPolicy: prefetched {packed} of {queued} files, {Game.RunTime - started} ms after it started");
			}
		}
	}

	/// <summary>
	/// Which images only some nations can ever field, worked out once per ruleset: the nations that can build each actor
	/// (the catalogue's prerequisite closure), carried along actor references (husks, spawned units) to the actors those
	/// make, then to the images they draw. Every image not listed is needed in any match.
	/// </summary>
	public sealed class PxSpriteScope
	{
		static readonly ConditionalWeakTable<Ruleset, PxSpriteScope> Cache = new();
		enum Kind { Actors, Images }

		static readonly Dictionary<(Type Type, Kind Kind), FieldInfo[]> FieldCache = new();

		/// <summary>Image -> the nations whose presence needs it.</summary>
		public readonly Dictionary<string, HashSet<string>> Restricted = new();

		public static PxSpriteScope For(Ruleset rules, string seedActor)
		{
			lock (Cache)
				return Cache.GetValue(rules, r => new PxSpriteScope(r, seedActor));
		}

		PxSpriteScope(Ruleset rules, string seedActor)
		{
			var built = PxCatalogueData.NationAvailability(rules, seedActor);
			var actors = rules.Actors.Values.Where(a => !a.Name.StartsWith('^')).ToList();
			var names = actors.Select(a => a.Name).ToHashSet();

			// Actors that other actors' traits refer to (husks, spawned units, paratroopers...); weapons can make theirs anywhere.
			// The player actor's lists (AI build orders, sidebar categories) name units without making them: what a player
			// can have is decided by the prerequisites above, so they do not count.
			var parents = new Dictionary<string, List<string>>();
			var everywhere = new HashSet<string>();
			foreach (var a in actors)
			{
				if (a.Name == SystemActors.Player.ToString().ToLowerInvariant())
					continue;

				foreach (var ti in a.TraitInfos<TraitInfo>())
					foreach (var child in Strings(ti, Kind.Actors))
						if (names.Contains(child.ToLowerInvariant()))
							parents.GetOrAdd(child.ToLowerInvariant()).Add(a.Name);
			}

			foreach (var w in rules.Weapons.Values)
				foreach (var part in Parts(w))
					foreach (var child in Strings(part, Kind.Actors))
						everywhere.Add(child.ToLowerInvariant());

			// Who can have each actor: its builders, plus whoever can have an actor that refers to it. Actors that nobody
			// builds and nothing refers to (map decorations, support power and script units) can turn up in any match.
			var nationsOf = new Dictionary<string, HashSet<string>>();
			foreach (var a in actors)
			{
				if (built.TryGetValue(a.Name, out var b))
					nationsOf[a.Name] = new HashSet<string>(b);
				else if (!parents.ContainsKey(a.Name))
					everywhere.Add(a.Name);
			}

			bool changed;
			do
			{
				changed = false;
				foreach (var a in actors)
				{
					if (everywhere.Contains(a.Name) || !parents.TryGetValue(a.Name, out var ps))
						continue;

					if (ps.Any(everywhere.Contains))
					{
						everywhere.Add(a.Name);
						nationsOf.Remove(a.Name);
						changed = true;
						continue;
					}

					foreach (var p in ps)
					{
						if (!nationsOf.TryGetValue(p, out var pn))
							continue;

						var own = nationsOf.GetOrAdd(a.Name);
						var before = own.Count;
						own.UnionWith(pn);
						changed |= own.Count != before;
					}
				}
			}
			while (changed);

			// Only reachable from actors nobody can have (a closed loop of references): count as possible anywhere
			foreach (var a in actors)
				if (!nationsOf.ContainsKey(a.Name))
					everywhere.Add(a.Name);

			var factions = rules.Actors[SystemActors.World].TraitInfos<FactionInfo>().Select(f => f.InternalName).Where(f => f != null)
				.Distinct().ToList();
			var always = new HashSet<string>();
			void Mark(string image, HashSet<string> nations)
			{
				if (string.IsNullOrEmpty(image))
					return;

				if (nations == null)
					always.Add(image);
				else
					Restricted.GetOrAdd(image).UnionWith(nations);
			}

			foreach (var a in actors)
			{
				var nations = everywhere.Contains(a.Name) ? null : nationsOf[a.Name];
				var rs = a.TraitInfoOrDefault<RenderSpritesInfo>();
				if (rs != null)
				{
					if (nations == null)
					{
						Mark(rs.GetImage(a, null), null);
						foreach (var f in factions)
							Mark(rs.GetImage(a, f), null);
					}
					else
						foreach (var n in nations)
							Mark(rs.GetImage(a, n), new HashSet<string> { n });
				}

				// Images its other traits draw (overlays, effects...) go wherever the actor goes
				foreach (var ti in a.TraitInfos<TraitInfo>())
					if (ti is not RenderSpritesInfo)
						foreach (var s in Strings(ti, Kind.Images))
							Mark(s, nations);
			}

			// Projectile and explosion images can show up in any match
			foreach (var w in rules.Weapons.Values)
				foreach (var part in Parts(w))
					foreach (var s in Strings(part, Kind.Images))
						Mark(s, null);

			foreach (var image in always)
				Restricted.Remove(image);
		}

		static IEnumerable<object> Parts(WeaponInfo weapon)
		{
			if (weapon.Projectile != null)
				yield return weapon.Projectile;

			foreach (var warhead in weapon.Warheads)
				yield return warhead;
		}

		/// <summary>
		/// The fields of a trait info or weapon part that name actors ([ActorReference]; AI modules only list what to build)
		/// or images: those a [SequenceReference] names as its image, and any field called *Image* (RAPX traits).
		/// </summary>
		static FieldInfo[] Fields(Type type, Kind kind)
		{
			lock (FieldCache)
			{
				if (!FieldCache.TryGetValue((type, kind), out var fields))
				{
					var all = type.GetFields(BindingFlags.Public | BindingFlags.Instance);
					if (kind == Kind.Actors)
						fields = type.Name.EndsWith("BotModuleInfo", StringComparison.Ordinal) ? Array.Empty<FieldInfo>() :
							all.Where(f => f.GetCustomAttribute<ActorReferenceAttribute>() != null).ToArray();
					else
					{
						var named = all.Select(f => f.GetCustomAttribute<SequenceReferenceAttribute>()?.ImageReference)
							.Where(n => n != null).ToHashSet();
						fields = all.Where(f => named.Contains(f.Name) || f.Name.Contains("Image", StringComparison.Ordinal)).ToArray();
					}

					FieldCache[(type, kind)] = fields;
				}

				return fields;
			}
		}

		/// <summary>The strings in those fields (lists, sets and dictionaries too).</summary>
		static IEnumerable<string> Strings(object o, Kind kind)
		{
			foreach (var field in Fields(o.GetType(), kind))
			{
				switch (field.GetValue(o))
				{
					case string s:
						yield return s;
						break;
					case IDictionary d:
						foreach (DictionaryEntry e in d)
						{
							if (e.Key is string k)
								yield return k;

							if (e.Value is string v)
								yield return v;
							else if (e.Value is IEnumerable<string> vs)
								foreach (var x in vs)
									if (x != null)
										yield return x;
						}

						break;
					case IEnumerable<string> list:
						foreach (var x in list)
							if (x != null)
								yield return x;

						break;
				}
			}
		}
	}
}
