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
using OpenRA.Activities;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Activities
{
	/// <summary>
	/// IDEA-47 fast rope: fly towards the landing zone, fire smoke on the way in, hover over the spot at the rope
	/// height, drop the ropes, send the soldiers down one by one (PxAirAssault.UnloadTick), cut the ropes loose once
	/// everyone is down and climb back to cruise height.
	/// </summary>
	public class PxFastRope : Activity
	{
		enum Stage { Approach, Arrive, Descend, Unload, Release, Climb }

		readonly Target target;
		readonly PxAirAssault assault;
		readonly Aircraft aircraft;
		readonly Cargo cargo;
		Stage stage;
		int wait;
		bool ropesOut;

		public PxFastRope(Actor self, PxAirAssault assault, in Target target)
		{
			this.target = target;
			this.assault = assault;
			aircraft = self.Trait<Aircraft>();
			cargo = self.Trait<Cargo>();
		}

		protected override void OnFirstRun(Actor self)
		{
			// Fly in until smoke range first; the smoke goes out from there while the helicopter closes in
			if (!target.IsInRange(self.CenterPosition, assault.Info.SmokeRange))
				QueueChild(new Fly(self, target, assault.Info.SmokeRange, targetLineColor: PxAirAssault.LineColor));
		}

		public override bool Tick(Actor self)
		{
			if (IsCanceling)
			{
				if (ropesOut)
					assault.ReleaseRopes();

				return true;
			}

			switch (stage)
			{
				case Stage.Approach:
					if (!cargo.IsEmpty())
						assault.FireSmoke(assault.Ground(target.CenterPosition));

					stage = Stage.Arrive;
					QueueChild(new Fly(self, target, targetLineColor: PxAirAssault.LineColor));
					return false;

				case Stage.Arrive:
					stage = cargo.IsEmpty() ? Stage.Climb : Stage.Descend;
					return false;

				case Stage.Descend:
					if (Fly.VerticalTakeOffOrLandTick(self, aircraft, aircraft.Facing, assault.Info.RopeAltitude))
						return false;

					assault.DeployRopes();
					ropesOut = true;
					wait = assault.Info.RopeDropTicks;
					stage = Stage.Unload;
					return false;

				case Stage.Unload:
					if (wait > 0)
					{
						wait--;
						return false;
					}

					if (!cargo.IsEmpty())
					{
						// Nowhere to stand under the ropes (water, a building, a crowd): the crew waits a moment, then
						// cuts the ropes and climbs away with the rest still aboard
						assault.UnloadTick();
						if (self.World.WorldTick - assault.LastProgress < assault.Info.GiveUpTicks + assault.Info.RopeDropTicks || assault.Sliding)
							return false;

						assault.NotifyBlocked();
					}

					// Hold the hover until the last man has let go of his rope
					if (assault.Sliding)
						return false;

					wait = assault.Info.ReleaseDelay;
					stage = Stage.Release;
					return false;

				case Stage.Release:
					if (wait-- > 0)
						return false;

					assault.ReleaseRopes();
					ropesOut = false;
					stage = Stage.Climb;
					return false;

				default:
					return !Fly.VerticalTakeOffOrLandTick(self, aircraft, aircraft.Facing, aircraft.Info.CruiseAltitude);
			}
		}

		public override IEnumerable<TargetLineNode> TargetLineNodes(Actor self)
		{
			yield return new TargetLineNode(target, PxAirAssault.LineColor);
		}
	}
}
