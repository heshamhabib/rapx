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

using System.Collections.Generic;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Titans: each player picks a giant (or none) in the lobby's TITAN column. It walks out next to their start when",
		"the game begins. One per player and never buildable: once it is killed it is gone for the rest of the game.")]
	public class PxTitanSpawnerInfo : TraitInfo, ILobbyTitanChoicesInfo
	{
		[FieldLoader.Require]
		[ActorReference(dictionaryReference: LintDictionaryReference.Values)]
		[Desc("Titan id (lower case letters/digits, sent in the lobby order) -> actor.")]
		public readonly Dictionary<string, string> Titans = new();

		[Desc("Titan id -> name shown in the lobby (default: the id).")]
		public readonly Dictionary<string, string> Names = new();

		[Desc("Titan id -> short line under its name in the lobby (e.g. ATOMIC TITAN). Ids none and random too.")]
		public readonly Dictionary<string, string> Subtitles = new();

		[Desc("Titan id -> what it does, shown on its picker card. Ids none and random too.")]
		public readonly Dictionary<string, string> Specials = new();

		[Desc("Titan id -> accent colour of its lobby box and card. Ids none and random too.")]
		public readonly Dictionary<string, Color> Colors = new();

		[Desc("Lobby id that picks one of the titans at random when the game starts. Empty: no random entry.")]
		public readonly string RandomId = "random";

		public readonly string RandomName = "Random";

		[Desc("The titan appears this many cells from the player's start, on the side facing the map centre.")]
		public readonly int MinDistance = 5;

		public readonly int MaxDistance = 12;

		IReadOnlyList<(string Id, string Name)> choices;

		IReadOnlyList<(string Id, string Name)> ILobbyTitanChoicesInfo.TitanChoices
		{
			get
			{
				if (choices == null)
				{
					var list = Titans.Keys.Select(id => (id, Names.TryGetValue(id, out var n) ? n : id)).ToList();
					if (!string.IsNullOrEmpty(RandomId) && list.Count > 1)
						list.Add((RandomId, RandomName));

					choices = list;
				}

				return choices;
			}
		}

		public override object Create(ActorInitializer init) { return new PxTitanSpawner(this); }
	}

	public class PxTitanSpawner : IWorldLoaded
	{
		readonly PxTitanSpawnerInfo info;

		public PxTitanSpawner(PxTitanSpawnerInfo info)
		{
			this.info = info;
		}

		void IWorldLoaded.WorldLoaded(World world, WorldRenderer wr)
		{
			// Developer check: RAPX_TITAN_SPAWN_AUDIT=1 logs, for every start location of the map, where each titan would be
			// placed and whether that cell connects to the start
			if (System.Environment.GetEnvironmentVariable("RAPX_TITAN_SPAWN_AUDIT") == "1")
				world.AddFrameEndTask(w => Audit(w));

			var ids = info.Titans.Keys.OrderBy(k => k).ToList();
			foreach (var player in world.Players)
			{
				if (player.NonCombatant || !player.Playable)
					continue;

				// By slot, not ClientIndex: map players (Creeps, Neutral) carry the host's index
				var id = world.LobbyInfo.ClientInSlot(player.InternalName)?.Titan;
				Log.Write("debug", $"PxTitanSpawner: slot {player.InternalName} ({player.PlayerName}) titan '{id}'");
				if (string.IsNullOrEmpty(id))
					continue;

				if (id == info.RandomId && ids.Count > 0)
					id = ids[world.SharedRandom.Next(ids.Count)];

				// Actor names are stored lower case (Ruleset), whatever the yaml spells them
				if (!info.Titans.TryGetValue(id, out var actorName))
					continue;

				actorName = actorName.ToLowerInvariant();

				var p = player;
				var name = actorName;

				// After every WorldLoaded, so the start units (MCV) already hold their cells
				world.AddFrameEndTask(w => Spawn(w, p, name));
			}
		}

		void Audit(World world)
		{
			var starts = world.Map.ActorDefinitions.Where(a => a.Value.Value == "mpspawn")
				.Select(a => new ActorReference(a.Value.Value, a.Value.ToDictionary()).Get<LocationInit>().Value).ToList();
			foreach (var actorName in info.Titans.Values.Distinct())
			{
				var mobile = world.Map.Rules.Actors[actorName.ToLowerInvariant()].TraitInfoOrDefault<MobileInfo>();
				var locomotor = world.WorldActor.TraitsImplementing<Locomotor>().First(l => l.Info.Name == mobile.Locomotor);
				var pathFinder = world.WorldActor.Trait<IPathFinder>();
				var centre = world.Map.CellContaining(world.Map.ProjectedBottomRight - (world.Map.ProjectedBottomRight - world.Map.ProjectedTopLeft) / 2);
				foreach (var home in starts)
				{
					var first = world.Map.FindTilesInAnnulus(home, info.MinDistance, info.MaxDistance)
						.Where(c => world.Map.Contains(c) && mobile.CanEnterCell(world, null, c, check: BlockedByActor.None))
						.OrderBy(c => (c - centre).LengthSquared + (c - home).LengthSquared)
						.Cast<CPos?>().FirstOrDefault();
					var ok = first != null && pathFinder.PathMightExistForLocomotorBlockedByImmovable(locomotor, home, first.Value);
					Log.Write("debug", $"PxTitanSpawner audit: {actorName} start {home}: old choice {first?.ToString() ?? "none"} reachable={ok}");
				}
			}
		}

		void Spawn(World world, Player player, string actorName)
		{
			var actorInfo = world.Map.Rules.Actors[actorName];
			var mobile = actorInfo.TraitInfoOrDefault<MobileInfo>();
			var home = player.HomeLocation;
			var centre = world.Map.CellContaining(world.Map.ProjectedBottomRight - (world.Map.ProjectedBottomRight - world.Map.ProjectedTopLeft) / 2);

			// Free cells around the start, preferring the side towards the middle of the map. Terrain only for the
			// locomotor (BlockedByActor.None): its actor checks need a real actor (crushables ask who crushes them).
			// The cell must also connect to the start on foot: a free cell can still be a pocket walled in by cliffs,
			// trees or buildings, and a titan put there could never leave it.
			var locomotor = mobile == null ? null : world.WorldActor.TraitsImplementing<Locomotor>().FirstOrDefault(l => l.Info.Name == mobile.Locomotor);
			var pathFinder = world.WorldActor.TraitOrDefault<IPathFinder>();
			bool Free(CPos c) => world.Map.Contains(c) && !world.ActorMap.AnyActorsAt(c)
				&& (mobile == null || mobile.CanEnterCell(world, null, c, check: BlockedByActor.None));
			bool Reachable(CPos c) => locomotor == null || pathFinder == null
				|| pathFinder.PathMightExistForLocomotorBlockedByImmovable(locomotor, home, c);

			CPos? cell = null;
			for (var max = info.MaxDistance; max <= info.MaxDistance * 3 && cell == null; max += info.MaxDistance)
			{
				var candidates = world.Map.FindTilesInAnnulus(home, info.MinDistance, max)
					.Where(Free)
					.OrderBy(c => (c - centre).LengthSquared + (c - home).LengthSquared)
					.ToList();
				cell = candidates.Where(Reachable).Cast<CPos?>().FirstOrDefault();
				if (candidates.Count > 0)
					Log.Write("debug", $"PxTitanSpawner: {actorName} for {player.PlayerName}: nearest free cell {candidates[0]} " +
						$"reachable={Reachable(candidates[0])}, chosen {cell?.ToString() ?? "none"} (search {max} cells)");
			}

			if (cell == null)
				return;

			var facing = (world.Map.CenterOfCell(centre) - world.Map.CenterOfCell(cell.Value)).Yaw;
			world.CreateActor(actorName, new TypeDictionary
			{
				new OwnerInit(player),
				new LocationInit(cell.Value),
				new FacingInit(facing),
			});
		}
	}
}
