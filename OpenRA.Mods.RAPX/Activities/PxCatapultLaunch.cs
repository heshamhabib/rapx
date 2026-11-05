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
using OpenRA.Activities;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Traits;

namespace OpenRA.Mods.RAPX.Activities
{
	/// <summary>
	/// IDEA-08 A1: a carrier jet taxis from its parking spot to the catapult, lines up with the ship's heading and is
	/// shot along the track (accelerating), leaving the bow already climbing. It then grows back to full size
	/// (PxCarrierJet) while the next activity (attack or climb-out) takes over.
	/// </summary>
	public class PxCatapultLaunch : Activity
	{
		enum Phase { Taxi, LineUp, Shot }

		readonly Aircraft aircraft;
		readonly PxCarrierJet jet;
		readonly Actor carrier;
		Phase phase;
		WVec local;
		int ticks;

		public PxCatapultLaunch(Actor self, Actor carrier, WVec spot)
		{
			aircraft = self.Trait<Aircraft>();
			jet = self.Trait<PxCarrierJet>();
			this.carrier = carrier;
			local = spot;
			IsInterruptible = false;
		}

		protected override void OnFirstRun(Actor self)
		{
			jet.OnDeck = true;
		}

		public override bool Tick(Actor self)
		{
			if (self.IsDead)
				return true;

			var deck = carrier.IsDead || !carrier.IsInWorld || carrier.Owner != self.Owner ? null : carrier.TraitOrDefault<PxCarrierDeck>();
			if (deck == null)
			{
				// The ship went down (or changed hands) under the jet.
				jet.ClearHome();
				self.Kill(self);
				return true;
			}

			var info = deck.Info;
			switch (phase)
			{
				case Phase.Taxi:
				{
					var direction = info.CatapultStart - local;
					var length = direction.HorizontalLength;
					if (length <= info.TaxiSpeed)
					{
						local = info.CatapultStart;
						phase = Phase.LineUp;
						Place(self, deck, aircraft.Facing);
						return false;
					}

					local += new WVec(direction.X * info.TaxiSpeed / length, direction.Y * info.TaxiSpeed / length, 0);
					Place(self, deck, Util.TickFacing(aircraft.Facing, deck.DeckYaw(direction), new WAngle(28)));
					return false;
				}

				case Phase.LineUp:
				{
					var heading = deck.DeckYaw(info.LaunchOffset - info.CatapultStart);
					Place(self, deck, Util.TickFacing(aircraft.Facing, heading, new WAngle(32)));
					if (aircraft.Facing == heading)
					{
						phase = Phase.Shot;
						deck.CatapultFired(self, deck.DeckPos(info.CatapultStart));
					}

					return false;
				}

				default:
				{
					// Accelerate along the track (ease-in); lift off over the last part and leave the bow climbing.
					ticks++;
					var x = Math.Min(1f, (float)ticks / Math.Max(1, info.ShotTicks));
					var f = x * x;
					var from = info.CatapultStart;
					var to = info.LaunchOffset;
					local = from + new WVec((int)((to.X - from.X) * f), (int)((to.Y - from.Y) * f), 0);
					var lift = Math.Max(0f, (x - 0.55f) / 0.45f);
					var pos = deck.DeckPos(local) + new WVec(0, 0, (int)(info.LaunchHeight.Length * lift * lift));
					aircraft.SetPosition(self, pos);
					aircraft.Facing = deck.DeckYaw(to - from);
					jet.HoldDeckScale(info.ParkedScale);
					if (x < 1f)
						return false;

					// Off the bow: from here the jet grows back to full size on its own.
					jet.OnDeck = false;
					return true;
				}
			}
		}

		void Place(Actor self, PxCarrierDeck deck, WAngle facing)
		{
			aircraft.SetPosition(self, deck.DeckPos(local));
			aircraft.Facing = facing;
			jet.HoldDeckScale(deck.Info.ParkedScale);
		}
	}
}
