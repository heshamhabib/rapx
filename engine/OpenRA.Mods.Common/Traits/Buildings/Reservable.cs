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
using OpenRA.Mods.Common.Activities;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.Common.Traits
{
	[Desc("Reserve landing places for aircraft.")]
	public sealed class ReservableInfo : TraitInfo
	{
		// RAPX (IDEA-06): several parking slots per building. Each slot is the home of one aircraft, which keeps it
		// while flying and lands back on it. Empty = one landing place at the exit, as in stock OpenRA.
		[Desc("Landing position of each parking slot, relative to the building centre. Each slot must be in its own cell.")]
		public readonly WVec[] SlotOffsets = Array.Empty<WVec>();

		[Desc("Facing of the parked aircraft, one per slot (optional).")]
		public readonly WAngle[] SlotFacings = Array.Empty<WAngle>();

		public bool HasSlots => SlotOffsets.Length > 0;

		public override object Create(ActorInitializer init) { return new Reservable(this); }
	}

	public class Reservable : ITick, INotifyOwnerChanged, INotifySold, INotifyActorDisposing, INotifyCreated
	{
		sealed class Slot
		{
			public Actor ReservedFor;
			public Aircraft ReservedForAircraft;

			// RAPX: the aircraft that owns this slot, also while it is away.
			public Actor Home;
		}

		public readonly ReservableInfo Info;
		readonly Slot[] slots;
		RallyPoint rallyPoint;

		public Reservable(ReservableInfo info)
		{
			Info = info;
			slots = new Slot[Math.Max(1, info.SlotOffsets.Length)];
			for (var i = 0; i < slots.Length; i++)
				slots[i] = new Slot();
		}

		void INotifyCreated.Created(Actor self)
		{
			rallyPoint = self.TraitOrDefault<RallyPoint>();
		}

		void ITick.Tick(Actor self)
		{
			foreach (var s in slots)
			{
				if (s.ReservedFor != null && !Target.FromActor(s.ReservedFor).IsValidFor(self))
				{
					// Not likely to arrive now.
					s.ReservedForAircraft.UnReserve();
					s.ReservedFor = null;
					s.ReservedForAircraft = null;
				}

				if (s.Home != null && (s.Home.IsDead || !s.Home.IsInWorld || s.Home.Owner != self.Owner))
					s.Home = null;
			}
		}

		bool IsFree(Slot s)
		{
			return (s.ReservedForAircraft == null || s.ReservedForAircraft.MayYieldReservation) && s.Home == null;
		}

		int SlotOf(Actor forActor)
		{
			for (var i = 0; i < slots.Length; i++)
				if (slots[i].ReservedFor == forActor || slots[i].Home == forActor)
					return i;

			return -1;
		}

		public IDisposable Reserve(Actor self, Actor forActor, Aircraft forAircraft)
		{
			var index = Info.HasSlots ? SlotOf(forActor) : 0;
			if (index < 0)
				index = Array.FindIndex(slots, IsFree);

			// No free slot (callers check IsAvailableFor first): nothing to reserve.
			if (index < 0)
				return new DisposableAction(() => { }, () => { });

			var slot = slots[index];
			if (slot.ReservedFor != forActor && slot.ReservedForAircraft != null && slot.ReservedForAircraft.MayYieldReservation)
				UnReserve(self, slot);

			slot.ReservedFor = forActor;
			slot.ReservedForAircraft = forAircraft;

			// RAPX: helicopters may set down on an airfield, but a parking slot is never their home (it would use up a
			// jet's slot for good).
			if (Info.HasSlots && forAircraft?.Info.CanHover != true)
			{
				slot.Home = forActor;
				ClearHomeElsewhere(self, forActor);
			}

			// NOTE: we really don't care about the GC eating DisposableActions that apply to a world *other* than
			// the one we're playing in.
			return new DisposableAction(
				() =>
				{
					if (slot.ReservedFor == forActor)
					{
						slot.ReservedFor = null;
						slot.ReservedForAircraft = null;
					}
				},
				() => Game.RunAfterTick(() =>
				{
					if (Game.IsCurrentWorld(self.World))
						throw new InvalidOperationException(
							$"Attempted to finalize an undisposed DisposableAction. {forActor.Info.Name} ({forActor.ActorID}) reserved {self.Info.Name} ({self.ActorID})");
				}));
		}

		static void ClearHomeElsewhere(Actor self, Actor forActor)
		{
			foreach (var other in self.World.ActorsWithTrait<Reservable>())
				if (other.Actor != self)
					foreach (var s in other.Trait.slots)
						if (s.Home == forActor && s.ReservedFor != forActor)
							s.Home = null;
		}

		/// <summary>RAPX: landing offset and facing of the slot held by this aircraft, if the building has slots.</summary>
		public bool TryGetSlot(Actor forActor, out WVec offset, out WAngle? facing)
		{
			offset = WVec.Zero;
			facing = null;
			if (!Info.HasSlots)
				return false;

			var index = SlotOf(forActor);
			if (index < 0)
				return false;

			offset = Info.SlotOffsets[index];
			if (index < Info.SlotFacings.Length)
				facing = Info.SlotFacings[index];

			return true;
		}

		/// <summary>RAPX: the building whose slot is this aircraft's home, or null.</summary>
		public static Actor HomeOf(Actor aircraft)
		{
			foreach (var r in aircraft.World.ActorsWithTrait<Reservable>())
				if (!r.Actor.IsDead && Array.Exists(r.Trait.slots, s => s.Home == aircraft))
					return r.Actor;

			return null;
		}

		/// <summary>RAPX: number of free slots and total slots (for slot counters and production limits).</summary>
		public (int Free, int Total) SlotUsage()
		{
			return (Array.FindAll(slots, IsFree).Length, slots.Length);
		}

		public static bool IsReserved(Actor a)
		{
			var res = a.TraitOrDefault<Reservable>();
			return res != null && !Array.Exists(res.slots, res.IsFree);
		}

		public static bool IsAvailableFor(Actor reservable, Actor forActor)
		{
			var res = reservable.TraitOrDefault<Reservable>();
			return res == null || res.SlotOf(forActor) >= 0 || Array.Exists(res.slots, res.IsFree);
		}

		void UnReserve(Actor self, Slot slot)
		{
			var reservedFor = slot.ReservedFor;
			var reservedForAircraft = slot.ReservedForAircraft;
			slot.Home = null;
			if (reservedForAircraft == null)
				return;

			if (reservedForAircraft.GetActorBelow() == self)
			{
				// HACK: Cache this in a local var, such that the inner activity of AttackMoveActivity can access the trait easily after reservedForAircraft was nulled
				var aircraft = reservedForAircraft;
				if (rallyPoint != null && rallyPoint.Path.Count > 0)
					foreach (var cell in rallyPoint.Path)
						reservedFor.QueueActivity(new AttackMoveActivity(reservedFor, () => aircraft.MoveTo(cell, 1, targetLineColor: Color.OrangeRed)));
				else
					reservedFor.QueueActivity(new TakeOff(reservedFor));
			}

			reservedForAircraft.UnReserve();
		}

		void UnReserveAll(Actor self)
		{
			foreach (var s in slots)
				UnReserve(self, s);
		}

		void INotifyActorDisposing.Disposing(Actor self) { UnReserveAll(self); }

		void INotifyOwnerChanged.OnOwnerChanged(Actor self, Player oldOwner, Player newOwner) { UnReserveAll(self); }

		void INotifySold.Selling(Actor self) { UnReserveAll(self); }
		void INotifySold.Sold(Actor self) { UnReserveAll(self); }
	}
}
