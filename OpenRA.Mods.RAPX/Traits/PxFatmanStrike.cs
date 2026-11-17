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
using OpenRA.Activities;
using OpenRA.GameRules;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Effects;
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Support power (USA Fatman strike, rules/fatman.yaml): charges like the nuke, then sends the owner's own",
		"strategic bomber (an actor with PxStrategicBomber, built at this airfield) to the target. The bomber takes off",
		"from wherever it is, drops its bomb over the target, flies on and returns to its slot.",
		"Add the bomber's ProvidesPrerequisite to Prerequisites, so the timer only runs while the bomber exists.")]
	public class PxFatmanStrikePowerInfo : SupportPowerInfo
	{
		[ActorReference(typeof(PxStrategicBomberInfo))]
		[FieldLoader.Require]
		[Desc("Bomber actor types that fly the strike.")]
		public readonly string[] Bombers = Array.Empty<string>();

		public override object Create(ActorInitializer init) { return new PxFatmanStrikePower(init.Self, this); }
	}

	public class PxFatmanStrikePower : SupportPower
	{
		readonly PxFatmanStrikePowerInfo info;

		public PxFatmanStrikePower(Actor self, PxFatmanStrikePowerInfo info)
			: base(self, info)
		{
			this.info = info;
		}

		public override void Activate(Actor self, Order order, SupportPowerManager manager)
		{
			base.Activate(self, order, manager);

			// Closest bomber first (there is normally one: BuildLimit 1)
			var bomber = self.World.ActorsHavingTrait<PxStrategicBomber>()
				.Where(a => a.Owner == self.Owner && !a.IsDead && a.IsInWorld && info.Bombers.Contains(a.Info.Name))
				.OrderBy(a => (a.CenterPosition - self.CenterPosition).HorizontalLengthSquared)
				.FirstOrDefault();

			if (bomber == null)
				return;

			PlayLaunchSounds();
			var target = order.Target.CenterPosition;
			target -= new WVec(0, 0, self.World.Map.DistanceAboveTerrain(target).Length);
			var start = bomber.CenterPosition;

			Beacon beacon = null;
			if (Info.DisplayBeacon)
			{
				var total = Math.Max(1, (target - start).HorizontalLength);
				beacon = new Beacon(
					self.Owner,
					target,
					Info.BeaconPaletteIsPlayerPalette,
					Info.BeaconPalette,
					Info.BeaconImage,
					Info.BeaconPoster,
					Info.BeaconPosterPalette,
					Info.BeaconSequence,
					Info.ArrowSequence,
					Info.CircleSequence,
					Info.ClockSequence,
					() => bomber.IsDead ? 1f : 1f - Math.Min(1f, (float)(target - bomber.CenterPosition).HorizontalLength / total),
					Info.BeaconDelay);

				self.World.AddFrameEndTask(w => w.Add(beacon));
			}

			bomber.Trait<PxStrategicBomber>().Strike(bomber, target, beacon);
		}
	}

	[Desc("A strategic bomber that only drops its bomb when a PxFatmanStrikePower sends it (it has no normal attack).")]
	public class PxStrategicBomberInfo : TraitInfo, Requires<AircraftInfo>, IRulesetLoaded
	{
		[WeaponReference]
		[FieldLoader.Require]
		[Desc("The bomb (a GravityBomb projectile falls from the bomber's position).")]
		public readonly string Weapon = null;

		[Desc("Horizontal distance from the target at which the bomb is released.")]
		public readonly WDist DropRange = new(512);

		[Desc("How far the bomber keeps flying straight after the drop before it turns home.")]
		public readonly WDist Overfly = WDist.FromCells(8);

		public WeaponInfo WeaponInfo { get; private set; }

		public override object Create(ActorInitializer init) { return new PxStrategicBomber(this); }

		public void RulesetLoaded(Ruleset rules, ActorInfo ai)
		{
			if (!rules.Weapons.TryGetValue(Weapon.ToLowerInvariant(), out var weapon))
				throw new YamlException($"Weapons Ruleset does not contain an entry '{Weapon.ToLowerInvariant()}'");

			WeaponInfo = weapon;
		}
	}

	public class PxStrategicBomber
	{
		public readonly PxStrategicBomberInfo Info;

		public PxStrategicBomber(PxStrategicBomberInfo info)
		{
			Info = info;
		}

		public void Strike(Actor self, WPos target, Beacon beacon)
		{
			// The bomb run cannot be interrupted: new orders queue after it
			self.QueueActivity(false, new PxBombRun(self, this, target, beacon));
		}

		public void Drop(Actor self, WPos target)
		{
			var weapon = Info.WeaponInfo;
			var source = self.CenterPosition;
			var ground = source - new WVec(0, 0, self.World.Map.DistanceAboveTerrain(source).Length);
			var args = new ProjectileArgs
			{
				Weapon = weapon,
				Facing = self.Orientation.Yaw,
				CurrentMuzzleFacing = () => self.Orientation.Yaw,
				DamageModifiers = self.TraitsImplementing<IFirepowerModifier>().Select(m => m.GetFirepowerModifier()).ToArray(),
				InaccuracyModifiers = Array.Empty<int>(),
				RangeModifiers = Array.Empty<int>(),
				Source = source,
				CurrentSource = () => source,
				SourceActor = self,
				PassiveTarget = ground,
				GuidedTarget = Target.FromPos(ground),
			};

			var projectile = weapon.Projectile.Create(args);
			if (projectile != null)
				self.World.AddFrameEndTask(w => w.Add(projectile));

			if (weapon.Report != null && weapon.Report.Length > 0)
				Game.Sound.Play(SoundType.World, weapon.Report[self.World.SharedRandom.Next(weapon.Report.Length)], source);
		}
	}

	sealed class PxBombRun : Activity
	{
		readonly PxStrategicBomber bomber;
		readonly WPos target;
		readonly Beacon beacon;
		bool dropped;

		public PxBombRun(Actor self, PxStrategicBomber bomber, WPos target, Beacon beacon)
		{
			this.bomber = bomber;
			this.target = target;
			this.beacon = beacon;
			IsInterruptible = false;
		}

		protected override void OnFirstRun(Actor self)
		{
			QueueChild(new Fly(self, Target.FromPos(target), bomber.Info.DropRange));
		}

		public override bool Tick(Actor self)
		{
			if (dropped)
				return true;

			bomber.Drop(self, target);
			dropped = true;

			// The bomb is away: the target marker and its progress clock go at once
			RemoveBeacon(self);

			// Fly on straight so the bomber clears the blast before it turns home
			var map = self.World.Map;
			var ahead = self.CenterPosition + new WVec(0, -bomber.Info.Overfly.Length, 0).Rotate(WRot.FromYaw(self.Orientation.Yaw));
			QueueChild(new Fly(self, Target.FromPos(map.CenterOfCell(map.Clamp(map.CellContaining(ahead))))));
			return false;
		}

		protected override void OnLastRun(Actor self)
		{
			if (!dropped)
				RemoveBeacon(self);
		}

		protected override void OnActorDispose(Actor self)
		{
			if (!dropped)
				RemoveBeacon(self);
		}

		void RemoveBeacon(Actor self)
		{
			if (beacon != null)
				self.World.AddFrameEndTask(w => w.Remove(beacon));
		}
	}
}
