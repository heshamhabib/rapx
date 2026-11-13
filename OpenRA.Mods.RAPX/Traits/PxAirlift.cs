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
using System.Collections.Generic;
using System.Linq;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Marks an airfield whose slots belong to the airlift transports (PxAirlift) only (IDEA-42 Airborne Base):",
		"PxAirfieldProductionQueue keeps them out of the jets' slot pool and gives them to the transports.")]
	public class PxAirliftBaseInfo : TraitInfo<PxAirliftBase> { }

	public class PxAirliftBase { }

	[Desc("Airborne transport (IDEA-42): carries its own paratrooper force, counted as the ammo of AmmoPool.",
		"Right-click the ground while it is loaded to drop them there: it flies to the spot, drops the whole stick in a line",
		"from the moment it gets within DropRange, then flies home to its pad, where the pool refills (Rearmable) and every",
		"trooper put back aboard is paid for at that soldier's price.")]
	public class PxAirliftInfo : TraitInfo, Requires<AmmoPoolInfo>, Requires<AircraftInfo>
	{
		[FieldLoader.Require]
		[Desc("The AmmoPool that counts the troopers aboard (its Ammo = the force size).")]
		public readonly string AmmoPool = null;

		[FieldLoader.Require]
		[ActorReference]
		[Desc("Soldier types and how many of each in a full load, e.g. E1: 30, E3: 10. They jump mixed together.")]
		public readonly Dictionary<string, int> Troops = new();

		[Desc("The drop starts when the plane is this close to the target.")]
		public readonly WDist DropRange = WDist.FromCells(3);

		[Desc("Ticks between two troopers jumping.")]
		public readonly int DropInterval = 2;

		[Desc("Sound played as each trooper jumps.")]
		public readonly string ChuteSound = null;

		[Desc("Pay for the troopers put back aboard on the pad (at each soldier's Valued cost).")]
		public readonly bool PayForReload = true;

		[Desc("Cursor for the drop order.")]
		public readonly string Cursor = "ability";

		[VoiceReference]
		public readonly string Voice = "Action";

		public override object Create(ActorInitializer init) { return new PxAirlift(init.Self, this); }
	}

	public class PxAirlift : IIssueOrder, IResolveOrder, IOrderVoice, ITick, INotifyCreated, ISync
	{
		const string OrderID = "PxAirdrop";

		readonly PxAirliftInfo info;
		readonly string[] stick;
		AmmoPool pool;
		PlayerResources resources;

		[Sync]
		CPos dropCell;

		[Sync]
		bool dropOrdered;

		[Sync]
		bool dropping;

		int delay;
		int lastAmmo;

		public PxAirlift(Actor self, PxAirliftInfo info)
		{
			this.info = info;

			// Mixed stick, e.g. 30 riflemen + 10 rocket soldiers: 3 riflemen, 1 rocket soldier, 3 riflemen...
			var counts = info.Troops.ToDictionary(kv => kv.Key.ToLowerInvariant(), kv => kv.Value);
			var total = counts.Values.Sum();
			var list = new List<string>();
			while (list.Count < total)
				foreach (var kv in info.Troops)
				{
					var name = kv.Key.ToLowerInvariant();
					var share = Math.Max(1, (int)Math.Round((double)kv.Value / info.Troops.Values.Min()));
					for (var i = 0; i < share && counts[name] > 0; i++)
					{
						list.Add(name);
						counts[name]--;
					}
				}

			stick = list.ToArray();
		}

		void INotifyCreated.Created(Actor self)
		{
			pool = self.TraitsImplementing<AmmoPool>().First(p => p.Info.Name == info.AmmoPool);
			resources = self.Owner.PlayerActor.Trait<PlayerResources>();
			lastAmmo = pool.CurrentAmmoCount;
		}

		/// <summary>Troopers aboard.</summary>
		public int Aboard => pool?.CurrentAmmoCount ?? 0;

		/// <summary>Troopers aboard a full load.</summary>
		public int Capacity => pool?.Info.Ammo ?? 0;

		/// <summary>True between a drop order and the end of the drop.</summary>
		public bool DropOrdered => dropOrdered;

		IEnumerable<IOrderTargeter> IIssueOrder.Orders
		{
			get { yield return new AirdropOrderTargeter(this); }
		}

		Order IIssueOrder.IssueOrder(Actor self, IOrderTargeter order, in Target target, bool queued)
		{
			return order.OrderID == OrderID ? new Order(OrderID, self, target, queued) : null;
		}

		string IOrderVoice.VoicePhraseForOrder(Actor self, Order order)
		{
			return order.OrderString == OrderID ? info.Voice : null;
		}

		void IResolveOrder.ResolveOrder(Actor self, Order order)
		{
			if (order.OrderString != OrderID || Aboard == 0)
				return;

			var cell = self.World.Map.CellContaining(order.Target.CenterPosition);
			if (!self.World.Map.Contains(cell))
				return;

			dropCell = cell;
			dropOrdered = true;
			dropping = false;

			var target = Target.FromCell(self.World, cell);
			self.QueueActivity(order.Queued, new Fly(self, target, targetLineColor: Color.LightGreen));
			self.QueueActivity(true, new ReturnToBase(self));
			self.ShowTargetLines();
		}

		void ITick.Tick(Actor self)
		{
			// Troopers put back aboard on the pad are paid for; without the money they stay off
			var ammo = pool.CurrentAmmoCount;
			if (ammo > lastAmmo && info.PayForReload)
			{
				for (var i = lastAmmo; i < ammo; i++)
				{
					var cost = self.World.Map.Rules.Actors[stick[i % stick.Length]].TraitInfoOrDefault<ValuedInfo>()?.Cost ?? 0;
					if (!resources.TakeCash(cost, true))
					{
						pool.TakeAmmo(self, ammo - i);
						ammo = i;
						break;
					}
				}
			}

			lastAmmo = ammo;

			if (!dropOrdered)
				return;

			if (ammo == 0 || !self.IsInWorld || self.World.Map.DistanceAboveTerrain(self.CenterPosition).Length < 256)
			{
				if (ammo == 0 || dropping)
					dropOrdered = dropping = false;

				return;
			}

			if (!dropping)
			{
				var lz = self.World.Map.CenterOfCell(dropCell);
				if ((lz - self.CenterPosition).HorizontalLengthSquared > (long)info.DropRange.Length * info.DropRange.Length)
					return;

				dropping = true;
				delay = 0;
			}

			if (delay-- > 0)
				return;

			// No free landing spot near the plane right now: try again next tick a little further on
			if (!Jump(self, stick[(stick.Length - ammo) % stick.Length], stick.Length - ammo))
				return;

			delay = info.DropInterval;
			pool.TakeAmmo(self, 1);
			lastAmmo = pool.CurrentAmmoCount;
		}

		bool Jump(Actor self, string soldier, int index)
		{
			var map = self.World.Map;
			var trooper = self.World.CreateActor(false, soldier, new TypeDictionary
			{
				new OwnerInit(self.Owner),
				new FactionInit(self.Owner.Faction.InternalName),
			});

			// Each jumper gets his own free spot he can stand on, alternating left and right of the flight path, so the
			// stick lands as a wide line: troopers landing on a full cell, a tree or water are killed (Parachutable)
			var positionable = trooper.Trait<IPositionable>();
			var facing = self.TraitOrDefault<IFacing>()?.Facing ?? WAngle.Zero;
			var right = new WVec(1024, 0, 0).Rotate(WRot.FromYaw(facing));
			var side = index % 2 == 0 ? 1 : -1;
			var cell = CPos.Zero;
			var subCell = SubCell.Invalid;
			foreach (var lateral in new[] { side, 0, -side, 2 * side, -2 * side })
			{
				var c = map.CellContaining(self.CenterPosition + right * lateral);
				if (!map.Contains(c) || !positionable.CanEnterCell(c, null, BlockedByActor.All))
					continue;

				subCell = positionable.GetAvailableSubCell(c);
				if (subCell != SubCell.Invalid)
				{
					cell = c;
					break;
				}
			}

			if (subCell == SubCell.Invalid)
			{
				trooper.Dispose();
				return false;
			}

			var altitude = self.CenterPosition.Z;
			self.World.AddFrameEndTask(w =>
			{
				positionable.SetPosition(trooper, cell, subCell);
				var at = trooper.CenterPosition + new WVec(0, 0, altitude - trooper.CenterPosition.Z);
				positionable.SetCenterPosition(trooper, at);
				w.Add(trooper);

				// Like a passenger leaving cargo (Passenger.cs): returning to its cell from up in the air opens the
				// parachute (Mobile.ReturnToCellActivity -> Parachute); without it the trooper just appears on the ground
				var move = trooper.TraitOrDefault<IMove>();
				if (move != null)
					trooper.QueueActivity(move.ReturnToCell(trooper));
			});

			if (info.ChuteSound != null)
				Game.Sound.Play(SoundType.World, info.ChuteSound, self.CenterPosition);

			return true;
		}

		sealed class AirdropOrderTargeter : IOrderTargeter
		{
			readonly PxAirlift airlift;

			public AirdropOrderTargeter(PxAirlift airlift) { this.airlift = airlift; }

			public string OrderID => PxAirlift.OrderID;
			public int OrderPriority => 6;
			public bool IsQueued { get; private set; }
			public bool TargetOverridesSelection(Actor self, in Target target, List<Actor> actorsAt, CPos xy, TargetModifiers modifiers) { return true; }

			public bool CanTarget(Actor self, in Target target, ref TargetModifiers modifiers, ref string cursor)
			{
				// Loaded: a click on open ground drops the troops there (Alt+click still just moves the plane)
				if (target.Type != TargetType.Terrain || airlift.Aboard == 0 || modifiers.HasModifier(TargetModifiers.ForceMove))
					return false;

				if (!self.World.Map.Contains(self.World.Map.CellContaining(target.CenterPosition)))
					return false;

				IsQueued = modifiers.HasModifier(TargetModifiers.ForceQueue);
				cursor = airlift.info.Cursor;
				return true;
			}
		}
	}
}
