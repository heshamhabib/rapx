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

using System.Linq;
using OpenRA.GameRules;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Warheads;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Warheads
{
	[Desc("Places an actor owned by the firing player in the cell it lands on, e.g. a scattered anti-tank mine",
		"(IDEA-17 MARZ II mine rockets). Only on free cells whose terrain has one of TerrainTypes.")]
	public class PxSpawnActorWarhead : Warhead
	{
		[ActorReference]
		[FieldLoader.Require]
		[Desc("Actor to place.")]
		public readonly string Actor = null;

		[Desc("Terrain target types the actor may be placed on.")]
		public readonly BitSet<TargetableType> TerrainTypes = new("Ground");

		public override void DoImpact(in Target target, WarheadArgs args)
		{
			if (target.Type == TargetType.Invalid || args.SourceActor == null)
				return;

			var world = args.SourceActor.World;
			var owner = args.SourceActor.Owner;
			var cell = world.Map.CellContaining(target.CenterPosition);
			if (!world.Map.Contains(cell) || !TerrainTypes.Overlaps(world.Map.GetTerrainInfo(cell).TargetTypes))
				return;

			world.AddFrameEndTask(w =>
			{
				// Checked when placing: two bomblets may land in the same cell in one tick
				if (w.ActorMap.GetActorsAt(cell).Any())
					return;

				w.CreateActor(Actor, new TypeDictionary
				{
					new LocationInit(cell),
					new OwnerInit(owner),
					new FactionInit(owner.Faction.InternalName),
				});
			});
		}
	}
}
