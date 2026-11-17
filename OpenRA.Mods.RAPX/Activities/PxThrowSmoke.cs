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
using OpenRA.Activities;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Activities
{
	/// <summary>
	/// IDEA-46 Red Smoke: a soldier walks into throwing range, turns to the target and throws the smoke grenade
	/// (fires the given armament once: the throw animation, the tumbling canister and its trail come from the weapon).
	/// </summary>
	public class PxThrowSmoke : Activity
	{
		static readonly Color LineColor = Color.FromArgb(238, 52, 38);

		readonly Target target;
		readonly Armament armament;
		readonly IMove move;
		readonly IFacing facing;
		int waited;

		public PxThrowSmoke(Actor self, in Target target, Armament armament)
		{
			this.target = target;
			this.armament = armament;
			move = self.TraitOrDefault<IMove>();
			facing = self.TraitOrDefault<IFacing>();
		}

		protected override void OnFirstRun(Actor self)
		{
			var range = armament.MaxRange();
			if (move != null && !target.IsInRange(self.CenterPosition, range))
				QueueChild(move.MoveWithinRange(target, new WDist(range.Length * 9 / 10), targetLineColor: LineColor));
		}

		public override bool Tick(Actor self)
		{
			if (IsCanceling || !target.IsInRange(self.CenterPosition, armament.MaxRange()))
				return true;

			var desired = (target.CenterPosition - self.CenterPosition).Yaw;
			if (facing != null && facing.Facing != desired)
			{
				QueueChild(new Turn(self, desired));
				return false;
			}

			// Still reloading from an earlier throw: wait a moment, then give up
			return armament.CheckFire(self, facing, target) || ++waited > 100;
		}

		public override IEnumerable<TargetLineNode> TargetLineNodes(Actor self)
		{
			yield return new TargetLineNode(target, LineColor);
		}
	}
}
