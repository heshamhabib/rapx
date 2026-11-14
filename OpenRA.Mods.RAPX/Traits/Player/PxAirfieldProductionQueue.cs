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
	[Desc("Classic production queue that limits planes to the parking slots of the player's airfields (IDEA-06).",
		"A plane uses slots when one of its Rearmable.RearmActors has Reservable.SlotOffsets.",
		"Helicopters (Aircraft.CanHover) never use slots.",
		"Carrier decks (PxCarrierDeck) add their slots.",
		"The Fatman bomber field (PxFatmanStrikePower) and its bomber (PxStrategicBomber) stay out of the pool.",
		"Airborne Bases (PxAirliftBase) have a pool of their own for the airlift transports (PxAirlift).",
		"Planes owned + planes queued can't exceed the total slots: the buttons grey out and extra orders are dropped.")]
	public class PxAirfieldProductionQueueInfo : ClassicProductionQueueInfo
	{
		public override object Create(ActorInitializer init) { return new PxAirfieldProductionQueue(init, this); }
	}

	public class PxAirfieldProductionQueue : ClassicProductionQueue
	{
		readonly Actor self;
		readonly Dictionary<ActorInfo, bool> usesSlots = new();
		HashSet<string> slotAirfields;

		// Index 0: the jets' pool, 1: the airlift transports' pool (Airborne Bases)
		readonly int[] totalSlots = new int[2];
		readonly int[] ownedPlanes = new int[2];
		int countedTick = -1;

		// Set while the base queue cancels unbuildable items, so planes already queued are not cancelled at the limit.
		bool ignoreSlots;

		public PxAirfieldProductionQueue(ActorInitializer init, PxAirfieldProductionQueueInfo info)
			: base(init, info)
		{
			self = init.Self;
		}

		bool UsesSlots(ActorInfo actor)
		{
			if (usesSlots.TryGetValue(actor, out var uses))
				return uses;

			slotAirfields ??= self.World.Map.Rules.Actors.Values
				.Where(a => a.TraitInfoOrDefault<ReservableInfo>()?.HasSlots == true)
				.Select(a => a.Name)
				.ToHashSet();

			// Helicopters land on helipads or open ground, never on an airfield slot.
			var aircraft = actor.TraitInfoOrDefault<AircraftInfo>();
			var rearmable = actor.TraitInfoOrDefault<RearmableInfo>();

			// The Fatman bomber (PxStrategicBomber) has its own one-slot field and BuildLimit, outside the pool
			uses = aircraft != null && !aircraft.CanHover && rearmable != null && rearmable.RearmActors.Overlaps(slotAirfields)
				&& !actor.HasTraitInfo<PxStrategicBomberInfo>();
			usesSlots[actor] = uses;
			return uses;
		}

		static int Pool(ActorInfo actor) { return actor.HasTraitInfo<PxAirliftInfo>() ? 1 : 0; }

		/// <summary>Slots of the player's airfields that are not taken by a plane or by a plane in production.</summary>
		public int FreeSlots() { return FreeSlots(0); }

		/// <summary>Free slots of one pool: 0 = jets (airfields, carrier decks), 1 = airlift transports (Airborne Bases).</summary>
		public int FreeSlots(int pool)
		{
			if (countedTick != self.World.WorldTick)
			{
				countedTick = self.World.WorldTick;
				totalSlots[0] = totalSlots[1] = 0;
				foreach (var r in self.World.ActorsWithTrait<Reservable>())
					if (r.Actor.Owner == self.Owner && !r.Actor.IsDead && r.Trait.Info.HasSlots
						&& !r.Actor.Info.HasTraitInfo<PxFatmanStrikePowerInfo>())
						totalSlots[r.Actor.Info.HasTraitInfo<PxAirliftBaseInfo>() ? 1 : 0] += r.Trait.SlotUsage().Total;

				// Carrier decks (IDEA-08) add their slots too.
				foreach (var d in self.World.ActorsWithTrait<PxCarrierDeck>())
					if (d.Actor.Owner == self.Owner && !d.Actor.IsDead)
						totalSlots[0] += d.Trait.Info.Slots;

				ownedPlanes[0] = ownedPlanes[1] = 0;
				foreach (var a in self.World.ActorsHavingTrait<Aircraft>())
					if (a.Owner == self.Owner && !a.IsDead && UsesSlots(a.Info))
						ownedPlanes[Pool(a.Info)]++;
			}

			var rules = self.World.Map.Rules;
			return totalSlots[pool] - ownedPlanes[pool] - Queue.Count(i => UsesSlots(rules.Actors[i.Item]) && Pool(rules.Actors[i.Item]) == pool);
		}

		/// <summary>Whether the player owns a working building that produces this unit's BuildAtProductionType.</summary>
		bool HasProducer(ActorInfo unit)
		{
			var type = unit.TraitInfoOrDefault<BuildableInfo>()?.BuildAtProductionType;
			return type == null || self.World.ActorsWithTrait<Production>()
				.Any(x => x.Actor.Owner == self.Owner && !x.Actor.IsDead && !x.Trait.IsTraitDisabled && x.Trait.Info.Produces.Contains(type));
		}

		public override IEnumerable<ActorInfo> BuildableItems()
		{
			var items = base.BuildableItems();
			if (ignoreSlots)
				return items;

			// Helicopters need a helipad even with the AllTech cheat (which ignores BuildAtProductionType): without
			// one the engine built them at the airfield, where they took a jet's parking slot as their home.
			return items.Where(a => (!UsesSlots(a) || FreeSlots(Pool(a)) > 0) && (!developerMode.AllTech || HasProducer(a)));
		}

		protected override void TickInner(Actor self, bool allProductionPaused)
		{
			ignoreSlots = true;
			try
			{
				base.TickInner(self, allProductionPaused);
			}
			finally
			{
				ignoreSlots = false;
			}
		}

		protected override bool BuildUnit(ActorInfo unit)
		{
			// The AllTech cheat makes the base queue ignore BuildAtProductionType, so helicopters came out of the
			// airfield and parked on a plane's slot. Keep them on the helipad whenever the player has one.
			var type = unit.TraitInfo<BuildableInfo>().BuildAtProductionType;
			if (!developerMode.AllTech || type == null)
				return base.BuildUnit(unit);

			var producers = self.World.ActorsWithTrait<Production>()
				.Where(x => x.Actor.Owner == self.Owner && !x.Trait.IsTraitDisabled && x.Trait.Info.Produces.Contains(type))
				.OrderByDescending(x => x.Actor.TraitOrDefault<PrimaryBuilding>()?.IsPrimary == true)
				.ThenByDescending(x => x.Actor.ActorID)
				.ToList();

			// No building of this type (e.g. the helipad was lost after the order): wait for one instead of letting
			// the engine fall back to the airfield, where a helicopter would take a jet's slot.
			if (producers.Count == 0)
				return false;

			foreach (var p in producers)
			{
				if (p.Trait.IsTraitPaused)
					continue;

				var inits = new TypeDictionary
				{
					new OwnerInit(self.Owner),
					new FactionInit(BuildableInfo.GetInitialFaction(unit, p.Trait.Faction))
				};

				var item = Queue.First(i => i.Done && i.Item == unit.Name);
				if (p.Trait.Produce(p.Actor, unit, type, inits, item.TotalCost))
				{
					EndProduction(item);
					return true;
				}
			}

			return false;
		}

		protected override void BeginProduction(ProductionItem item, bool hasPriority)
		{
			// One order can queue several planes (shift-click): stop at the last free slot.
			var actor = self.World.Map.Rules.Actors[item.Item];
			if (UsesSlots(actor) && FreeSlots(Pool(actor)) <= 0)
				return;

			base.BeginProduction(item, hasPriority);
		}
	}
}
