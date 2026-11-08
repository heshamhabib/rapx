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
using OpenRA.GameRules;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Projectiles;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Close-in weapon system (CIWS, e.g. Phalanx, Kashtan, Type 1130; IDEA-08 carrier defence): gatling mounts that",
		"shoot down incoming hostile missiles (PxRocket projectiles) aimed at this actor or close to it. Each mount picks",
		"the nearest missile in Range, fires its tracer Weapon at it for AimTicks, then rolls Chance to destroy it (the",
		"missile bursts in the air and does no damage) and reloads. Mount positions follow PxCarrierDeck's deck",
		"coordinates when the actor has one (so they sit on the drawn hull at every heading).")]
	public class PxPointDefenseInfo : ConditionalTraitInfo
	{
		[Desc("Gun mounts (forward, right, up) relative to the actor's centre.")]
		public readonly WVec[] Mounts = { WVec.Zero };

		[Desc("Height of the guns above the actor.")]
		public readonly WDist MountHeight = new(192);

		[Desc("How far a mount can engage a missile.")]
		public readonly WDist Range = WDist.FromCells(3);

		[Desc("Only missiles that will hit within this distance of the actor are engaged (it guards itself and close escorts).")]
		public readonly WDist ProtectRadius = WDist.FromCells(3);

		[Desc("Ticks a mount fires at a missile before it is hit or missed.")]
		public readonly int AimTicks = 4;

		[Desc("Chance (percent) that a burst destroys the missile.")]
		public readonly int Chance = 75;

		[Desc("Ticks a mount needs after a burst before it can engage again.")]
		public readonly int ReloadDelay = 10;

		[Desc("Ticks between tracer bursts while a mount is engaging.")]
		public readonly int BurstInterval = 3;

		[WeaponReference]
		[FieldLoader.Require]
		[Desc("Cosmetic tracer weapon fired at the missile (no warheads needed).")]
		public readonly string Weapon = null;

		public WeaponInfo WeaponInfo { get; private set; }

		public override void RulesetLoaded(Ruleset rules, ActorInfo ai)
		{
			base.RulesetLoaded(rules, ai);
			if (!rules.Weapons.TryGetValue(Weapon.ToLowerInvariant(), out var weapon))
				throw new YamlException($"Weapons Ruleset does not contain an entry '{Weapon.ToLowerInvariant()}'");

			WeaponInfo = weapon;
		}

		public override object Create(ActorInitializer init) { return new PxPointDefense(init.Self, this); }
	}

	public class PxPointDefense : ConditionalTrait<PxPointDefenseInfo>, ITick
	{
		sealed class Mount
		{
			public PxRocket Target;
			public int Aim;
			public int Cooldown;
		}

		readonly Actor self;
		readonly Mount[] mounts;
		BodyOrientation body;
		PxCarrierDeck deck;

		public PxPointDefense(Actor self, PxPointDefenseInfo info)
			: base(info)
		{
			this.self = self;
			mounts = info.Mounts.Select(_ => new Mount()).ToArray();
		}

		protected override void Created(Actor self)
		{
			body = self.TraitOrDefault<BodyOrientation>();
			deck = self.TraitOrDefault<PxCarrierDeck>();
			base.Created(self);
		}

		WPos MountPosition(int i)
		{
			var offset = Info.Mounts[i];
			WPos pos;
			if (deck != null)
				pos = deck.DeckPos(offset);
			else
				pos = self.CenterPosition + (body != null ? body.LocalToWorld(offset.Rotate(self.Orientation)) : WVec.Zero);

			return pos + new WVec(0, 0, Info.MountHeight.Length);
		}

		void ITick.Tick(Actor self)
		{
			if (IsTraitDisabled || self.IsDead)
				return;

			List<PxRocket> threats = null;
			for (var i = 0; i < mounts.Length; i++)
			{
				var mount = mounts[i];
				if (mount.Cooldown > 0)
				{
					mount.Cooldown--;
					continue;
				}

				var from = MountPosition(i);
				if (mount.Target != null)
				{
					if (!mount.Target.InFlight || (mount.Target.Position - from).Length > Info.Range.Length * 3 / 2)
					{
						mount.Target = null;
						continue;
					}

					if (--mount.Aim > 0)
					{
						if (mount.Aim % Math.Max(1, Info.BurstInterval) == 0)
							Fire(from, mount.Target.Position);

						continue;
					}

					// End of the burst: hit or miss, then reload.
					if (self.World.SharedRandom.Next(100) < Info.Chance)
						mount.Target.Intercept();

					mount.Target = null;
					mount.Cooldown = Info.ReloadDelay;
					continue;
				}

				threats ??= FindThreats();
				PxRocket best = null;
				var bestDistance = long.MaxValue;
				foreach (var rocket in threats)
				{
					if (mounts.Any(m => m.Target == rocket))
						continue;

					var d = (rocket.Position - from).LengthSquared;
					if (d <= (long)Info.Range.Length * Info.Range.Length && d < bestDistance)
					{
						best = rocket;
						bestDistance = d;
					}
				}

				if (best == null)
					continue;

				mount.Target = best;
				mount.Aim = Math.Max(1, Info.AimTicks);
				Fire(from, best.Position);
			}
		}

		List<PxRocket> FindThreats()
		{
			var protect = (long)Info.ProtectRadius.Length * Info.ProtectRadius.Length;
			var centre = self.CenterPosition;
			return self.World.Effects.OfType<PxRocket>()
				.Where(r => r.InFlight && r.Interceptable && r.Owner != null && self.Owner.RelationshipWith(r.Owner) == PlayerRelationship.Enemy
					&& (r.TargetPosition - centre).HorizontalLengthSquared <= protect)
				.ToList();
		}

		void Fire(WPos from, WPos to)
		{
			var weapon = Info.WeaponInfo;
			if (weapon?.Projectile == null)
				return;

			var args = new ProjectileArgs
			{
				Weapon = weapon,
				Facing = (to - from).Yaw,
				CurrentMuzzleFacing = () => (to - from).Yaw,
				DamageModifiers = Array.Empty<int>(),
				InaccuracyModifiers = Array.Empty<int>(),
				RangeModifiers = Array.Empty<int>(),
				Source = from,
				CurrentSource = () => from,
				SourceActor = self,
				PassiveTarget = to,
				GuidedTarget = Target.FromPos(to)
			};

			self.World.AddFrameEndTask(w =>
			{
				var projectile = weapon.Projectile.Create(args);
				if (projectile != null)
					w.Add(projectile);

				if (weapon.Report != null && weapon.Report.Length > 0)
					Game.Sound.Play(SoundType.World, weapon.Report, w, from);
			});
		}
	}
}
