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
	[Desc("Bot module: air assault with transport helicopters. An empty transport at home loads idle infantry from the",
		"base, flies them to the enemy building with the least anti-air around it, lands them next to it (or fast-ropes them",
		"down, PxAirAssault) and flies home.")]
	public class PxTransportBotModuleInfo : ConditionalTraitInfo
	{
		[Desc("Actor types of the transports (they need Cargo).")]
		public readonly HashSet<string> TransportTypes = new();

		[Desc("Actor types the transports carry.")]
		public readonly HashSet<string> PassengerTypes = new();

		[Desc("Ticks between two looks at the transports.")]
		public readonly int ScanInterval = 100;

		[Desc("Infantry this far from the transport is called aboard.")]
		public readonly WDist PickupRadius = WDist.FromCells(20);

		[Desc("A transport takes off with what it has once it has been loading this long.")]
		public readonly int LoadTimeout = 750;

		[Desc("Enemy buildings looked at per flight (picked at random).")]
		public readonly int TargetOptions = 20;

		[Desc("Radius around a target in which enemy anti-air is counted.")]
		public readonly WDist AntiAirScanRadius = WDist.FromCells(9);

		[Desc("Don't fly where more anti-air units than this cover the target.")]
		public readonly int MaximumAntiAir = 1;

		[Desc("Target type of the transports, to tell which enemy weapons can hit them.")]
		public readonly BitSet<TargetableType> AircraftTargetType = new("AirborneActor");

		[Desc("The transport lands up to this far from the target building.")]
		public readonly int LandingScatter = 4;

		[Desc("Chance (percent) that a transport able to fast-rope (PxAirAssault) ropes its troops down instead of landing.")]
		public readonly int FastRopeChance = 70;

		[Desc("A transport further than this from every own building counts as away from home.")]
		public readonly WDist HomeRadius = WDist.FromCells(15);

		public override object Create(ActorInitializer init) { return new PxTransportBotModule(init.Self, this); }
	}

	public class PxTransportBotModule : ConditionalTrait<PxTransportBotModuleInfo>, IBotTick
	{
		readonly World world;
		readonly Player player;

		// Transport -> tick its loading started
		readonly Dictionary<Actor, int> loadingSince = new();
		int ticks;

		public PxTransportBotModule(Actor self, PxTransportBotModuleInfo info)
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

			foreach (var gone in loadingSince.Keys.Where(a => a.IsDead || !a.IsInWorld).ToList())
				loadingSince.Remove(gone);

			var transports = world.ActorsWithTrait<Cargo>()
				.Where(t => t.Actor.Owner == player && !t.Actor.IsDead && t.Actor.IsInWorld && t.Actor.IsIdle
					&& Info.TransportTypes.Contains(t.Actor.Info.Name))
				.ToList();

			if (transports.Count == 0)
				return;

			var ownBuildings = world.ActorsHavingTrait<Building>()
				.Where(a => a.Owner == player && !a.IsDead && a.IsInWorld)
				.ToList();

			if (ownBuildings.Count == 0)
				return;

			List<Actor> targets = null;
			foreach (var t in transports)
			{
				var cargo = t.Trait;
				var transport = t.Actor;
				var atHome = ownBuildings.Any(b => (b.CenterPosition - transport.CenterPosition).HorizontalLengthSquared
					<= Info.HomeRadius.LengthSquared);

				if (cargo.IsEmpty())
				{
					loadingSince.Remove(transport);
					if (!atHome)
					{
						var home = ownBuildings.Random(world.LocalRandom);
						bot.QueueOrder(new Order("Move", transport, Target.FromCell(world, home.Location), false));
						continue;
					}

					CallAboard(bot, transport, cargo);
					continue;
				}

				// Partly loaded: wait for the rest unless it has waited long enough or it is full
				if (!loadingSince.TryGetValue(transport, out var since))
					loadingSince[transport] = since = world.WorldTick;

				var full = !cargo.HasSpace(1);
				if (!full && world.WorldTick - since < Info.LoadTimeout)
				{
					CallAboard(bot, transport, cargo);
					continue;
				}

				targets ??= PxBotUtils.VisibleEnemyBuildings(world, player);
				if (targets.Count == 0)
					continue;

				var best = PxBotUtils.LeastDefended(world, player, targets, Info.TargetOptions, Info.AntiAirScanRadius,
					Info.AircraftTargetType, out var antiAir);

				if (best == null || antiAir > Info.MaximumAntiAir)
					continue;

				var cell = PxBotUtils.ScatterCell(world, best, Info.LandingScatter);
				AIUtils.BotDebug($"{player.ResolvedPlayerName} flies {transport.Info.Name} with {cargo.PassengerCount} aboard to {best.Info.Name} at {cell}.");
				loadingSince.Remove(transport);
				var assault = transport.TraitOrDefault<PxAirAssault>();
				if (assault != null && assault.CanRope && world.LocalRandom.Next(100) < Info.FastRopeChance)
				{
					bot.QueueOrder(new Order(assault.Info.OrderName, transport, Target.FromCell(world, cell), false));
					continue;
				}

				bot.QueueOrder(new Order("Move", transport, Target.FromCell(world, cell), false));
				bot.QueueOrder(new Order("Unload", transport, true));
			}
		}

		void CallAboard(IBot bot, Actor transport, Cargo cargo)
		{
			var passengers = world.FindActorsInCircle(transport.CenterPosition, Info.PickupRadius)
				.Where(a => a.Owner == player && !a.IsDead && a.IsInWorld && a.IsIdle && Info.PassengerTypes.Contains(a.Info.Name))
				.ToList();

			var aboard = 0;
			foreach (var p in passengers)
			{
				var passenger = p.TraitOrDefault<Passenger>();
				if (passenger == null || !cargo.Info.Types.Contains(passenger.Info.CargoType) || !cargo.HasSpace(aboard + passenger.Info.Weight))
					continue;

				aboard += passenger.Info.Weight;
				bot.QueueOrder(new Order("EnterTransport", p, Target.FromActor(transport), false));
			}
		}
	}
}
