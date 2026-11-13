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
	[TraitLocation(SystemActors.Player)]
	[Desc("Bot module for unarmed vehicles with one job, which the squads can't use:",
		"MAD Tanks drive into the densest, most valuable group of enemy buildings and shake them apart,",
		"Supply Trucks bring their cash to the poorest ally (or back to the own base when there is none),",
		"crushers (Monster Truck) run over enemy infantry.")]
	public class PxSpecialVehiclesBotModuleInfo : ConditionalTraitInfo
	{
		[Desc("Actor types of the MAD Tanks (MadTank, ordered with DetonateAttack).")]
		public readonly HashSet<string> MadTankTypes = new();

		[Desc("Radius of the MAD Tank's shock wave: the enemy buildings inside it are what a spot is worth.")]
		public readonly WDist MadTankRadius = WDist.FromCells(7);

		[Desc("Actor types of the Supply Trucks (DeliversCash).")]
		public readonly HashSet<string> SupplyTruckTypes = new();

		[Desc("Actor types of the unarmed crushers.")]
		public readonly HashSet<string> CrusherTypes = new();

		[Desc("Target type of what the crushers run over.")]
		public readonly BitSet<TargetableType> CrushTargetType = new("Infantry");

		[Desc("Crushers look for enemy infantry this far away.")]
		public readonly WDist CrushScanRadius = WDist.FromCells(25);

		[Desc("Ticks between two looks for idle vehicles.")]
		public readonly int ScanInterval = 100;

		public override object Create(ActorInitializer init) { return new PxSpecialVehiclesBotModule(init.Self, this); }
	}

	public class PxSpecialVehiclesBotModule : ConditionalTrait<PxSpecialVehiclesBotModuleInfo>, IBotTick
	{
		readonly World world;
		readonly Player player;
		int ticks;

		public PxSpecialVehiclesBotModule(Actor self, PxSpecialVehiclesBotModuleInfo info)
			: base(info)
		{
			world = self.World;
			player = self.Owner;
		}

		protected override void TraitEnabled(Actor self)
		{
			ticks = world.LocalRandom.Next(Info.ScanInterval);
		}

		void IBotTick.BotTick(IBot bot)
		{
			if (--ticks > 0)
				return;

			ticks = Info.ScanInterval;

			var idle = world.Actors
				.Where(a => a.Owner == player && !a.IsDead && a.IsInWorld && a.IsIdle)
				.ToList();

			List<Actor> enemyBuildings = null;
			foreach (var a in idle)
			{
				var name = a.Info.Name;
				if (Info.MadTankTypes.Contains(name))
				{
					enemyBuildings ??= PxBotUtils.VisibleEnemyBuildings(world, player);
					OrderMadTank(bot, a, enemyBuildings);
				}
				else if (Info.SupplyTruckTypes.Contains(name))
					OrderSupplyTruck(bot, a);
				else if (Info.CrusherTypes.Contains(name))
					OrderCrusher(bot, a);
			}
		}

		void OrderMadTank(IBot bot, Actor tank, List<Actor> enemyBuildings)
		{
			// The building whose neighbourhood holds the most enemy building value
			var radiusSquared = Info.MadTankRadius.LengthSquared;
			Actor best = null;
			var bestValue = 0;
			foreach (var b in enemyBuildings)
			{
				var value = enemyBuildings
					.Where(o => (o.CenterPosition - b.CenterPosition).HorizontalLengthSquared <= radiusSquared)
					.Sum(o => o.Info.TraitInfoOrDefault<ValuedInfo>()?.Cost ?? 0);

				if (value > bestValue)
				{
					best = b;
					bestValue = value;
				}
			}

			if (best == null)
				return;

			AIUtils.BotDebug($"{player.ResolvedPlayerName} sends {tank.Info.Name} to blow up next to {best.Info.Name} ({bestValue} worth around).");
			bot.QueueOrder(new Order("DetonateAttack", tank, Target.FromActor(best), false));
		}

		void OrderSupplyTruck(IBot bot, Actor truck)
		{
			// Cash only helps an ally; to the own base it just pays the truck back
			var receivers = world.ActorsHavingTrait<AcceptsDeliveredCash>()
				.Where(a => !a.IsDead && a.IsInWorld && a.Owner.IsAlliedWith(player) && !a.Owner.NonCombatant)
				.ToList();

			var allies = receivers.Where(a => a.Owner != player).ToList();
			var pool = allies.Count > 0
				? allies.GroupBy(a => a.Owner).OrderBy(g => g.Key.PlayerActor.Trait<PlayerResources>().GetCashAndResources()).First().ToList()
				: receivers.Where(a => a.Owner == player).ToList();

			var target = pool.MinByOrDefault(a => (a.CenterPosition - truck.CenterPosition).HorizontalLengthSquared);
			if (target == null)
				return;

			AIUtils.BotDebug($"{player.ResolvedPlayerName} sends {truck.Info.Name} with cash to {target.Owner.ResolvedPlayerName}.");
			bot.QueueOrder(new Order("DeliverCash", truck, Target.FromActor(target), false));
		}

		void OrderCrusher(IBot bot, Actor crusher)
		{
			var victim = world.FindActorsInCircle(crusher.CenterPosition, Info.CrushScanRadius)
				.Where(a => !a.IsDead && a.IsInWorld && player.RelationshipWith(a.Owner) == PlayerRelationship.Enemy
					&& a.GetEnabledTargetTypes().Overlaps(Info.CrushTargetType) && a.CanBeViewedByPlayer(player))
				.MinByOrDefault(a => (a.CenterPosition - crusher.CenterPosition).HorizontalLengthSquared);

			if (victim == null)
				return;

			bot.QueueOrder(new Order("Move", crusher, Target.FromCell(world, victim.Location), false));
		}
	}
}
