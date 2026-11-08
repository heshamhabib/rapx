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

using OpenRA.Activities;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Activities;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("A jet that flies attack orders in V formation with the other jets given the same order (see PxStrikeFormations",
		"on the World actor). Swaps the AttackAircraft's own attack activity for PxFormationStrike; a jet ordered on its",
		"own attacks exactly as before.")]
	public class PxStrikeFormationInfo : TraitInfo, Requires<AircraftInfo>, NotBefore<AttackBaseInfo>
	{
		public override object Create(ActorInitializer init) { return new PxStrikeFormation(); }
	}

	public class PxStrikeFormation : IResolveOrder
	{
		/// <summary>Where this jet's formation place was last tick (its slot velocity), or null when not following.</summary>
		public WPos? LastSlot { get; set; }

		/// <summary>Last horizontal step while following its place.</summary>
		public WVec LastMove { get; set; }

		void IResolveOrder.ResolveOrder(Actor self, Order order)
		{
			var forceAttack = order.OrderString == "ForceAttack";
			if (!forceAttack && order.OrderString != "Attack")
				return;

			var attack = self.TraitOrDefault<AttackAircraft>();
			if (attack == null || attack.IsTraitDisabled)
				return;

			// AttackAircraft resolved this order just before us (NotBefore) and queued its FlyAttack last.
			var last = self.CurrentActivity;
			while (last?.NextActivity != null)
				last = last.NextActivity;

			if (last is not FlyAttack queued || queued.State != ActivityState.Queued)
				return;

			queued.Cancel(self, true);
			var group = self.World.WorldActor.Trait<PxStrikeFormations>().Join(self, order.Target, order.Queued);
			self.QueueActivity(new PxFormationStrike(self, order.Target, forceAttack, attack.Info.TargetLineColor, group));
		}
	}
}
