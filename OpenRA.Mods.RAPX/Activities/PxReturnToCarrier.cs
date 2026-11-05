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
using OpenRA.Activities;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Mods.RAPX.Traits.Render;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Activities
{
	/// <summary>
	/// IDEA-08 A1: a carrier jet flies back to its (moving) carrier and lands. While the deck is not taking landings it
	/// flies a holding pattern around the ship. Once cleared it lines up astern on the landing strip and glides in,
	/// shrinking smoothly to deck size; it catches the wires, rolls out, taxis to its parking spot and turns into it.
	/// </summary>
	public class PxReturnToCarrier : Activity
	{
		enum Phase { Return, Final, Rollout, Taxi, Park }

		readonly Aircraft aircraft;
		readonly PxCarrierJet jet;
		readonly PxAltitudeScale altitudeScale;
		Phase phase;
		int ticks;
		WVec local; // position on deck while rolling and taxiing (forward, right, up)

		// Final approach: where it started (deck coordinates), its height and on-screen size then, length in ticks.
		WVec finalStart;
		int finalHeight;
		float finalSize;
		int finalTicks;
		int touchdownSpeed;
		int rolloutTicks;
		int taxiSpeed;

		public PxReturnToCarrier(Actor self)
		{
			aircraft = self.Trait<Aircraft>();
			jet = self.Trait<PxCarrierJet>();
			altitudeScale = self.TraitOrDefault<PxAltitudeScale>();
		}

		protected override void OnFirstRun(Actor self)
		{
			// Parked on an airfield: take off first (frees the pad and plays the take-off).
			if (self.World.Map.DistanceAboveTerrain(aircraft.CenterPosition) <= aircraft.LandAltitude)
				QueueChild(new TakeOff(self));
		}

		public override bool Tick(Actor self)
		{
			if (self.IsDead)
				return true;

			if (phase == Phase.Return && IsCanceling)
			{
				jet.Holding = false;
				return true;
			}

			var deck = jet.HomeDeck;
			if (deck == null)
			{
				// The carrier sank or changed hands: on deck the jet goes down with it, in the air it flies home to land.
				var onDeck = jet.OnDeck;
				jet.ClearHome();
				if (onDeck)
					self.Kill(self);

				return true;
			}

			switch (phase)
			{
				case Phase.Return:
					return TickReturn(self, deck);
				case Phase.Final:
					TickFinal(self, deck);
					return false;
				case Phase.Rollout:
					TickRollout(self, deck);
					return false;
				case Phase.Taxi:
					TickTaxi(self, deck);
					return false;
				default:
					return TickPark(self, deck);
			}
		}

		bool TickReturn(Actor self, PxCarrierDeck deck)
		{
			var carrier = jet.Home;
			var speed = Math.Max(1, aircraft.MovementSpeed);
			var toCarrier = carrier.CenterPosition - self.CenterPosition;
			var distance = toCarrier.HorizontalLength;
			var approach = deck.Info.ApproachRange.Length;

			// Cleared jets break off the holding circle (or come straight in), turn onto the landing line astern of
			// the ship and descend to pattern height; at the entry point the scripted final approach takes over.
			var holdingRadius = deck.Info.HoldingRadius.Length;
			if (distance <= Math.Max(approach, holdingRadius * 3 / 2) && deck.CanRecover(self))
			{
				jet.Holding = false;
				var touchdown = deck.DeckPos(deck.Info.RecoveryOffset);
				var axis = deck.DeckPos(deck.Info.RolloutOffset) - touchdown;
				var axisLength = Math.Max(1, axis.HorizontalLength);
				var finalLength = deck.Info.FinalLength.Length;
				var entry = touchdown - new WVec(axis.X * finalLength / axisLength, axis.Y * finalLength / axisLength, 0);
				var toEntry = entry - self.CenterPosition;
				toEntry = new WVec(toEntry.X, toEntry.Y, 0);

				if (toEntry.HorizontalLength <= Math.Max(768, speed * 2))
				{
					StartFinal(self, deck, speed);
					TickFinal(self, deck);
					return false;
				}

				// The break: a tight, banked turn (twice the normal rate) towards the entry point.
				var turn = new WAngle(aircraft.TurnSpeed.Angle * 2);
				aircraft.Facing = Util.TickFacing(aircraft.Facing, toEntry.Yaw, turn);
				var pattern = new WDist(aircraft.Info.CruiseAltitude.Length * deck.Info.PatternAltitude / 100);
				Fly.FlyTick(self, aircraft, aircraft.Facing, pattern, aircraft.FlyStep(aircraft.Facing));
				return false;
			}

			// Holding pattern: head for the carrier, then circle it at HoldingRadius until cleared. The first jet to
			// arrive leads; the others form up on it in a V.
			var radius = deck.Info.HoldingRadius.Length;

			// Join the holding pattern inside 1.5x the radius; once in, stay in up to 3x (outer wingmen and the
			// trailing Vs fly well outside the circle and must not drop out and reshuffle the formation).
			jet.Holding = distance <= (jet.Holding ? radius * 3 : radius * 3 / 2);
			if (jet.Holding)
			{
				var (group, index, groupLeader, lead, groups) = deck.FormationSlot(self);
				if (index > 0)
				{
					FlyInFormation(self, deck, groupLeader, index, speed);
					return false;
				}

				if (group > 0)
				{
					FlyOnStation(self, carrier, lead, group, groups, radius, speed);
					return false;
				}
			}

			WAngle desired;
			if (distance > radius * 3 / 2 || distance == 0)
				desired = toCarrier.Yaw;
			else
			{
				// Tangent to the circle, bent inwards when too far out and outwards when too close.
				var error = ((distance - radius) * 256 / radius).Clamp(-128, 128);
				desired = toCarrier.Yaw + new WAngle(256 - error);
			}

			Fly.FlyTick(self, aircraft, desired, aircraft.Info.CruiseAltitude);
			var step = aircraft.FlyStep(aircraft.Facing);
			jet.LastMove = new WVec(step.X, step.Y, 0);
			jet.LastSlot = null;
			return false;
		}

		void FlyInFormation(Actor self, PxCarrierDeck deck, Actor leader, int index, int speed)
		{
			// V formation: rank 1 just behind the leader's wings, rank 2 behind that, alternating left and right.
			var leaderAircraft = leader.Trait<Aircraft>();
			var leaderMove = leader.Trait<PxCarrierJet>().LastMove;
			var rank = (index + 1) / 2;
			var side = index % 2 == 1 ? -1 : 1;
			var rotation = WRot.FromYaw(leaderAircraft.Facing);
			var forward = new WVec(0, -1024, 0).Rotate(rotation);
			var right = new WVec(1024, 0, 0).Rotate(rotation);
			var back = deck.Info.FormationSpacing.Length * rank;
			var wide = deck.Info.FormationWidth.Length * rank * side;
			var slot = leader.CenterPosition + leaderMove - forward * back / 1024 + right * wide / 1024;
			Steer(self, slot, leaderMove, speed);
		}

		void FlyOnStation(Actor self, Actor carrier, Actor lead, int group, int groups, int radius, int speed)
		{
			// The other Vs keep their station on the holding circle, spaced evenly behind the lead V.
			var leadMove = lead.Trait<PxCarrierJet>().LastMove;
			var fromCarrier = lead.CenterPosition - carrier.CenterPosition;
			fromCarrier = new WVec(fromCarrier.X, fromCarrier.Y, 0);
			var length = Math.Max(1, fromCarrier.HorizontalLength);
			var onCircle = new WVec(fromCarrier.X * radius / length, fromCarrier.Y * radius / length, 0);

			// Rotate around the carrier by the spacing; pick the direction that lies behind the lead (against its motion).
			var gap = new WAngle(1024 * group / Math.Max(2, groups));
			var a = WRot.FromYaw(gap);
			var b = WRot.FromYaw(-gap);
			var stationA = carrier.CenterPosition + onCircle.Rotate(a);
			var stationB = carrier.CenterPosition + onCircle.Rotate(b);
			var behindA = (long)(stationA.X - lead.CenterPosition.X) * leadMove.X + (long)(stationA.Y - lead.CenterPosition.Y) * leadMove.Y < 0;
			var station = behindA ? stationA : stationB;
			var stationMove = leadMove.Rotate(behindA ? a : b);
			Steer(self, station + stationMove, stationMove, speed);
		}

		void Steer(Actor self, WPos slot, WVec leaderMove, int speed)
		{
			// Fly the slot's own motion (on a circle the outer wing flies faster than the leader, the inner wing
			// slower, so the V turns as one piece) and close the remaining gap; far away, head for the slot flat out.
			var slotMove = jet.LastSlot.HasValue ? slot - jet.LastSlot.Value : leaderMove;
			slotMove = new WVec(slotMove.X, slotMove.Y, 0);
			if (slotMove.HorizontalLength > speed * 2)
				slotMove = leaderMove; // the jet just moved up to another slot

			jet.LastSlot = slot;

			var error = slot - self.CenterPosition;
			error = new WVec(error.X, error.Y, 0);
			var velocity = error.HorizontalLength > WDist.FromCells(5).Length ? error : slotMove + error / 5;
			var length = Math.Max(1, velocity.HorizontalLength);
			var clamped = Math.Clamp(length, speed * 2 / 5, speed * 9 / 5);
			velocity = new WVec(velocity.X * clamped / length, velocity.Y * clamped / length, 0);

			Fly.FlyTick(self, aircraft, velocity.Yaw, aircraft.Info.CruiseAltitude, velocity);
			jet.LastMove = velocity;
		}

		float AltitudeFactor(Actor self)
		{
			return altitudeScale?.Factor(self) ?? 1f;
		}

		void StartFinal(Actor self, PxCarrierDeck deck, int speed)
		{
			phase = Phase.Final;
			ticks = 0;
			finalStart = deck.DeckLocal(self.CenterPosition);
			finalStart = new WVec(finalStart.X, finalStart.Y, 0);
			finalHeight = self.World.Map.DistanceAboveTerrain(self.CenterPosition).Length;
			finalSize = AltitudeFactor(self) * jet.DeckScale;
			touchdownSpeed = Math.Max(1, speed * deck.Info.TouchdownSpeed / 100);

			// Length so that the jet slows evenly from its speed to the touch-down speed over the glide.
			var length = (deck.Info.RecoveryOffset - finalStart).HorizontalLength;
			finalTicks = Math.Max(10, 2 * length / (speed + touchdownSpeed));
		}

		void TickFinal(Actor self, PxCarrierDeck deck)
		{
			// Scripted glide down a steady slope with a flare at the end, slowing to touch-down speed. The on-screen
			// size follows one smooth curve to the parked size: the deck scale makes up whatever the altitude scale
			// does not, so the jet never jumps in size.
			ticks++;
			var u = Math.Min(1f, (float)ticks / finalTicks);
			var v0 = (float)Math.Max(1, aircraft.MovementSpeed);
			var v1 = (float)touchdownSpeed;
			var f = (v0 * u + (v1 - v0) * u * u / 2) / ((v0 + v1) / 2);

			var target = deck.Info.RecoveryOffset;
			var pos = finalStart + new WVec((int)((target.X - finalStart.X) * f), (int)((target.Y - finalStart.Y) * f), 0);
			var glide = 1f - f;
			var height = (int)(finalHeight * Math.Pow(glide, 1.3));
			aircraft.SetPosition(self, deck.DeckPos(pos) + new WVec(0, 0, height));

			var heading = deck.DeckYaw(target - finalStart);
			aircraft.Facing = Util.TickFacing(aircraft.Facing, heading, new WAngle(aircraft.TurnSpeed.Angle * 2));

			var parkedSize = deck.ParkedSize(altitudeScale);
			var e = f * f * (3 - 2 * f);
			var size = finalSize + (parkedSize - finalSize) * e;
			jet.HoldDeckScale(size / Math.Max(0.05f, AltitudeFactor(self)));

			if (u < 1f)
				return;

			// Trap: the hook catches a wire.
			deck.BeginRecovery(self);
			deck.TouchdownEffects(deck.DeckPos(target));
			IsInterruptible = false;
			jet.OnDeck = true;
			jet.HoldDeckScale(deck.Info.ParkedScale);
			local = target;
			aircraft.SetPosition(self, deck.DeckPos(target));
			var rollout = (deck.Info.RolloutOffset - target).HorizontalLength;
			rolloutTicks = Math.Clamp(2 * rollout / Math.Max(1, touchdownSpeed), 6, 40);
			ticks = 0;
			phase = Phase.Rollout;
		}

		void TickRollout(Actor self, PxCarrierDeck deck)
		{
			// The wire pulls the jet to a stop along the strip: starts at touch-down speed and eases out to zero.
			ticks++;
			var x = Math.Min(1f, (float)ticks / Math.Max(1, rolloutTicks));
			var f = 1 - (1 - x) * (1 - x);
			var from = deck.Info.RecoveryOffset;
			var to = deck.Info.RolloutOffset;
			local = from + new WVec((int)((to.X - from.X) * f), (int)((to.Y - from.Y) * f), 0);
			OnDeckAt(self, deck, deck.DeckYaw(to - from));
			if (x >= 1f)
			{
				taxiSpeed = 0;
				phase = Phase.Taxi;
			}
		}

		void TickTaxi(Actor self, PxCarrierDeck deck)
		{
			// Taxi to the spot: pull away gently, brake as it arrives.
			var direction = deck.SpotOffset(self) - local;
			var length = direction.HorizontalLength;
			taxiSpeed = Math.Min(Math.Min(deck.Info.TaxiSpeed, taxiSpeed + 4), length / 5 + 6);
			if (length <= taxiSpeed)
			{
				local = deck.SpotOffset(self);
				phase = Phase.Park;
				OnDeckAt(self, deck, aircraft.Facing);
				return;
			}

			local += new WVec(direction.X * taxiSpeed / length, direction.Y * taxiSpeed / length, 0);
			OnDeckAt(self, deck, Util.TickFacing(aircraft.Facing, deck.DeckYaw(direction), new WAngle(24)));
		}

		bool TickPark(Actor self, PxCarrierDeck deck)
		{
			// Swing the nose into the parking spot, then stand down.
			var desired = deck.SpotFacing(self);
			OnDeckAt(self, deck, Util.TickFacing(aircraft.Facing, desired, new WAngle(24)));
			if (aircraft.Facing != desired)
				return false;

			deck.CompleteRecovery(self);
			return true;
		}

		void OnDeckAt(Actor self, PxCarrierDeck deck, WAngle facing)
		{
			// The ship moves under the jet, so place it in deck coordinates every tick.
			aircraft.SetPosition(self, deck.DeckPos(local));
			aircraft.Facing = facing;
			jet.HoldDeckScale(deck.Info.ParkedScale);
		}

		public override IEnumerable<TargetLineNode> TargetLineNodes(Actor self)
		{
			if (jet.Home != null && !jet.Home.IsDead)
				yield return new TargetLineNode(Target.FromActor(jet.Home), Color.Green);
		}
	}
}
