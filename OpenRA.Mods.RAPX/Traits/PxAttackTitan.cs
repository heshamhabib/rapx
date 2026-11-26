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
	[Desc("AttackFrontal for actors whose weapons cover separate distance bands (titans: a long-range breath or boulder",
		"with a minimum range, plus a melee blow). The stock Attack activity moves into the range that suits ALL usable",
		"weapons at once (largest minimum, smallest maximum), which is empty for such bands, so the actor never fires.",
		"This picks only the weapons that can hit from where the actor stands; if none can, the ones it should close",
		"in for (the longest reach when the target is too far, the short ones when it is too close).")]
	public class PxAttackTitanInfo : AttackFrontalInfo
	{
		public override object Create(ActorInitializer init) { return new PxAttackTitan(init.Self, this); }
	}

	public class PxAttackTitan : AttackFrontal
	{
		readonly Actor self;

		public PxAttackTitan(Actor self, PxAttackTitanInfo info)
			: base(self, info)
		{
			this.self = self;
		}

		public override IEnumerable<Armament> ChooseArmamentsForTarget(Target t, bool forceAttack)
		{
			var usable = base.ChooseArmamentsForTarget(t, forceAttack).ToList();
			if (usable.Count < 2 || t.Type == TargetType.Invalid)
				return usable;

			var pos = self.CenterPosition;
			var fromHere = usable.Where(a => t.IsInRange(pos, a.MaxRange())
				&& (a.Weapon.MinRange == WDist.Zero || !t.IsInRange(pos, a.Weapon.MinRange))).ToList();
			if (fromHere.Count > 0)
				return fromHere;

			// Too close for every long weapon: step in for the melee ones (no minimum range)
			var tooClose = usable.Where(a => a.Weapon.MinRange != WDist.Zero && t.IsInRange(pos, a.Weapon.MinRange)).ToList();
			if (tooClose.Count == usable.Count(a => a.Weapon.MinRange != WDist.Zero) && tooClose.Count > 0)
			{
				var melee = usable.Where(a => a.Weapon.MinRange == WDist.Zero).ToList();
				if (melee.Count > 0)
					return melee;
			}

			// Too far: walk only as far as the longest reach needs
			var reach = usable.Max(a => a.MaxRange());
			return usable.Where(a => a.MaxRange() == reach);
		}
	}

	[Desc("Armament whose shots leave from a fixed point on an HD-rendered body (Godzilla's mouth), placed where the",
		"sprite of the current facing shows it. The point is given as it is in the 3D render (forward, right, up from the",
		"ground under the actor); the renders' camera (50 degrees) draws ground depth at ViewSquash and height at",
		"HeightScale, so a plain LocalOffset (drawn 1:1 by the engine) only lines up at some facings.")]
	public class PxTitanArmamentInfo : ArmamentInfo
	{
		[Desc("Muzzle point in the render, in WDist: forward, right, up.")]
		public readonly WVec Muzzle = WVec.Zero;

		[Desc("Facings of the body sprite (the muzzle follows the facing the sprite shows).")]
		public readonly int Facings = 16;

		[Desc("Per mille: how the render camera draws ground depth (sin 50 = 766) and height (cos 50 = 643).")]
		public readonly int ViewSquash = 766;

		public readonly int HeightScale = 643;

		public override object Create(ActorInitializer init) { return new PxTitanArmament(init.Self, this); }
	}

	public class PxTitanArmament : Armament
	{
		readonly PxTitanArmamentInfo info;

		public PxTitanArmament(Actor self, PxTitanArmamentInfo info)
			: base(self, info)
		{
			this.info = info;
		}

		protected override WVec CalculateMuzzleOffset(Actor self, Barrel b)
		{
			// The facing the sprite shows
			var step = 1024 / info.Facings;
			var yaw = new WAngle((self.Orientation.Yaw.Angle + step / 2) / step * step);

			// Forward is north (-Y) at yaw 0; right is east (+X)
			var ground = new WVec(info.Muzzle.Y, -info.Muzzle.X, 0).Rotate(WRot.FromYaw(yaw));
			return new WVec(ground.X, ground.Y * info.ViewSquash / 1000, info.Muzzle.Z * info.HeightScale / 1000);
		}
	}

	[Desc("Plays a sound when the named armament starts an attack (its FireDelay still to come), e.g. a charge-up.")]
	public class PxAttackPrepareSoundInfo : TraitInfo
	{
		[Desc("Armament name.")]
		public readonly string Armament = "primary";

		[FieldLoader.Require]
		public readonly string[] Sounds = null;

		public override object Create(ActorInitializer init) { return new PxAttackPrepareSound(this); }
	}

	public class PxAttackPrepareSound : INotifyAttack
	{
		readonly PxAttackPrepareSoundInfo info;

		public PxAttackPrepareSound(PxAttackPrepareSoundInfo info)
		{
			this.info = info;
		}

		void INotifyAttack.PreparingAttack(Actor self, in Target target, Armament a, Barrel barrel)
		{
			if (a.Info.Name == info.Armament)
				Game.Sound.Play(SoundType.World, info.Sounds.Random(Game.CosmeticRandom), self.CenterPosition);
		}

		void INotifyAttack.Attacking(Actor self, in Target target, Armament a, Barrel barrel) { }
	}
}
