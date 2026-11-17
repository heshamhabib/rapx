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
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Activities;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Red Smoke support power (IDEA-46), carried by every combat soldier: one shared charge for the player. On use the",
		"soldier nearest to the target walks into throwing range and throws a smoke grenade (its Armament named",
		"Armament), which lands as a PxSmokeMarker that calls the player's long-range support onto it.")]
	public class PxSmokeMarkerPowerInfo : SupportPowerInfo
	{
		[Desc("Name of the thrower's Armament that throws the smoke grenade (kept out of AttackBase.Armaments).")]
		public readonly string Armament = "smoke";

		public override object Create(ActorInitializer init) { return new PxSmokeMarkerPower(init.Self, this); }
	}

	public class PxSmokeMarkerPower : SupportPower
	{
		readonly PxSmokeMarkerPowerInfo info;

		public PxSmokeMarkerPower(Actor self, PxSmokeMarkerPowerInfo info)
			: base(self, info)
		{
			this.info = info;
		}

		public override void Activate(Actor self, Order order, SupportPowerManager manager)
		{
			base.Activate(self, order, manager);

			// The engine picks the nearest instance, but that soldier may be riding in a transport or garrisoned: choose
			// the nearest one that is actually standing on the battlefield
			var target = Target.FromPos(order.Target.CenterPosition);
			var thrower = self.World.ActorsWithTrait<PxSmokeMarkerPower>()
				.Where(p => p.Actor.Owner == self.Owner && p.Actor.IsInWorld && !p.Actor.IsDead &&
					!p.Trait.IsTraitDisabled && !p.Trait.IsTraitPaused && p.Trait.Info.OrderName == Info.OrderName)
				.Select(p => p.Actor)
				.MinByOrDefault(a => (a.CenterPosition - target.CenterPosition).HorizontalLengthSquared);

			var armament = thrower?.TraitsImplementing<Armament>().FirstOrDefault(a => a.Info.Name == info.Armament && !a.IsTraitDisabled);
			if (armament == null)
				return;

			PlayLaunchSounds();
			thrower.QueueActivity(false, new PxThrowSmoke(thrower, target, armament));
			thrower.ShowTargetLines();
		}
	}
}
