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
using OpenRA.Effects;
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Warheads;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Warheads
{
	[Desc("Leaves the ground burning where it lands (incendiary submunitions, white phosphorus): Weapon goes off at the",
		"impact point every Interval ticks for Duration ticks, e.g. a small fire that damages whatever stands in it and",
		"keeps the flames and smoke going. Owned by the firing player even after the firer is gone.")]
	public class PxBurnWarhead : Warhead, IRulesetLoaded<WeaponInfo>
	{
		[WeaponReference]
		[FieldLoader.Require]
		[Desc("Weapon fired at the impact point on every pulse (its projectile is ignored, only its warheads apply).")]
		public readonly string Weapon = null;

		[Desc("How long the ground burns, in ticks.")]
		public readonly int Duration = 250;

		[Desc("Ticks between two pulses.")]
		public readonly int Interval = 25;

		[Desc("Ticks before the first pulse.")]
		public readonly int FirstPulse = 10;

		WeaponInfo weapon;

		public void RulesetLoaded(Ruleset rules, WeaponInfo info)
		{
			if (!rules.Weapons.TryGetValue(Weapon.ToLowerInvariant(), out weapon))
				throw new YamlException($"Weapons Ruleset does not contain an entry '{Weapon.ToLowerInvariant()}'");
		}

		public override void DoImpact(in Target target, WarheadArgs args)
		{
			if (target.Type == TargetType.Invalid || args.SourceActor == null)
				return;

			var world = args.SourceActor.World;
			var pos = target.CenterPosition;
			pos = new WPos(pos.X, pos.Y, world.Map.CenterOfCell(world.Map.CellContaining(pos)).Z);
			var burn = new PxBurningGround(weapon, pos, new WarheadArgs(args), FirstPulse, Interval, Duration);
			world.AddFrameEndTask(w => w.Add(burn));
		}
	}

	/// <summary>A patch of burning ground: fires its weapon at one spot every few ticks (synced: effects tick with the
	/// world), then goes out.</summary>
	sealed class PxBurningGround : IEffect
	{
		readonly WeaponInfo weapon;
		readonly WPos pos;
		readonly WarheadArgs args;
		readonly int interval;
		int next;
		int left;

		public PxBurningGround(WeaponInfo weapon, WPos pos, WarheadArgs args, int delay, int interval, int duration)
		{
			this.weapon = weapon;
			this.pos = pos;
			this.args = args;
			this.interval = interval < 1 ? 1 : interval;
			next = delay;
			left = duration;
		}

		public void Tick(World world)
		{
			if (--left < 0)
			{
				world.AddFrameEndTask(w => w.Remove(this));
				return;
			}

			if (--next > 0)
				return;

			next = interval;
			weapon.Impact(Target.FromPos(pos), new WarheadArgs(args) { ImpactPosition = pos, Weapon = weapon });
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr) { yield break; }
	}
}
