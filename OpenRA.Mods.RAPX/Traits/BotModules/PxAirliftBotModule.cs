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
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.Player)]
	[Desc("Bot module: sends the bot's loaded airborne transports (PxAirlift) to drop their troops next to the enemy",
		"building with the least anti-air around it. Transports wait on their pad while every target is too well defended.")]
	public class PxAirliftBotModuleInfo : ConditionalTraitInfo
	{
		[Desc("Ticks between two looks for transports ready to go.")]
		public readonly int ScanInterval = 150;

		[Desc("Only transports at least this full (percent of a full load) take off.")]
		public readonly int MinimumLoadPercent = 75;

		[Desc("Enemy buildings looked at per transport (picked at random).")]
		public readonly int TargetOptions = 20;

		[Desc("Radius around a target in which enemy anti-air is counted.")]
		public readonly WDist AntiAirScanRadius = WDist.FromCells(9);

		[Desc("Don't drop where more anti-air units than this cover the target.")]
		public readonly int MaximumAntiAir = 2;

		[Desc("Target type of the transports, to tell which enemy weapons can hit them.")]
		public readonly BitSet<TargetableType> AircraftTargetType = new("AirborneActor");

		[Desc("The troops land up to this far from the target building.")]
		public readonly int DropScatter = 3;

		public override object Create(ActorInitializer init) { return new PxAirliftBotModule(init.Self, this); }
	}

	public class PxAirliftBotModule : ConditionalTrait<PxAirliftBotModuleInfo>, IBotTick
	{
		readonly World world;
		readonly Player player;
		int ticks;

		public PxAirliftBotModule(Actor self, PxAirliftBotModuleInfo info)
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

			var transports = world.ActorsWithTrait<PxAirlift>()
				.Where(p => p.Actor.Owner == player && !p.Actor.IsDead && p.Actor.IsInWorld && p.Actor.IsIdle
					&& !p.Trait.DropOrdered && p.Trait.Capacity > 0
					&& p.Trait.Aboard * 100 >= p.Trait.Capacity * Info.MinimumLoadPercent)
				.ToList();

			if (transports.Count == 0)
				return;

			var targets = PxBotUtils.VisibleEnemyBuildings(world, player);
			if (targets.Count == 0)
				return;

			foreach (var t in transports)
			{
				var best = PxBotUtils.LeastDefended(world, player, targets, Info.TargetOptions, Info.AntiAirScanRadius,
					Info.AircraftTargetType, out var antiAir);

				if (best == null || antiAir > Info.MaximumAntiAir)
					continue;

				var cell = PxBotUtils.ScatterCell(world, best, Info.DropScatter);
				AIUtils.BotDebug($"{player.ResolvedPlayerName} airdrops {t.Actor.Info.Name} next to {best.Info.Name} at {cell}.");
				bot.QueueOrder(new Order("PxAirdrop", t.Actor, Target.FromCell(world, cell), false));
			}
		}
	}
}
