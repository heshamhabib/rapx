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
using OpenRA.Activities;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Activities
{
	/// <summary>
	/// A jet's part in a formation strike (PxStrikeGroup): the lead flies attack passes at the target (in, past and out
	/// of range, a wide turn, in again); the others hold their places in the Vs, close up on the run in and fire as
	/// their weapons come into range. Firing itself is AttackFollow's, as with the engine's FlyAttack. A jet out of
	/// ammo, or ordered alone, drops out and finishes with the engine's FlyAttack (rearm and come back).
	/// </summary>
	public class PxFormationStrike : Activity
	{
		readonly Aircraft aircraft;
		readonly AttackAircraft attack;
		readonly Rearmable rearmable;
		readonly PxStrikeFormation formation;
		readonly PxStrikeGroup group;
		readonly bool forceAttack;
		readonly Color? targetLineColor;

		Target target;
		Target lastVisibleTarget;
		bool hasTicked;
		bool solo;

		public PxFormationStrike(Actor self, in Target target, bool forceAttack, Color? targetLineColor, PxStrikeGroup group)
		{
			this.target = target;
			this.forceAttack = forceAttack;
			this.targetLineColor = targetLineColor;
			this.group = group;
			aircraft = self.Trait<Aircraft>();
			attack = self.Trait<AttackAircraft>();
			rearmable = self.TraitOrDefault<Rearmable>();
			formation = self.Trait<PxStrikeFormation>();

			if ((target.Type == TargetType.Actor && target.Actor.CanBeViewedByPlayer(self.Owner))
				|| target.Type == TargetType.FrozenActor || target.Type == TargetType.Terrain)
				lastVisibleTarget = Target.FromPos(target.CenterPosition);
		}

		protected override void OnFirstRun(Actor self)
		{
			// Ordered alone (or the others were already re-tasked): the engine's own attack, unchanged.
			if (group.Count <= 1)
				DropOut(self);
			else
				QueueChild(new TakeOff(self));
		}

		void DropOut(Actor self)
		{
			solo = true;
			group.Leave(self);
			formation.LastSlot = null;
			QueueChild(new FlyAttack(self, AttackSource.Default, target, forceAttack, targetLineColor));
		}

		public override bool Tick(Actor self)
		{
			if (solo || IsCanceling)
				return true;

			if (aircraft.ForceLanding)
			{
				Cancel(self);
				return true;
			}

			// AttackFollow cancelled the target (e.g. a stance change).
			if (hasTicked && attack.RequestedTarget.Type == TargetType.Invalid)
				return true;

			if (attack.IsTraitPaused)
				return false;

			target = target.Recalculate(self.Owner, out var targetIsHiddenActor);
			if (!targetIsHiddenActor && target.Type == TargetType.Actor)
				lastVisibleTarget = Target.FromTargetPositions(target);
			else if (target.Type == TargetType.FrozenActor && !lastVisibleTarget.IsValidFor(self))
				lastVisibleTarget = Target.FromTargetPositions(target);

			// Killed (not just out of sight): the strike is over.
			if (!targetIsHiddenActor && !target.IsValidFor(self))
				return true;

			var useLastVisibleTarget = targetIsHiddenActor;
			if ((useLastVisibleTarget && !lastVisibleTarget.IsValidFor(self)) || group.Finished)
				return true;

			if (!useLastVisibleTarget)
				attack.SetRequestedTarget(target, forceAttack);

			hasTicked = true;

			// Out of ammo for this target: leave the formation; FlyAttack takes it home to rearm and back again.
			if (rearmable != null && !useLastVisibleTarget
				&& attack.Armaments.All(x => x.IsTraitPaused || !x.Weapon.IsValidAgainst(target, self.World, self)))
			{
				DropOut(self);
				return false;
			}

			group.Ready(self);
			var aim = useLastVisibleTarget ? lastVisibleTarget : target;
			var targetPos = attack.GetTargetPosition(self.CenterPosition, aim);
			var range = attack.GetMaximumRangeVersusTarget(target).Length;

			if (group.IsLead(self))
			{
				FlyLead(self, targetPos, range);

				// Flew over where the hidden target was last seen, and it is not there: everyone breaks off.
				if (useLastVisibleTarget && (targetPos - self.CenterPosition).HorizontalLengthSquared < 1024L * 1024)
				{
					group.Finished = true;
					return true;
				}
			}
			else
				FlyInFormation(self, targetPos, range);

			return false;
		}

		void FlyLead(Actor self, WPos targetPos, int range)
		{
			var desired = group.TickLead(self, targetPos, range);
			var speed = group.Speed;
			if (group.FormingUp())
				speed = Math.Max(1, speed * self.World.WorldActor.Trait<PxStrikeFormations>().Info.FormUpSpeed / 100);

			// Turn no tighter than TurnRadius, so the whole V comes round together.
			var radius = Math.Max(1024, self.World.WorldActor.Trait<PxStrikeFormations>().Info.TurnRadius.Length);
			var rate = (int)Math.Clamp(speed * 1024L / (2 * 3217L * radius / 1024), 1, aircraft.TurnSpeed.Angle);
			aircraft.Facing = Util.TickFacing(aircraft.Facing, desired, new WAngle(rate));

			var move = aircraft.FlyStep(speed, aircraft.Facing);
			Fly.FlyTick(self, aircraft, aircraft.Facing, aircraft.Info.CruiseAltitude, move);
			formation.LastMove = move;
			formation.LastSlot = null;
			group.RecordPath(self);
		}

		void FlyInFormation(Actor self, WPos targetPos, int range)
		{
			var place = group.Slot(self);
			if (place == null)
				return;

			var (slot, facing, run) = place.Value;
			var speed = Math.Max(1, aircraft.MovementSpeed);
			var leadMove = group.Lead?.TraitOrDefault<PxStrikeFormation>()?.LastMove ?? aircraft.FlyStep(facing);

			// Fly the place's own motion (in a turn the outer wing flies faster than the leader and the inner wing
			// slower) and close the gap; far away, head for the place flat out.
			var slotMove = formation.LastSlot.HasValue ? slot - formation.LastSlot.Value : leadMove;
			slotMove = new WVec(slotMove.X, slotMove.Y, 0);
			if (slotMove.HorizontalLength > speed * 2)
				slotMove = leadMove; // it just moved up to another place

			formation.LastSlot = slot;

			var error = slot - self.CenterPosition;
			error = new WVec(error.X, error.Y, 0);
			var velocity = error.HorizontalLength > WDist.FromCells(5).Length ? error : slotMove + error / 5;
			var length = Math.Max(1, velocity.HorizontalLength);
			var clamped = Math.Clamp(length, speed * 2 / 5, speed * 9 / 5);
			velocity = new WVec(velocity.X * clamped / length, velocity.Y * clamped / length, 0);

			// On the run in, a wingman off to the side noses round onto the target as it comes into range, so it
			// fires with its leader (it keeps flying its place; only the nose turns).
			var desired = velocity.Yaw;
			var toTarget = targetPos - self.CenterPosition;
			if (run && toTarget.HorizontalLength < range + 1024)
			{
				var aimYaw = new WVec(toTarget.X, toTarget.Y, 0).Yaw;
				if (PxStrikeGroup.AngleBetween(aimYaw, desired) < 128)
					desired = aimYaw;
			}

			Fly.FlyTick(self, aircraft, desired, aircraft.Info.CruiseAltitude, velocity);
			formation.LastMove = velocity;
		}

		protected override void OnLastRun(Actor self)
		{
			group.Leave(self);
			formation.LastSlot = null;

			// Stop chasing the target, but keep firing on it while in range (as FlyAttack does).
			if (!solo)
				attack.ClearRequestedTarget();
		}

		public override IEnumerable<TargetLineNode> TargetLineNodes(Actor self)
		{
			if (solo && ChildActivity != null)
			{
				foreach (var n in ChildActivity.TargetLineNodes(self))
					yield return n;

				yield break;
			}

			if (targetLineColor != null)
				yield return new TargetLineNode(target.IsValidFor(self) ? target : lastVisibleTarget, targetLineColor.Value);
		}
	}
}
