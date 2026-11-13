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
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	/// <summary>Helpers shared by the RAPX bot modules.</summary>
	public static class PxBotUtils
	{
		/// <summary>Enemy ground units and defences around pos whose weapons can hit targets of the given type.</summary>
		public static int CountAntiAir(World world, Player player, WPos pos, WDist radius, BitSet<TargetableType> aircraftType)
		{
			var count = 0;
			foreach (var a in world.FindActorsInCircle(pos, radius))
			{
				if (a.IsDead || player.RelationshipWith(a.Owner) != PlayerRelationship.Enemy || a.Info.HasTraitInfo<AircraftInfo>())
					continue;

				foreach (var ab in a.TraitsImplementing<AttackBase>())
				{
					if (ab.IsTraitDisabled || !ab.Armaments.Any(arm => arm.Weapon.IsValidTarget(aircraftType)))
						continue;

					count++;
					break;
				}
			}

			return count;
		}

		/// <summary>Enemy buildings the player can see.</summary>
		public static List<Actor> VisibleEnemyBuildings(World world, Player player)
		{
			return world.ActorsHavingTrait<Building>()
				.Where(a => !a.IsDead && a.IsInWorld && player.RelationshipWith(a.Owner) == PlayerRelationship.Enemy
					&& a.CanBeViewedByPlayer(player) && !a.Info.HasTraitInfo<HuskInfo>())
				.ToList();
		}

		/// <summary>Of up to options random targets, the one with the least anti-air around it (null when none).</summary>
		public static Actor LeastDefended(World world, Player player, List<Actor> targets, int options, WDist radius,
			BitSet<TargetableType> aircraftType, out int antiAir)
		{
			Actor best = null;
			antiAir = int.MaxValue;
			foreach (var target in targets.Shuffle(world.LocalRandom).Take(options))
			{
				var count = CountAntiAir(world, player, target.CenterPosition, radius, aircraftType);
				if (count < antiAir)
				{
					best = target;
					antiAir = count;
				}
			}

			return best;
		}

		/// <summary>A cell up to scatter cells away from the actor's location, inside the map.</summary>
		public static CPos ScatterCell(World world, Actor target, int scatter)
		{
			var cell = target.Location + new CVec(
				world.LocalRandom.Next(-scatter, scatter + 1),
				world.LocalRandom.Next(-scatter, scatter + 1));

			return world.Map.Contains(cell) ? cell : target.Location;
		}

		/// <summary>A random building of the player (its base), or null.</summary>
		public static Actor RandomOwnBuilding(World world, Player player)
		{
			return world.ActorsHavingTrait<Building>()
				.Where(a => a.Owner == player && !a.IsDead && a.IsInWorld)
				.RandomOrDefault(world.LocalRandom);
		}
	}
}
