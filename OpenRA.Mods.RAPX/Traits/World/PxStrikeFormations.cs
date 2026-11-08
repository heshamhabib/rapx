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
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Jets told to attack the same target in one order (PxStrikeFormation) fly and fire as V (arrow) formations.",
		"Up to FormationSize jets make one V (leader + wingmen, alternating left/right by rank). More jets make more Vs,",
		"sized evenly (7 jets = 4 + 3, never 5 + 2 or a lone jet), that follow the lead V's flight path in trail, each",
		"TrailSpacing behind the one ahead, so every V passes over the target on the same line.")]
	public class PxStrikeFormationsInfo : TraitInfo
	{
		[Desc("Jets in one V (leader + wingmen).")]
		public readonly int FormationSize = 5;

		[Desc("How far each rank of wingmen flies behind the one ahead.")]
		public readonly WDist FormationSpacing = new(2560);

		[Desc("How far each rank of wingmen flies out to the side.")]
		public readonly WDist FormationWidth = new(2816);

		[Desc("Distance along the flight path from one V's leader to the next V's leader.")]
		public readonly WDist TrailSpacing = new(7168);

		[Desc("On the attack run a V closes up to this percent of its normal size, so the wingmen are in range and",
			"fire together with the leader (keep it at or above about 50: closer than ~1.7 cells, jets push apart).")]
		public readonly int RunSpread = 50;

		[Desc("A V starts closing up this far outside the formation's weapon range.")]
		public readonly WDist RunInDistance = new(6144);

		[Desc("After a pass the lead flies on this far beyond the weapon range before it turns back for the next pass.")]
		public readonly WDist ExtendDistance = new(5120);

		[Desc("Turn radius of the lead, wide enough that the outer wingmen keep their places through the turn.")]
		public readonly WDist TurnRadius = new(8192);

		[Desc("Percent of the formation speed the lead flies at while wingmen are still far from their places.")]
		public readonly int FormUpSpeed = 75;

		public override object Create(ActorInitializer init) { return new PxStrikeFormations(this); }
	}

	public sealed class PxStrikeFormations
	{
		public readonly PxStrikeFormationsInfo Info;

		// Groups opened by the orders resolved this tick: every jet of one click gets its own Attack order, all with
		// the same target and all resolved in the same tick.
		readonly Dictionary<(Player Owner, string Target, bool Queued), PxStrikeGroup> joining = new();
		int joiningTick = -1;

		public PxStrikeFormations(PxStrikeFormationsInfo info)
		{
			Info = info;
		}

		public PxStrikeGroup Join(Actor self, in Target target, bool queued)
		{
			var tick = self.World.WorldTick;
			if (tick != joiningTick)
			{
				joining.Clear();
				joiningTick = tick;
			}

			var key = (self.Owner, TargetKey(target), queued);
			if (!joining.TryGetValue(key, out var group))
				joining[key] = group = new PxStrikeGroup(Info);

			group.Join(self);
			return group;
		}

		static string TargetKey(in Target target)
		{
			switch (target.Type)
			{
				case TargetType.Actor:
					return "a" + target.Actor.ActorID;
				case TargetType.FrozenActor:
					return "f" + target.FrozenActor.ID;
				default:
					var p = target.CenterPosition;
					return "t" + p.X + "," + p.Y;
			}
		}
	}

	/// <summary>
	/// One strike: the jets ordered onto a target together. The first jet in the air leads and flies the route; the
	/// group records its path so the trailing Vs can follow it, and works out every other jet's place.
	/// </summary>
	public sealed class PxStrikeGroup
	{
		enum Leg { Inbound, Outbound, Turning }

		readonly PxStrikeFormationsInfo info;

		// Every jet that joined (in order), and those flying in formation (in the order they got airborne).
		readonly List<Actor> members = new();
		readonly List<Actor> ready = new();

		// The lead's recent positions, newest last, long enough for the last V to follow.
		readonly List<WPos> path = new();
		readonly List<int> spreads = new();
		int lastTick = -1;
		Leg leg = Leg.Turning;

		/// <summary>Speed of the slowest jet in formation: the lead flies at this (or slower while forming up).</summary>
		public int Speed { get; private set; }

		/// <summary>Set by the lead when the target is gone (hidden and not at its last known place): all break off.</summary>
		public bool Finished { get; set; }

		public PxStrikeGroup(PxStrikeFormationsInfo info)
		{
			this.info = info;
		}

		public int Count => members.Count;

		public void Join(Actor jet)
		{
			if (!members.Contains(jet))
				members.Add(jet);
		}

		public void Ready(Actor jet)
		{
			if (members.Contains(jet) && !ready.Contains(jet))
				ready.Add(jet);
		}

		public void Leave(Actor jet)
		{
			members.Remove(jet);
			ready.Remove(jet);
		}

		public bool IsLead(Actor jet)
		{
			Prune();
			return ready.Count > 0 && ready[0] == jet;
		}

		public Actor Lead => ready.Count > 0 ? ready[0] : null;

		void Prune()
		{
			ready.RemoveAll(a => a.IsDead || !a.IsInWorld);
			members.RemoveAll(a => a.IsDead || !a.IsInWorld);
		}

		/// <summary>V number (0 = lead V) and place in it (0 = its leader) of the n-th jet of count. The Vs are sized
		/// evenly: the first ones get the odd jets, so 7 = 4 + 3, 11 = 4 + 4 + 3, 12 = 4 + 4 + 4.</summary>
		public static (int V, int Index, int Vs) Place(int n, int count, int size)
		{
			size = Math.Max(1, size);
			var vs = Math.Max(1, (count + size - 1) / size);
			var small = count / vs;
			var extra = count % vs;
			var big = small + 1;
			if (n < extra * big)
				return (n / big, n % big, vs);

			n -= extra * big;
			return (extra + n / Math.Max(1, small), n % Math.Max(1, small), vs);
		}

		/// <summary>Called once per tick by the lead after it moved: records its path, picks the leg of the attack
		/// pattern and closes up / opens out each V.</summary>
		public WAngle TickLead(Actor lead, WPos target, int maxRange)
		{
			var world = lead.World;
			if (lastTick == world.WorldTick)
				return lead.Trait<Aircraft>().Facing;

			lastTick = world.WorldTick;
			Prune();

			var speed = int.MaxValue;
			foreach (var a in ready)
				speed = Math.Min(speed, a.Trait<Aircraft>().MovementSpeed);

			Speed = Math.Max(1, speed == int.MaxValue ? lead.Trait<Aircraft>().MovementSpeed : speed);

			var aircraft = lead.Trait<Aircraft>();
			var pos = lead.CenterPosition;
			var toTarget = target - pos;
			toTarget = new WVec(toTarget.X, toTarget.Y, 0);
			var distance = toTarget.HorizontalLength;
			var forward = new WVec(0, -1024, 0).Rotate(WRot.FromYaw(aircraft.Facing));
			var ahead = WVec.Dot(toTarget, forward) > 0;

			// Inbound: straight at the target. Past it (or over it): fly on until well out of range, then turn back;
			// the turn ends when the nose points at the target again.
			switch (leg)
			{
				case Leg.Inbound:
					if (!ahead || distance < 512)
						leg = Leg.Outbound;
					break;
				case Leg.Outbound:
					if (distance > maxRange + info.ExtendDistance.Length)
						leg = Leg.Turning;
					break;
				default:
					if (ahead && AngleBetween(toTarget.Yaw, aircraft.Facing) < 64)
						leg = Leg.Inbound;
					break;
			}

			// Closing up: each V on its own, as its leader's place comes within reach of the target on the way in.
			var vs = Place(0, Math.Max(1, ready.Count), info.FormationSize).Vs;
			while (spreads.Count < vs)
				spreads.Add(100);

			for (var v = 0; v < vs; v++)
			{
				var (anchor, facing) = PathPoint(v * info.TrailSpacing.Length, lead);
				var toT = target - anchor;
				var fwd = new WVec(0, -1024, 0).Rotate(WRot.FromYaw(facing));
				var run = WVec.Dot(new WVec(toT.X, toT.Y, 0), fwd) > 0
					&& toT.HorizontalLength < maxRange + info.RunInDistance.Length;
				var want = run ? info.RunSpread : 100;
				spreads[v] += Math.Sign(want - spreads[v]) * Math.Min(2, Math.Abs(want - spreads[v]));
			}

			return leg == Leg.Outbound ? aircraft.Facing : toTarget.Yaw;
		}

		/// <summary>Smallest angle between two facings (0-512).</summary>
		public static int AngleBetween(WAngle a, WAngle b)
		{
			var d = (a - b).Angle;
			return d > 512 ? 1024 - d : d;
		}

		/// <summary>Called by the lead after it moved, so the trailing Vs can follow its exact track.</summary>
		public void RecordPath(Actor lead)
		{
			var pos = lead.CenterPosition;
			if (path.Count == 0 || path[^1] != pos)
				path.Add(pos);

			// Keep just enough track for the last V (plus a margin).
			var vs = Place(0, Math.Max(1, ready.Count), info.FormationSize).Vs;
			var needed = (long)vs * info.TrailSpacing.Length + 4096;
			var length = 0L;
			for (var i = path.Count - 1; i > 0; i--)
			{
				length += (path[i] - path[i - 1]).HorizontalLength;
				if (length > needed)
				{
					path.RemoveRange(0, i - 1);
					break;
				}
			}
		}

		/// <summary>Where the lead was `back` (world units, along its track) ago, and which way it was flying. Before
		/// the track is that long, it is extended straight back from its oldest point.</summary>
		(WPos Pos, WAngle Facing) PathPoint(int back, Actor lead)
		{
			var leadFacing = lead.Trait<Aircraft>().Facing;
			if (path.Count == 0)
				return (lead.CenterPosition - new WVec(0, -1024, 0).Rotate(WRot.FromYaw(leadFacing)) * back / 1024, leadFacing);

			var remaining = back;
			var current = path[^1];
			var facing = leadFacing;
			for (var i = path.Count - 1; i > 0; i--)
			{
				var step = current - path[i - 1];
				step = new WVec(step.X, step.Y, 0);
				var length = step.HorizontalLength;
				if (length > 0)
					facing = step.Yaw;

				if (length >= remaining)
					return (current - step * remaining / Math.Max(1, length), facing);

				remaining -= length;
				current = path[i - 1];
			}

			return (current - new WVec(0, -1024, 0).Rotate(WRot.FromYaw(facing)) * remaining / 1024, facing);
		}

		/// <summary>This jet's place in the formation now, the way the formation is flying there, and whether its V
		/// is on its attack run. Null for the lead, or a jet not in formation.</summary>
		public (WPos Slot, WAngle Facing, bool Run)? Slot(Actor jet)
		{
			Prune();
			var n = ready.IndexOf(jet);
			if (n <= 0)
				return null;

			var lead = ready[0];
			var (v, index, _) = Place(n, ready.Count, info.FormationSize);
			var spread = v < spreads.Count ? spreads[v] : 100;

			// The lead V's leader is the lead itself, a step ahead (followers tick before or after it in a tick).
			WPos anchor;
			WAngle facing;
			if (v == 0)
			{
				var leadAircraft = lead.Trait<Aircraft>();
				facing = leadAircraft.Facing;
				anchor = lead.CenterPosition + leadAircraft.FlyStep(Speed, facing);
			}
			else
				(anchor, facing) = PathPoint(v * info.TrailSpacing.Length, lead);

			var rank = (index + 1) / 2;
			var side = index % 2 == 1 ? -1 : 1;
			var rotation = WRot.FromYaw(facing);
			var forward = new WVec(0, -1024, 0).Rotate(rotation);
			var right = new WVec(1024, 0, 0).Rotate(rotation);
			var back = info.FormationSpacing.Length * rank * spread / 100;
			var wide = info.FormationWidth.Length * rank * side * spread / 100;
			var slot = anchor - forward * back / 1024 + right * wide / 1024;
			return (new WPos(slot.X, slot.Y, jet.CenterPosition.Z), facing, spread < 100);
		}

		/// <summary>True while any jet in formation is still far from its place (the lead then slows down).</summary>
		public bool FormingUp()
		{
			foreach (var a in ready)
			{
				var slot = Slot(a);
				if (slot != null && (slot.Value.Slot - a.CenterPosition).HorizontalLengthSquared > (long)WDist.FromCells(6).Length * WDist.FromCells(6).Length)
					return true;
			}

			return false;
		}
	}
}
