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
using OpenRA.Mods.Common.Traits.Radar;
using OpenRA.Mods.RAPX.Projectiles;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Area air defence against missiles (IDEA-26): shoots down hostile PxRocket projectiles (rockets, cruise and",
		"ballistic missiles, drones) that fly within Range and are aimed inside it. Each launch rail fires an interceptor",
		"at the point where the threat will be, and when they meet rolls the Chance for that ThreatType: a hit makes the",
		"threat burst in the air harmlessly. Rails then reload, so many missiles at once saturate the defence. Without a",
		"working radar of the owner (ProvidesRadar, e.g. the Radar Dome) only NoRadarRange percent of the range is covered.")]
	public class PxInterceptorInfo : ConditionalTraitInfo
	{
		[Desc("How far threats are engaged (with radar).")]
		public readonly WDist Range = WDist.FromCells(8);

		[Desc("Percent of Range covered while the owner has no working radar.")]
		public readonly int NoRadarRange = 50;

		[Desc("Interception chance (percent) per PxRocket ThreatType. Types not listed are ignored.")]
		public readonly Dictionary<string, int> Chances = new();

		[Desc("Launch rails: interceptors that can be in the air at once.")]
		public readonly int Rails = 2;

		[Desc("Ticks a rail needs after a launch before it fires again.")]
		public readonly int ReloadDelay = 100;

		[Desc("Interceptor speed per tick (match the Weapon's projectile speed so the shown missile arrives on time).")]
		public readonly WDist Speed = new(400);

		[Desc("Where the interceptors leave from (forward, right, up) relative to the actor's centre.")]
		public readonly WVec LocalOffset = new(0, 0, 256);

		[Desc("At most this many interceptors (from all defences) chase one threat at a time.")]
		public readonly int MaxPerThreat = 1;

		[WeaponReference]
		[FieldLoader.Require]
		[Desc("Cosmetic interceptor weapon fired at the meeting point (an air burst, no damage).")]
		public readonly string Weapon = null;

		public WeaponInfo WeaponInfo { get; private set; }

		public override void RulesetLoaded(Ruleset rules, ActorInfo ai)
		{
			base.RulesetLoaded(rules, ai);
			if (!rules.Weapons.TryGetValue(Weapon.ToLowerInvariant(), out var weapon))
				throw new YamlException($"Weapons Ruleset does not contain an entry '{Weapon.ToLowerInvariant()}'");

			WeaponInfo = weapon;
		}

		public override object Create(ActorInitializer init) { return new PxInterceptor(init.Self, this); }
	}

	public class PxInterceptor : ConditionalTrait<PxInterceptorInfo>, ITick, INotifyKilled, INotifyRemovedFromWorld
	{
		sealed class Rail
		{
			public PxRocket Target;
			public int Flight;
			public int Cooldown;
		}

		readonly Actor self;
		readonly Rail[] rails;
		BodyOrientation body;

		public PxInterceptor(Actor self, PxInterceptorInfo info)
			: base(info)
		{
			this.self = self;
			rails = Enumerable.Range(0, Math.Max(1, info.Rails)).Select(_ => new Rail()).ToArray();
		}

		protected override void Created(Actor self)
		{
			body = self.TraitOrDefault<BodyOrientation>();
			base.Created(self);
		}

		/// <summary>The range covered right now (shorter without radar).</summary>
		public WDist EffectiveRange
		{
			get
			{
				var hasRadar = self.World.ActorsWithTrait<ProvidesRadar>()
					.Any(p => p.Actor.Owner == self.Owner && !p.Actor.IsDead && !p.Trait.IsTraitDisabled);
				return hasRadar ? Info.Range : Info.Range * Info.NoRadarRange / 100;
			}
		}

		WPos LaunchPosition()
		{
			var offset = body != null ? body.LocalToWorld(Info.LocalOffset.Rotate(self.Orientation)) : Info.LocalOffset;
			return self.CenterPosition + offset;
		}

		void ITick.Tick(Actor self)
		{
			if (self.IsDead)
				return;

			var disabled = IsTraitDisabled;
			List<PxRocket> threats = null;
			var range = WDist.Zero;
			foreach (var rail in rails)
			{
				if (rail.Target != null)
				{
					if (--rail.Flight > 0)
						continue;

					// The interceptor reaches the meeting point: hit or miss
					var threat = rail.Target;
					threat.Engagements--;
					if (threat.InFlight && Info.Chances.TryGetValue(threat.ThreatType, out var chance)
						&& self.World.SharedRandom.Next(100) < chance)
						threat.Intercept();

					rail.Target = null;
					rail.Cooldown = Info.ReloadDelay;
					continue;
				}

				if (rail.Cooldown > 0)
				{
					rail.Cooldown--;
					continue;
				}

				if (disabled)
					continue;

				if (threats == null)
				{
					range = EffectiveRange;
					threats = FindThreats(range);
				}

				var from = LaunchPosition();
				foreach (var threat in threats)
				{
					if (threat.Engagements >= Info.MaxPerThreat)
						continue;

					// Meeting point: where the threat will be when an interceptor flying at Speed gets there
					var flight = 1;
					var meet = threat.Position;
					for (var i = 0; i < 4; i++)
					{
						flight = Math.Max(1, (meet - from).Length / Math.Max(1, Info.Speed.Length));
						meet = threat.PositionAt(flight);
					}

					// Too late: it hits before the interceptor gets there, or the meeting point is out of reach
					if (flight >= threat.TicksLeft || (meet - self.CenterPosition).HorizontalLengthSquared > (long)range.Length * range.Length)
						continue;

					rail.Target = threat;
					rail.Flight = flight;
					threat.Engagements++;
					Launch(from, meet);
					break;
				}
			}
		}

		List<PxRocket> FindThreats(WDist range)
		{
			var r2 = (long)range.Length * range.Length;
			var centre = self.CenterPosition;

			// Soonest impact first
			return self.World.Effects.OfType<PxRocket>()
				.Where(r => r.InFlight && r.Owner != null && self.Owner.RelationshipWith(r.Owner) == PlayerRelationship.Enemy
					&& Info.Chances.TryGetValue(r.ThreatType, out var c) && c > 0
					&& (r.TargetPosition - centre).HorizontalLengthSquared <= r2)
				.OrderBy(r => r.TicksLeft)
				.ToList();
		}

		void Launch(WPos from, WPos to)
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

		void Release()
		{
			foreach (var rail in rails)
			{
				if (rail.Target != null)
					rail.Target.Engagements--;

				rail.Target = null;
			}
		}

		void INotifyKilled.Killed(Actor self, AttackInfo e) { Release(); }

		void INotifyRemovedFromWorld.RemovedFromWorld(Actor self) { Release(); }
	}
}
