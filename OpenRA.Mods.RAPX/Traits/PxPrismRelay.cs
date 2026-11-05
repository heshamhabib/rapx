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
using OpenRA.GameRules;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Prism relay (Prism Tower, IDEA-16 laser satellites): when this actor fires, every linked actor of the same",
		"owner and Group feeds energy into the shot. Links chain: actors within LinkRange of each other form one mesh.",
		"Each feeder adds BonusPerLink % damage (up to MaxBonus), draws a relay beam towards the shooter and",
		"gets the FeedingCondition for FeedingDuration ticks (use it to pause its own attack).")]
	public class PxPrismRelayInfo : ConditionalTraitInfo, Requires<ArmamentInfo>
	{
		[Desc("Actors only link to actors of the same group.")]
		public readonly string Group = "prism";

		[Desc("Maximum distance between two linked actors.")]
		public readonly WDist LinkRange = WDist.FromCells(6);

		[Desc("Extra damage (percent) per feeding actor.")]
		public readonly int BonusPerLink = 40;

		[Desc("Cap on the total extra damage (percent).")]
		public readonly int MaxBonus = 200;

		[Desc("Whether this actor can feed others (false: it only receives).")]
		public readonly bool CanFeed = true;

		[Desc("Whether this actor's own shots are boosted by its mesh.")]
		public readonly bool CanReceive = true;

		[GrantedConditionReference]
		[Desc("Condition granted to a feeder while it recovers from feeding.")]
		public readonly string FeedingCondition = "prism-feeding";

		[Desc("Ticks a feeder keeps the FeedingCondition (and cannot feed again).")]
		public readonly int FeedingDuration = 100;

		[WeaponReference]
		[Desc("Cosmetic weapon (no warheads) fired from each feeder to the next actor in the chain.")]
		public readonly string RelayWeapon = null;

		[Desc("Offset (forward, right, up) of the relay beam's ends from the actor centre, e.g. the crystal.")]
		public readonly WVec BeamOffset = WVec.Zero;

		public WeaponInfo RelayWeaponInfo { get; private set; }

		public override void RulesetLoaded(Ruleset rules, ActorInfo ai)
		{
			base.RulesetLoaded(rules, ai);
			if (RelayWeapon == null)
				return;

			if (!rules.Weapons.TryGetValue(RelayWeapon.ToLowerInvariant(), out var weapon))
				throw new YamlException($"Weapons Ruleset does not contain an entry '{RelayWeapon.ToLowerInvariant()}'");

			RelayWeaponInfo = weapon;
		}

		public override object Create(ActorInitializer init) { return new PxPrismRelay(this); }
	}

	public class PxPrismRelay : ConditionalTrait<PxPrismRelayInfo>, INotifyAttack, IFirepowerModifier, ITick
	{
		int boost;
		int feedingTicks;
		int feedingToken = Actor.InvalidConditionToken;

		public PxPrismRelay(PxPrismRelayInfo info)
			: base(info) { }

		public int LastFeeders { get; private set; }

		bool ReadyToFeed(Actor self)
		{
			return Info.CanFeed && !IsTraitDisabled && feedingTicks <= 0 && !self.IsDead && self.IsInWorld;
		}

		WPos BeamEnd(Actor self)
		{
			return self.CenterPosition + Info.BeamOffset;
		}

		void INotifyAttack.PreparingAttack(Actor self, in Target target, Armament a, Barrel barrel)
		{
			boost = 0;
			LastFeeders = 0;
			if (IsTraitDisabled || !Info.CanReceive)
				return;

			// Breadth-first walk over the mesh: every ready relay within LinkRange of a mesh member joins and feeds
			// the member that found it, so the beams visibly hop along the chain towards the shooter.
			var candidates = self.World.ActorsWithTrait<PxPrismRelay>()
				.Where(p => p.Actor != self && p.Actor.Owner == self.Owner && p.Trait.Info.Group == Info.Group)
				.ToList();
			var queue = new Queue<Actor>();
			var joined = new HashSet<Actor> { self };
			queue.Enqueue(self);
			var feeders = new List<(Actor Feeder, PxPrismRelay Relay, Actor Into)>();
			while (queue.Count > 0)
			{
				var member = queue.Dequeue();
				foreach (var c in candidates)
				{
					if (joined.Contains(c.Actor) || !c.Trait.ReadyToFeed(c.Actor))
						continue;

					var range = c.Trait.Info.LinkRange.Length;
					if ((c.Actor.CenterPosition - member.CenterPosition).HorizontalLengthSquared > (long)range * range)
						continue;

					joined.Add(c.Actor);
					queue.Enqueue(c.Actor);
					feeders.Add((c.Actor, c.Trait, member));
				}
			}

			LastFeeders = feeders.Count;
			boost = System.Math.Min(feeders.Count * Info.BonusPerLink, Info.MaxBonus);
			foreach (var (feeder, relay, into) in feeders)
			{
				relay.StartFeeding(feeder);
				relay.FireRelayBeam(feeder, into);
			}
		}

		void INotifyAttack.Attacking(Actor self, in Target target, Armament a, Barrel barrel)
		{
			// The projectile has taken its damage modifiers by now
			boost = 0;
		}

		int IFirepowerModifier.GetFirepowerModifier()
		{
			return 100 + boost;
		}

		void StartFeeding(Actor self)
		{
			feedingTicks = Info.FeedingDuration;
			if (feedingToken == Actor.InvalidConditionToken && !string.IsNullOrEmpty(Info.FeedingCondition))
				feedingToken = self.GrantCondition(Info.FeedingCondition);
		}

		void FireRelayBeam(Actor self, Actor into)
		{
			var weapon = Info.RelayWeaponInfo;
			if (weapon?.Projectile == null)
				return;

			var source = BeamEnd(self);
			var intoRelay = into.TraitOrDefault<PxPrismRelay>();
			var dest = intoRelay != null ? intoRelay.BeamEnd(into) : into.CenterPosition;
			var args = new ProjectileArgs
			{
				Weapon = weapon,
				Facing = (dest - source).Yaw,
				CurrentMuzzleFacing = () => (dest - source).Yaw,
				DamageModifiers = System.Array.Empty<int>(),
				InaccuracyModifiers = System.Array.Empty<int>(),
				RangeModifiers = System.Array.Empty<int>(),
				Source = source,
				CurrentSource = () => source,
				SourceActor = self,
				PassiveTarget = dest,
				GuidedTarget = Target.FromPos(dest)
			};

			self.World.AddFrameEndTask(w =>
			{
				var projectile = weapon.Projectile.Create(args);
				if (projectile != null)
					w.Add(projectile);

				if (weapon.Report != null && weapon.Report.Length > 0)
					Game.Sound.Play(SoundType.World, weapon.Report, w, source);
			});
		}

		void ITick.Tick(Actor self)
		{
			if (feedingTicks > 0 && --feedingTicks == 0 && feedingToken != Actor.InvalidConditionToken)
				feedingToken = self.RevokeCondition(feedingToken);
		}
	}
}
