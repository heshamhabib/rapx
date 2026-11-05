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
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.Player)]
	[Desc("Classic production queue that limits planes to the parking slots of the player's airfields (IDEA-06).",
		"A plane uses slots when one of its Rearmable.RearmActors has Reservable.SlotOffsets.",
		"Carrier decks (PxCarrierDeck) add their slots.",
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

		int countedTick = -1;
		int totalSlots;
		int ownedPlanes;

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

			var rearmable = actor.TraitInfoOrDefault<RearmableInfo>();
			uses = actor.HasTraitInfo<AircraftInfo>() && rearmable != null && rearmable.RearmActors.Overlaps(slotAirfields);
			usesSlots[actor] = uses;
			return uses;
		}

		/// <summary>Slots of the player's airfields that are not taken by a plane or by a plane in production.</summary>
		public int FreeSlots()
		{
			if (countedTick != self.World.WorldTick)
			{
				countedTick = self.World.WorldTick;
				totalSlots = 0;
				foreach (var r in self.World.ActorsWithTrait<Reservable>())
					if (r.Actor.Owner == self.Owner && !r.Actor.IsDead && r.Trait.Info.HasSlots)
						totalSlots += r.Trait.SlotUsage().Total;

				// Carrier decks (IDEA-08) add their slots too.
				foreach (var d in self.World.ActorsWithTrait<PxCarrierDeck>())
					if (d.Actor.Owner == self.Owner && !d.Actor.IsDead)
						totalSlots += d.Trait.Info.Slots;

				ownedPlanes = 0;
				foreach (var a in self.World.ActorsHavingTrait<Aircraft>())
					if (a.Owner == self.Owner && !a.IsDead && UsesSlots(a.Info))
						ownedPlanes++;
			}

			var rules = self.World.Map.Rules;
			return totalSlots - ownedPlanes - Queue.Count(i => UsesSlots(rules.Actors[i.Item]));
		}

		public override IEnumerable<ActorInfo> BuildableItems()
		{
			var items = base.BuildableItems();
			if (ignoreSlots || FreeSlots() > 0)
				return items;

			return items.Where(a => !UsesSlots(a));
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

		protected override void BeginProduction(ProductionItem item, bool hasPriority)
		{
			// One order can queue several planes (shift-click): stop at the last free slot.
			if (UsesSlots(self.World.Map.Rules.Actors[item.Item]) && FreeSlots() <= 0)
				return;

			base.BeginProduction(item, hasPriority);
		}
	}
}
