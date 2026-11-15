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
	[Desc("Tramples (Elephanta walker): while the actor moves, everything crushable under its feet within Radius is",
		"crushed at once. Unlike the engine's crushing (the cell it enters, with a warning that lets infantry dodge),",
		"nothing gets away. Crushable's own rules still apply (no friendlies, nothing during the peace treaty).")]
	public class PxTrampleInfo : ConditionalTraitInfo, Requires<MobileInfo>
	{
		[Desc("Crush classes it tramples.")]
		public readonly BitSet<CrushClass> CrushClasses = new("infantry");

		[Desc("Distance from the actor's centre that its feet cover.")]
		public readonly WDist Radius = new(640);

		[Desc("Checks every this many ticks while moving.")]
		public readonly int Interval = 3;

		public override object Create(ActorInitializer init) { return new PxTrample(this); }
	}

	public class PxTrample : ConditionalTrait<PxTrampleInfo>, ITick
	{
		WPos lastPosition;
		int countdown;

		public PxTrample(PxTrampleInfo info)
			: base(info) { }

		void ITick.Tick(Actor self)
		{
			if (IsTraitDisabled || --countdown > 0)
				return;

			countdown = Info.Interval;
			var position = self.CenterPosition;
			var moved = position != lastPosition;
			lastPosition = position;
			if (!moved)
				return;

			var victims = self.World.FindActorsInCircle(position, Info.Radius)
				.Where(a => a != self && !a.IsDead && a.IsAtGroundLevel()
					&& a.Crushables.Any(c => c.CrushableBy(a, self, Info.CrushClasses)))
				.ToList();

			foreach (var victim in victims)
				foreach (var notify in victim.TraitsImplementing<INotifyCrushed>())
					if (!victim.IsDead)
						notify.OnCrush(victim, self, Info.CrushClasses);
		}
	}
}
