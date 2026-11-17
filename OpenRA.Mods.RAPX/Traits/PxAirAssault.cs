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
using OpenRA.Graphics;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Activities;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Air assault for transport helicopters (IDEA-47). Before troops go down the helicopter fires smoke rounds:",
		"a wall of white smoke between the landing zone and the nearest enemy it can see (a ring around the zone when",
		"there is none) and a yellow marker at the zone. The smoke hides everyone inside it (PxSmokeScreen).",
		"Two ways down: the normal Unload order (land, then get out) gets the smoke first, and the PxFastRope order",
		"(G, PxFastRopeOrderGenerator) flies to a spot, hovers at RopeAltitude, drops ropes from the doors and the",
		"soldiers slide down them one by one, then the ropes are cut loose and the helicopter climbs away.")]
	public class PxAirAssaultInfo : ConditionalTraitInfo, Requires<CargoInfo>, Requires<AircraftInfo>, Requires<BodyOrientationInfo>
	{
		[ActorReference]
		[Desc("Smoke round that builds the screen.")]
		public readonly string ScreenActor = "smoke.screen";

		[ActorReference]
		[Desc("Smoke round that marks the landing zone (empty: none).")]
		public readonly string MarkerActor = "smoke.lz";

		[Desc("Screening rounds per salvo.")]
		public readonly int ScreenRounds = 4;

		[Desc("The screen stands this far from the landing zone, towards the threat.")]
		public readonly WDist ScreenDistance = new(2560);

		[Desc("Distance between two screening rounds along the wall.")]
		public readonly WDist ScreenSpacing = new(1536);

		[Desc("Enemies this close to the landing zone are what the screen is laid against.")]
		public readonly WDist ThreatRadius = WDist.FromCells(12);

		[Desc("The marker lands this far from the zone, on the side away from the threat.")]
		public readonly WDist MarkerDistance = new(1024);

		[Desc("Ticks before the launcher can fire another salvo.")]
		public readonly int SmokeReloadTicks = 1000;

		[Desc("A fast-roping helicopter fires its smoke when it is this close to the landing zone.")]
		public readonly WDist SmokeRange = WDist.FromCells(7);

		[Desc("Ticks between two rounds of a salvo.")]
		public readonly int LaunchInterval = 3;

		[Desc("Where the rounds leave the helicopter (local offset).")]
		public readonly WVec LauncherOffset = new(0, 0, -128);

		public readonly string LaunchSound = "ra|audio/sfx/smokelaunch.ogg";

		[Desc("The ordinary Unload order (F) on a flying helicopter fast-ropes the troops down where it is instead of",
			"landing. A helicopter already on the ground unloads normally.")]
		public readonly bool RopeOnUnload = true;

		[Desc("Fire smoke before an ordinary landing to unload (when RopeOnUnload is off).")]
		public readonly bool SmokeBeforeLanding = true;

		[Desc("Give up roping (cut the ropes, climb away with the rest aboard) when nobody could get down for this long.")]
		public readonly int GiveUpTicks = 100;

		[FluentReference]
		[Desc("Shown to the owner when there is no room under the ropes.")]
		public readonly string BlockedNotification = "notification-px-fast-rope-blocked";

		[Desc("Rope anchors at the doors (local offsets). Soldiers take turns on the ropes.")]
		public readonly WVec[] RopeOffsets = { new(0, -300, -80), new(0, 300, -80) };

		[Desc("Height the helicopter hovers at while the soldiers rope down.")]
		public readonly WDist RopeAltitude = new(640);

		[Desc("Ticks for a rope to fall from the door to the ground.")]
		public readonly int RopeDropTicks = 10;

		[Desc("Ticks a soldier takes to slide down.")]
		public readonly int SlideTicks = 24;

		[Desc("Ticks between two soldiers on the same rope.")]
		public readonly int RopeInterval = 16;

		[Desc("Ticks the helicopter holds its hover after the last soldier is down, before cutting the ropes.")]
		public readonly int ReleaseDelay = 8;

		[Desc("Soldiers spread out to about this far from the helicopter once they are down.")]
		public readonly WDist ExitDistance = new(2048);

		[Desc("How far above a soldier's position his hands grip the rope.")]
		public readonly int HandsHeight = 150;

		public readonly string RopeSound = "ra|audio/sfx/ropezip.ogg";
		public readonly string RopeDropSound = "ra|audio/sfx/ropedrop.ogg";

		public readonly Color RopeColor = Color.FromArgb(92, 84, 62);
		public readonly Color RopeEdgeColor = Color.FromArgb(30, 28, 22);
		public readonly Color RopeLightColor = Color.FromArgb(158, 148, 118);

		[Desc("Rope thickness in world pixels.")]
		public readonly float RopeWidth = 0.85f;

		[Desc("Order name of the fast-rope order.")]
		public readonly string OrderName = "PxFastRope";

		[VoiceReference]
		public readonly string Voice = "Action";

		public override object Create(ActorInitializer init) { return new PxAirAssault(init.Self, this); }
	}

	public class PxAirAssault : ConditionalTrait<PxAirAssaultInfo>, ITick, ITickRender, IRender, IResolveOrder, IOrderVoice, INotifyActorDisposing
	{
		public static readonly Color LineColor = Color.FromArgb(226, 214, 120);
		const float PixelsPerWorld = 24f / 1024f;

		sealed class Rope
		{
			public WVec Offset;
			public int Deployed = -1;
			public int NextAt;
		}

		/// <summary>A soldier on a rope. He is out of the cargo but not yet in the world: the helicopter moves and draws
		/// him (his own sprite), and he becomes a real unit on the ground the moment he touches down. In the world in mid
		/// air the engine would make him parachute (RideTransport -> ReturnToCell -> Parachute).</summary>
		sealed class Slider
		{
			public Actor Actor;
			public int Rope;
			public WPos Start, Landing;
			public CPos Cell, Exit;
			public SubCell SubCell;
			public int Ticks;
		}

		readonly Actor self;
		readonly Rope[] ropes;
		readonly List<(int Tick, WPos Target, string Actor)> launches = new();
		readonly List<Slider> sliders = new();
		readonly HashSet<(CPos, SubCell)> claimed = new();
		Cargo cargo;
		Aircraft aircraft;
		BodyOrientation body;
		INotifyUnloadCargo[] notifiers;
		Activity smokedUnload;
		int smokeReadyAt;

		// Cosmetic: dust kicked up where the soldiers land
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float3 dust;
		WPos anchor;
		long lastTime = -1;

		public PxAirAssault(Actor self, PxAirAssaultInfo info)
			: base(info)
		{
			this.self = self;
			ropes = info.RopeOffsets.Select(o => new Rope { Offset = o }).ToArray();
			particles = new PxParticles(self.World) { Max = 120 };
			dust = self.World.Map.Tileset switch
			{
				"SNOW" => new float3(0.9f, 0.92f, 0.95f),
				"DESERT" => new float3(0.76f, 0.66f, 0.48f),
				_ => new float3(0.55f, 0.48f, 0.38f),
			};
		}

		protected override void Created(Actor self)
		{
			cargo = self.Trait<Cargo>();
			aircraft = self.Trait<Aircraft>();
			body = self.Trait<BodyOrientation>();
			notifiers = self.TraitsImplementing<INotifyUnloadCargo>().ToArray();
			base.Created(self);
		}

		/// <summary>Has soldiers aboard and may rope them down.</summary>
		public bool CanRope => !IsTraitDisabled && cargo != null && !cargo.IsEmpty();

		public bool SmokeReady => self.World.WorldTick >= smokeReadyAt;

		/// <summary>Someone is still on a rope.</summary>
		public bool Sliding => sliders.Count > 0;

		public WPos Ground(WPos p)
		{
			var map = self.World.Map;
			var cell = map.CellContaining(p);
			return new WPos(p.X, p.Y, map.Contains(cell) ? map.CenterOfCell(cell).Z : 0);
		}

		WVec Local(WVec offset)
		{
			return body.LocalToWorld(offset.Rotate(body.QuantizeOrientation(self.Orientation)));
		}

		WPos RopeTop(int i) { return self.CenterPosition + Local(ropes[i].Offset); }

		// ------------------------------------------------------------------------------------------------------- orders
		void IResolveOrder.ResolveOrder(Actor self, Order order)
		{
			if (order.OrderString != Info.OrderName || IsTraitDisabled || order.Target.Type != TargetType.Terrain)
				return;

			self.QueueActivity(order.Queued, new PxFastRope(self, this, order.Target));
			self.ShowTargetLines();
		}

		string IOrderVoice.VoicePhraseForOrder(Actor self, Order order)
		{
			return order.OrderString == Info.OrderName ? Info.Voice : null;
		}

		// -------------------------------------------------------------------------------------------------------- smoke
		void ITick.Tick(Actor self)
		{
			if (sliders.Count > 0)
				TickSliders();

			// The ordinary Unload order on a flying helicopter: instead of landing, hover where it is and rope the troops
			// down (or, with roping off, at least lay smoke while it lands)
			if (self.CurrentActivity is UnloadCargo unload && unload != smokedUnload && !unload.IsCanceling)
			{
				smokedUnload = unload;
				if (!aircraft.AtLandAltitude && !cargo.IsEmpty() && !IsTraitDisabled)
				{
					if (Info.RopeOnUnload)
						self.QueueActivity(false, new PxFastRope(self, this, Target.FromPos(Ground(self.CenterPosition))));
					else if (Info.SmokeBeforeLanding)
						FireSmoke(Ground(self.CenterPosition));
				}
			}

			if (launches.Count == 0)
				return;

			var now = self.World.WorldTick;
			for (var i = 0; i < launches.Count; i++)
			{
				var l = launches[i];
				if (l.Tick > now)
					continue;

				launches.RemoveAt(i--);
				Launch(l.Target, l.Actor);
			}
		}

		/// <summary>Fires a salvo of smoke at the landing zone (if the launcher is loaded): a wall between the zone and
		/// the nearest enemy that can shoot, or a ring when no enemy is in sight, and a marker at the zone.</summary>
		public void FireSmoke(WPos lz)
		{
			if (IsTraitDisabled || !SmokeReady)
				return;

			var world = self.World;
			smokeReadyAt = world.WorldTick + Info.SmokeReloadTicks;

			Actor threat = null;
			var best = long.MaxValue;
			foreach (var a in world.FindActorsInCircle(lz, Info.ThreatRadius))
			{
				if (a.IsDead || !a.IsInWorld || a.Owner.RelationshipWith(self.Owner) != PlayerRelationship.Enemy)
					continue;

				if (!a.Info.HasTraitInfo<AttackBaseInfo>() || a.Info.HasTraitInfo<AircraftInfo>() || !a.CanBeViewedByPlayer(self.Owner))
					continue;

				var d = (a.CenterPosition - lz).HorizontalLengthSquared;
				if (d < best)
				{
					best = d;
					threat = a;
				}
			}

			// Never the same pattern twice: distances, spacing, angles and timing all vary a little (synced random)
			var random = world.SharedRandom;
			var targets = new List<WPos>();
			WVec away;
			var rounds = Math.Max(1, Info.ScreenRounds);
			var spacing = Info.ScreenSpacing.Length;
			if (threat != null)
			{
				// A ragged wall across the line of fire: rounds spread out perpendicular to the direction of the threat
				var dir = threat.CenterPosition - lz;
				var len = Math.Max(1, dir.HorizontalLength);
				var fx = dir.X * 1024 / len;
				var fy = dir.Y * 1024 / len;
				for (var i = 0; i < rounds; i++)
				{
					var o = (2 * i - (rounds - 1)) * spacing / 2 + random.Next(-spacing / 4, spacing / 4 + 1);
					var d = Info.ScreenDistance.Length + random.Next(-512, 513);
					targets.Add(lz + new WVec((fx * d - fy * o) / 1024, (fy * d + fx * o) / 1024, 0));
				}

				away = new WVec(-fx, -fy, 0);
			}
			else
			{
				// A loose ring: random start, uneven gaps, each round at its own distance
				var start = random.Next(1024);
				for (var i = 0; i < rounds; i++)
				{
					var yaw = new WAngle(start + i * 1024 / rounds + random.Next(-1024 / (rounds * 4), 1024 / (rounds * 4) + 1));
					var d = Info.ScreenDistance.Length + random.Next(-640, 641);
					targets.Add(lz + new WVec(0, -d, 0).Rotate(WRot.FromYaw(yaw)));
				}

				away = new WVec(0, -1024, 0).Rotate(WRot.FromYaw(new WAngle(random.Next(1024))));
			}

			var now = world.WorldTick;
			var at = now;
			if (!string.IsNullOrEmpty(Info.MarkerActor))
			{
				var m = Info.MarkerDistance.Length + random.Next(-256, 257);
				launches.Add((at, lz + away * m / 1024, Info.MarkerActor));
				at += Info.LaunchInterval + random.Next(0, 3);
			}

			foreach (var t in targets)
			{
				launches.Add((at, t, Info.ScreenActor));
				at += Info.LaunchInterval + random.Next(0, 4);
			}
		}

		void Launch(WPos target, string actor)
		{
			var map = self.World.Map;
			var cell = map.CellContaining(target);
			if (!map.Contains(cell))
				return;

			var pos = new WPos(target.X, target.Y, map.CenterOfCell(cell).Z);
			var from = self.CenterPosition + Local(Info.LauncherOffset);
			var owner = self.Owner;
			Game.Sound.Play(SoundType.World, Info.LaunchSound, from);
			self.World.AddFrameEndTask(w => w.CreateActor(actor, new TypeDictionary
			{
				new CenterPositionInit(pos),
				new LocationInit(cell),
				new OwnerInit(owner),
				new PxSmokeLaunchInit(from),
			}));
		}

		// --------------------------------------------------------------------------------------------------------- ropes
		public void DeployRopes()
		{
			var now = self.World.WorldTick;
			LastProgress = now;
			anchor = Ground(self.CenterPosition);
			for (var i = 0; i < ropes.Length; i++)
			{
				ropes[i].Deployed = now;

				// The second rope's first man goes a moment after the first's, then they alternate
				ropes[i].NextAt = now + Info.RopeDropTicks + i * Info.RopeInterval / 2;
				Game.Sound.Play(SoundType.World, Info.RopeDropSound, RopeTop(i));
			}
		}

		/// <summary>Cuts the ropes loose: they fall from the doors and lie on the ground for a while.</summary>
		public void ReleaseRopes()
		{
			for (var i = 0; i < ropes.Length; i++)
			{
				var rope = ropes[i];
				if (rope.Deployed < 0)
					continue;

				var top = RopeTop(i);
				var effect = new PxDroppedRope(top, Ground(top), Info.RopeWidth, Info.RopeColor, Info.RopeEdgeColor, Info.RopeLightColor,
					Info.RopeDropSound);
				self.World.AddFrameEndTask(w => w.Add(effect));
				rope.Deployed = -1;
			}
		}

		/// <summary>World tick when the ropes went out or the last soldier got onto one (PxFastRope gives up after
		/// GiveUpTicks without progress).</summary>
		public int LastProgress { get; private set; }

		/// <summary>Sends the next soldier down each free rope (PxFastRope's unload stage, synced).</summary>
		public void UnloadTick()
		{
			var world = self.World;
			var map = world.Map;
			var now = world.WorldTick;
			for (var i = 0; i < ropes.Length && !cargo.IsEmpty(); i++)
			{
				var rope = ropes[i];
				if (rope.Deployed < 0 || now < rope.NextAt)
					continue;

				var passenger = cargo.Peek();
				var top = RopeTop(i);
				var landing = FindLanding(passenger, top);
				if (landing == null)
				{
					// Nowhere to stand under this rope yet: try again in a moment
					rope.NextAt = now + 10;
					continue;
				}

				var (cell, subCell) = landing.Value;
				claimed.Add((cell, subCell));
				foreach (var n in notifiers)
					n.Unloading(self);

				cargo.Unload(self, passenger);
				rope.NextAt = now + Info.RopeInterval;
				LastProgress = now;

				// Away from the helicopter on the side of his door, fanned out a little so the squad spreads
				var side = top - self.CenterPosition;
				var sideLen = Math.Max(1, side.HorizontalLength);
				var dir = new WVec(side.X * 1024 / sideLen, side.Y * 1024 / sideLen, 0);
				var jitter = world.SharedRandom.Next(-640, 641);
				var fan = new WVec(-dir.Y * jitter / 1024, dir.X * jitter / 1024, 0);
				var exitPos = top + dir * Info.ExitDistance.Length / 1024 + fan;

				// Hands on the rope at the door, facing the fuselage
				var start = top - new WVec(0, 0, Info.HandsHeight);
				var f = passenger.TraitOrDefault<IFacing>();
				if (f != null)
					f.Facing = (self.CenterPosition - top).Yaw;

				passenger.Trait<IPositionable>().SetCenterPosition(passenger, start);
				sliders.Add(new Slider
				{
					Actor = passenger,
					Rope = i,
					Start = start,
					Landing = map.CenterOfSubCell(cell, subCell),
					Cell = cell,
					SubCell = subCell,
					Exit = map.Clamp(map.CellContaining(exitPos)),
				});

				Game.Sound.Play(SoundType.World, Info.RopeSound, top);
			}
		}

		/// <summary>Moves the soldiers down their ropes: they ease off the door, drop fast, brake hard at the bottom and
		/// step over to their spot; touching down they become real units again and move out.</summary>
		void TickSliders()
		{
			for (var k = 0; k < sliders.Count; k++)
			{
				var s = sliders[k];
				if (s.Actor.Disposed)
				{
					claimed.Remove((s.Cell, s.SubCell));
					sliders.RemoveAt(k--);
					continue;
				}

				s.Ticks++;
				var t = Math.Min(s.Ticks * 1000 / Math.Max(1, Info.SlideTicks), 1000);

				// Height: smoothstep. Sideways: under the rope until the last stretch, then onto his spot
				var drop = (int)((3L * t * t * 1000 - 2L * t * t * t) / 1000000);
				var step = Math.Max(0, t - 700) * 1000 / 300;
				var pos = new WPos(
					s.Start.X + (int)((long)(s.Landing.X - s.Start.X) * step / 1000),
					s.Start.Y + (int)((long)(s.Landing.Y - s.Start.Y) * step / 1000),
					s.Start.Z + (int)((long)(s.Landing.Z - s.Start.Z) * drop / 1000));
				s.Actor.Trait<IPositionable>().SetCenterPosition(s.Actor, pos);

				if (t < 1000)
					continue;

				sliders.RemoveAt(k--);
				TouchDown(s);
			}
		}

		void TouchDown(Slider s)
		{
			Landed(s.Landing);
			var passenger = s.Actor;
			self.World.AddFrameEndTask(w =>
			{
				claimed.Remove((s.Cell, s.SubCell));
				if (passenger.Disposed || passenger.IsInWorld)
					return;

				var pos = passenger.Trait<IPositionable>();
				pos.SetPosition(passenger, s.Cell, s.SubCell);
				pos.SetCenterPosition(passenger, s.Landing);
				passenger.Trait<Passenger>().OnBeforeAddedToWorld(passenger);
				w.Add(passenger);

				var move = passenger.TraitOrDefault<IMove>();
				if (move != null)
					passenger.QueueActivity(move.MoveTo(s.Exit, 1, evaluateNearestMovableCell: true));
			});
		}

		/// <summary>The helicopter is gone (shot down, sold): whoever is still on a rope lets go where he is.</summary>
		void INotifyActorDisposing.Disposing(Actor self)
		{
			foreach (var s in sliders)
			{
				var passenger = s.Actor;
				var cell = self.World.Map.CellContaining(passenger.CenterPosition);
				var center = passenger.CenterPosition;
				self.World.AddFrameEndTask(w =>
				{
					if (passenger.Disposed || passenger.IsInWorld)
						return;

					var pos = passenger.Trait<IPositionable>();
					pos.SetPosition(passenger, cell);
					pos.SetCenterPosition(passenger, center);
					passenger.Trait<Passenger>().OnBeforeAddedToWorld(passenger);
					w.Add(passenger);
				});
			}

			sliders.Clear();
		}

		(CPos Cell, SubCell SubCell)? FindLanding(Actor passenger, WPos top)
		{
			var map = self.World.Map;
			var pos = passenger.Trait<IPositionable>();
			var under = map.CellContaining(top);
			foreach (var c in map.FindTilesInCircle(under, 1).OrderBy(c => (map.CenterOfCell(c) - top).HorizontalLengthSquared))
			{
				if (!map.Contains(c))
					continue;

				var sub = pos.GetAvailableSubCell(c);
				if (sub == SubCell.Invalid || claimed.Contains((c, sub)))
					continue;

				return (c, sub);
			}

			return null;
		}

		/// <summary>No room to rope down: tell the owner.</summary>
		public void NotifyBlocked()
		{
			TextNotificationsManager.AddTransientLine(self.Owner, Info.BlockedNotification);
		}

		/// <summary>A soldier touched down at `pos`: boots hit the dirt.</summary>
		void Landed(WPos pos)
		{
			// Cosmetic puff of dust around his feet
			var o = pos - anchor;
			for (var k = 0; k < 4; k++)
			{
				var a = (float)(random.NextFloat() * Math.PI * 2);
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Smoke2,
					X = o.X * PixelsPerWorld,
					Y = o.Y * PixelsPerWorld,
					Z = 0.5f,
					VX = MathF.Cos(a) * Rand(0.2f, 0.5f),
					VY = MathF.Sin(a) * Rand(0.1f, 0.3f),
					VZ = Rand(0.02f, 0.08f),
					Drag = 0.08f,
					Life = Rand(22, 34),
					Size = Rand(0.08f, 0.12f),
					Grow = 1.8f,
					Alpha = 0.55f,
					Tint = dust,
					Frame = random.Next(12),
					Angle = random.Next(1024),
					Spin = Rand(-2, 2),
				});
			}
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		// ----------------------------------------------------------------------------------------------------- rendering
		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)self.World.Timestep;
			lastTime = now;
			if (!self.World.Paused && dt > 0)
				particles.Update(dt);
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			var tick = self.World.WorldTick;
			var time = Game.RunTime;
			for (var i = 0; i < ropes.Length; i++)
			{
				var rope = ropes[i];
				if (rope.Deployed < 0)
					continue;

				var top = RopeTop(i);
				var ground = Ground(top);
				var fall = Math.Clamp((tick - rope.Deployed) / (float)Math.Max(1, Info.RopeDropTicks), 0, 1);
				var reach = fall * fall;
				var bottomZ = top.Z - (int)((top.Z - ground.Z) * reach);

				// Top, then each soldier's hands from the highest down, then the free end swaying in the downwash
				var points = new List<WPos> { top };
				var last = top;
				foreach (var s in sliders.Where(s => s.Rope == i).OrderByDescending(s => s.Actor.CenterPosition.Z))
				{
					last = s.Actor.CenterPosition + new WVec(0, 0, Info.HandsHeight);
					points.Add(last);
				}

				const int Segments = 5;
				var amplitude = sliders.Any(s => s.Rope == i) ? 28f : 64f;
				for (var k = 1; k <= Segments; k++)
				{
					var s = (float)k / Segments;
					var z = last.Z + (bottomZ - last.Z) * s;
					var phase = time * 0.0055f + i * 1.9f;
					var sway = amplitude * MathF.Pow(s, 1.5f);
					var dx = MathF.Sin(phase - s * 1.2f) * sway;
					var dy = MathF.Cos(phase * 0.7f - s) * sway * 0.5f;
					points.Add(new WPos(last.X + (int)dx, last.Y + (int)dy, (int)z));
				}

				// Sorts just under the helicopter (whose sprite sorts at its CenterPosition) and over the soldiers
				yield return new PxRopeRenderable(points.ToArray(), top, -16, Info.RopeWidth, Info.RopeColor, Info.RopeEdgeColor, Info.RopeLightColor);
			}

			// The soldiers on the ropes, drawn with their own sprites
			foreach (var s in sliders)
				foreach (var r in s.Actor.Render(wr))
					yield return r;

			if (particles.Items.Count > 0)
				foreach (var r in particles.Render(anchor, 128))
					yield return r;
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			if (ropes.All(r => r.Deployed < 0) && sliders.Count == 0 && particles.Items.Count == 0)
				yield break;

			var c = wr.ScreenPxPosition(self.CenterPosition);
			var g = wr.ScreenPxPosition(Ground(self.CenterPosition));
			yield return Rectangle.FromLTRB(Math.Min(c.X, g.X) - 96, Math.Min(c.Y, g.Y) - 48, Math.Max(c.X, g.X) + 96, Math.Max(c.Y, g.Y) + 64);
		}
	}
}
