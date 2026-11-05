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
using System.Linq;
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Shoot and scoot (IDEA-17 HIMAX): a moment after firing, the actor drives to a free cell a few cells away,",
		"preferring the side away from its target, so return fire lands where it was. It then attacks the same target",
		"again (if it is still valid); idle units pick targets as usual.")]
	public class PxShootAndScootInfo : ConditionalTraitInfo, Requires<MobileInfo>, Requires<AttackBaseInfo>
	{
		[Desc("Ticks after firing before it starts moving (lets the rocket clear the launcher).")]
		public readonly int Delay = 8;

		[Desc("Nearest distance, in cells, of the new position.")]
		public readonly int MinDistance = 3;

		[Desc("Farthest distance, in cells, of the new position.")]
		public readonly int MaxDistance = 5;

		public override object Create(ActorInitializer init) { return new PxShootAndScoot(init.Self, this); }
	}

	public class PxShootAndScoot : ConditionalTrait<PxShootAndScootInfo>, INotifyAttack, ITick
	{
		readonly Mobile mobile;
		AttackBase[] attacks;
		int countdown = -1;
		Target lastTarget = Target.Invalid;

		public PxShootAndScoot(Actor self, PxShootAndScootInfo info)
			: base(info)
		{
			mobile = self.Trait<Mobile>();
		}

		protected override void Created(Actor self)
		{
			attacks = self.TraitsImplementing<AttackBase>().ToArray();
			base.Created(self);
		}

		void INotifyAttack.PreparingAttack(Actor self, in Target target, Armament a, Barrel barrel) { }

		void INotifyAttack.Attacking(Actor self, in Target target, Armament a, Barrel barrel)
		{
			if (IsTraitDisabled)
				return;

			lastTarget = target;
			countdown = Info.Delay;
		}

		void ITick.Tick(Actor self)
		{
			if (countdown < 0 || --countdown > 0)
				return;

			countdown = -1;
			if (IsTraitDisabled)
				return;

			var cell = PickCell(self);
			if (cell == null)
				return;

			self.QueueActivity(false, mobile.MoveTo(cell.Value, 0));
			if (lastTarget.IsValidFor(self))
				foreach (var attack in attacks)
					if (!attack.IsTraitDisabled)
					{
						attack.AttackTarget(lastTarget, AttackSource.Default, true, false);
						break;
					}
		}

		CPos? PickCell(Actor self)
		{
			var map = self.World.Map;
			var random = self.World.SharedRandom;
			var from = self.Location;

			// Away from the target: the vector from the target to us (any direction if there is no target)
			var away = lastTarget.Type != TargetType.Invalid ? self.CenterPosition - lastTarget.CenterPosition : WVec.Zero;
			var awayLength = Math.Max(1, away.HorizontalLength);

			CPos? best = null;
			var bestScore = int.MinValue;
			for (var i = 0; i < 16; i++)
			{
				var angle = random.Next(1024);
				var distance = random.Next(Info.MinDistance, Info.MaxDistance + 1);
				var offset = new WVec(0, -1024 * distance, 0).Rotate(WRot.FromYaw(new WAngle(angle)));
				var cell = map.CellContaining(self.CenterPosition + offset);
				if (cell == from || !map.Contains(cell) || !mobile.CanEnterCell(cell))
					continue;

				// Score: how much it points away from the target (-1024..1024), plus some randomness
				var score = (offset.X * away.X + offset.Y * away.Y) / (1024 * distance) * 1024 / awayLength + random.Next(512);
				if (score > bestScore)
				{
					bestScore = score;
					best = cell;
				}
			}

			return best;
		}
	}
}
