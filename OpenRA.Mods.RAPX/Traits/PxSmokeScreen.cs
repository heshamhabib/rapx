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
using OpenRA.Graphics;
using OpenRA.Mods.Common;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	/// <summary>Where a smoke round was fired from (PxAirAssault): the canister flies from here to the actor's position.</summary>
	public class PxSmokeLaunchInit : ValueActorInit<WPos>, ISingleInstanceInit
	{
		public PxSmokeLaunchInit(WPos value)
			: base(value) { }
	}

	[Desc("Air assault smoke (IDEA-47): a smoke round fired by a helicopter (PxAirAssault). The canister arcs in from",
		"PxSmokeLaunchInit, lands, and pours out a thick cloud for SmokeTicks. While the cloud is thick it grants",
		"Condition to itself; a ProximityExternalCondition on the same actor uses it to hide everyone inside the cloud",
		"(Cloak@SMOKE in rules/air-assault.yaml). Every canister burns its own way: a hissing jet on ignition, then a plume",
		"that streams off in its own direction (downwind when there is wind) with gusts and sputters. It is drawn in two",
		"layers: a heavy layer rolling along the ground under the units (so the owner still sees his soldiers in it) and a",
		"buoyant column rising and leaning over them, semi-transparent.",
		"It drifts a little with PxWeatherManager wind, purely cosmetic.",
		"Sprites: `pxsmoke can-<band>/spin-<band>` and `pxfx csmoke` (artsrc/fx/make_smoke_fx.py).")]
	public class PxSmokeScreenInfo : TraitInfo
	{
		[Desc("Colour of fresh smoke.")]
		public readonly Color Color = Color.FromArgb(250, 250, 246);

		[Desc("Colour the smoke thins out to.")]
		public readonly Color FadeColor = Color.FromArgb(222, 226, 228);

		[Desc("Colour of the burning composition in the vent.")]
		public readonly Color VentColor = Color.FromArgb(255, 186, 96);

		[SequenceReference(nameof(Image))]
		[Desc("The canister lying on the ground.")]
		public readonly string CanSequence = "can-white";

		[SequenceReference(nameof(Image))]
		[Desc("The canister tumbling through the air.")]
		public readonly string SpinSequence = "spin-white";

		public readonly string Image = "pxsmoke";

		[Desc("Size of the canister sprite.")]
		public readonly float CanisterScale = 1.25f;

		[Desc("Flight time of the round: MinFlightTicks plus one tick per FlightSpeed of distance.")]
		public readonly int MinFlightTicks = 20;

		public readonly WDist FlightSpeed = new(120);

		[Desc("Highest point of the round's arc above the straight line, plus a third of the distance flown.")]
		public readonly WDist ArcHeight = new(512);

		[Desc("Filmed smoke burst when the canister ignites (sequences of image pxvideofx, one picked at random), tinted",
			"with Color. Empty = particles only.")]
		public readonly string[] Video = { "smoke-grenade-1" };

		public readonly float VideoScale = 0.6f;

		[Desc("How long the canister pours out smoke, in ticks after it lands.")]
		public readonly int SmokeTicks = 550;

		[Desc("Ticks after landing before the cloud is thick enough to hide anyone.")]
		public readonly int BuildTicks = 30;

		[Desc("The cloud stops hiding units this many ticks before the canister is spent.")]
		public readonly int ThinTicks = 60;

		[GrantedConditionReference]
		[Desc("Granted to this actor while the cloud is thick.")]
		public readonly string Condition = "smoking";

		[Desc("Size of the cloud: scales how far the plume streams (cosmetic, match the ProximityExternalCondition Range).")]
		public readonly WDist Radius = new(2048);

		[Desc("How far the cloud's centre drifts in calm air ...")]
		public readonly WDist CalmDrift = new(128);

		[Desc("... and in a gale (PxWeatherManager wind strength 1000).")]
		public readonly WDist GaleDrift = new(768);

		[Desc("Puffs per tick at full output (each canister burns a little stronger or weaker, and in gusts).")]
		public readonly float PuffRate = 3f;

		[Desc("Share of the puffs that rise as a buoyant column instead of rolling along the ground.")]
		public readonly float RiseShare = 0.35f;

		[Desc("Opacity of the ground layer (drawn under units).")]
		public readonly float FogAlpha = 0.85f;

		[Desc("Opacity of the rising column (drawn over units: keep it moderate so soldiers in the smoke stay visible).")]
		public readonly float RiseAlpha = 0.6f;

		[Desc("How far the plume streams away from the canister in still air, in world pixels per tick of puff speed.")]
		public readonly float PlumeSpeed = 0.45f;

		[Desc("Most particles of one cloud (ground layer; the rising column gets half of it).")]
		public readonly int MaxParticles = 420;

		[Desc("Played where the round lands and ignites.")]
		public readonly string IgniteSound = "ra|audio/sfx/smokehiss.ogg";

		public override object Create(ActorInitializer init) { return new PxSmokeScreen(init, this); }
	}

	public class PxSmokeScreen : ITick, ITickRender, IRender
	{
		const float PixelsPerWorld = 24f / 1024f;

		// The ground layer sorts below everything around it (units stand in it, drawn on top); the rising column and the
		// flying round sort above them
		const int FogZ = -3072;
		const int RiseZ = 2048;
		const int FlatZ = -1024;

		readonly PxSmokeScreenInfo info;
		readonly WPos origin;
		readonly WPos launch;
		readonly int flightTicks;
		readonly int arc;
		PxWeatherManager weather;
		int age;
		int token = Actor.InvalidConditionToken;

		// Cosmetic
		readonly PxParticles fog, rise, air;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly ISpriteSequence can, spin, light, shadow;
		readonly float3 color, fade, vent;
		float emit, trail, burnTime;
		bool launched, burst;

		// Each canister's own character (cosmetic): where its nozzle points, which way its plume streams, how hard it
		// burns, the rhythm of its gusts and how the can lies on the ground
		float windPush;
		readonly float jetAngle, plumeAngle, strength, gustPhase1, gustPhase2, canAngle;
		long lastTime = -1;

		public PxSmokeScreen(ActorInitializer init, PxSmokeScreenInfo info)
		{
			this.info = info;
			var world = init.World;
			origin = init.GetValue<CenterPositionInit, WPos>(world.Map.CenterOfCell(init.GetValue<LocationInit, CPos>()));
			launch = init.GetValue<PxSmokeLaunchInit, WPos>(origin);

			var distance = (origin - launch).HorizontalLength;
			flightTicks = distance == 0 ? 0 : info.MinFlightTicks + distance / Math.Max(1, info.FlightSpeed.Length);
			arc = info.ArcHeight.Length + distance / 3;

			fog = new PxParticles(world) { Max = info.MaxParticles };
			rise = new PxParticles(world) { Max = info.MaxParticles / 2 };
			air = new PxParticles(world) { Max = 120 };
			var sequences = world.Map.Sequences;
			can = sequences.GetSequence(info.Image, info.CanSequence);
			spin = sequences.GetSequence(info.Image, info.SpinSequence);
			light = fog.Sequence("xlight");
			shadow = fog.Sequence("shadow");
			color = ToFloat3(info.Color);
			fade = ToFloat3(info.FadeColor);
			vent = ToFloat3(info.VentColor);

			jetAngle = Rand(0, MathF.PI * 2);
			plumeAngle = jetAngle + Rand(-0.9f, 0.9f);
			strength = Rand(0.8f, 1.2f);
			gustPhase1 = Rand(0, 10);
			gustPhase2 = Rand(0, 10);
			canAngle = Rand(-90, 90);
		}

		static float3 ToFloat3(Color c) { return new float3(c.R / 255f, c.G / 255f, c.B / 255f); }

		static float3 Lerp(float3 a, float3 b, float t) { return new float3(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t, a.Z + (b.Z - a.Z) * t); }

		/// <summary>Ticks since the round landed (negative while it is still in the air).</summary>
		int Burning => age - flightTicks;

		void ITick.Tick(Actor self)
		{
			age++;
			if (Burning == 0)
			{
				weather = self.World.WorldActor.TraitOrDefault<PxWeatherManager>();
				Game.Sound.Play(SoundType.World, info.IgniteSound, origin);
			}

			if (Burning == info.BuildTicks && token == Actor.InvalidConditionToken)
				token = self.GrantCondition(info.Condition);

			if (Burning == info.SmokeTicks - info.ThinTicks && token != Actor.InvalidConditionToken)
				token = self.RevokeCondition(token);

			// The last puffs live ~260 ticks: let them fade before the actor goes
			if (Burning == info.SmokeTicks + 280)
				self.World.AddFrameEndTask(w =>
				{
					if (!self.Disposed)
						self.Dispose();
				});
		}

		/// <summary>The round's position in flight: straight line from the launcher plus a parabolic arc.</summary>
		WPos FlightPosition(float t)
		{
			var x = launch.X + (origin.X - launch.X) * t;
			var y = launch.Y + (origin.Y - launch.Y) * t;
			var z = launch.Z + (origin.Z - launch.Z) * t + 4 * arc * t * (1 - t);
			return new WPos((int)x, (int)y, (int)z);
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		/// <summary>0..1: full output for most of the canister's life, sputtering out over the last fifth.</summary>
		float Output
		{
			get
			{
				var b = Burning;
				if (b < 0 || b >= info.SmokeTicks)
					return 0;

				return Math.Clamp(b / 20f, 0, 1) * Math.Clamp((info.SmokeTicks - b) / (info.SmokeTicks * 0.2f), 0, 1);
			}
		}

		PxParticle Puff(float x, float y, float z, float vx, float vy, float vz, float life, float size, float grow, float alpha)
		{
			return new PxParticle
			{
				Kind = PxParticleKind.Dye,
				X = x,
				Y = y,
				Z = z,
				VX = vx,
				VY = vy,
				VZ = vz,
				Drag = 0.025f,
				Life = life,
				Size = size,
				Grow = grow,
				Alpha = alpha,
				Tint = color,
				TintEnd = fade,
				FadeTint = true,
				Frame = random.Next(12),
				Angle = random.Next(1024),
				Spin = Rand(-1.2f, 1.2f),
				Wind = 1,
			};
		}

		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)self.World.Timestep;
			lastTime = now;
			if (self.World.Paused || dt <= 0)
				return;

			if (weather != null)
			{
				var (direction, strength) = weather.SyncedWind();
				var calm = info.CalmDrift.Length;
				var drift = (calm + (info.GaleDrift.Length - calm) * strength / 1000f) * PixelsPerWorld / 90f;
				var wind = new float2(direction.X / 1024f, direction.Y / 1024f) * drift;
				fog.Wind = wind;
				rise.Wind = wind * 1.8f;
				air.Wind = wind;

				// A real wind takes over from the canister's own drift
				windPush = MathF.Min(1, wind.Length * 40);
			}

			fog.Update(dt);
			rise.Update(dt);
			air.Update(dt);

			if (!launched)
			{
				launched = true;
				LaunchFlash();
			}

			// In flight: a thick white trail behind the tumbling round
			if (Burning < 0)
			{
				trail += dt * 2;
				while (trail >= 1)
				{
					trail--;
					var p = FlightPosition(Math.Clamp((age + random.NextFloat()) / Math.Max(1, flightTicks), 0, 1)) - origin;
					var puff = Puff(p.X * PixelsPerWorld + Rand(-0.3f, 0.3f), p.Y * PixelsPerWorld, p.Z * PixelsPerWorld,
						Rand(-0.05f, 0.05f), Rand(-0.05f, 0.05f), 0.04f, Rand(45, 70), Rand(0.08f, 0.12f), Rand(3, 4), 0.7f);
					puff.Drag = 0.06f;
					air.Add(puff);
				}

				return;
			}

			if (!burst)
			{
				burst = true;
				Burst(self);
			}

			var output = Output;
			if (output <= 0)
				return;

			burnTime += dt;

			// Gusts and sputter: two slow waves and the odd hard puff, different for every canister
			var gust = 0.62f + 0.24f * MathF.Sin(burnTime * 0.071f + gustPhase1) + 0.14f * MathF.Sin(burnTime * 0.023f + gustPhase2);
			if (random.NextFloat() < 0.012f * dt)
				emit += Rand(3, 6);

			// Ignition: a hissing jet out of the nozzle for the first second and a half
			var jet = MathF.Max(0, 1 - Burning / 38f);
			var rate = info.PuffRate * strength * output * gust * (1 + 1.5f * jet);
			emit += dt * rate;

			var plume = new float2(MathF.Cos(plumeAngle), MathF.Sin(plumeAngle) * 0.78f) * (info.PlumeSpeed * info.Radius.Length / 2048f * (1 - 0.6f * windPush));
			var jx = MathF.Cos(jetAngle);
			var jy = MathF.Sin(jetAngle) * 0.78f;
			while (emit >= 1)
			{
				emit--;
				var vx = plume.X;
				var vy = plume.Y;

				// Jet: fast, dense, low, straight out of the nozzle
				if (jet > 0 && random.NextFloat() < jet)
				{
					var v = Rand(1.2f, 2.2f);
					var p = Puff(jx * 1.5f, jy * 1.5f, Rand(0.5f, 1.5f), jx * v + Rand(-0.2f, 0.2f), jy * v + Rand(-0.15f, 0.15f),
						Rand(0.02f, 0.1f), Rand(110, 160), Rand(0.1f, 0.15f), Rand(4, 5.5f), Rand(0.7f, 0.9f) * info.FogAlpha);
					p.Drag = 0.045f;
					p.Wind = 0.5f;
					Shade(ref p, 0.94f);
					fog.Add(p);
					continue;
				}

				// Churning knots right at the vent: small, dense, short-lived, the texture of fresh smoke
				if (random.NextFloat() < 0.2f)
				{
					var p = Puff(Rand(-1, 1), Rand(-0.6f, 0.6f), Rand(1, 4), vx + Rand(-0.3f, 0.3f), vy + Rand(-0.2f, 0.2f),
						Rand(0.1f, 0.35f), Rand(35, 70), Rand(0.06f, 0.1f), Rand(2, 3), Rand(0.65f, 0.85f) * info.RiseAlpha * 1.4f);
					p.Kind = random.NextFloat() < 0.15f ? PxParticleKind.Smoke2 : PxParticleKind.Dye;
					p.Spin = Rand(-3, 3);
					Shade(ref p, Rand(0.92f, 1f));
					rise.Add(p);
					continue;
				}

				var lateral = Rand(-0.35f, 0.35f);
				var px = -plume.Y / 0.78f;
				var py = plume.X * 0.78f;
				if (random.NextFloat() < info.RiseShare)
				{
					// Buoyant column: climbs, speeds up a little as it warms, leans downwind and opens into a cone
					var p = Puff(Rand(-1, 1), Rand(-0.6f, 0.6f), Rand(2, 5), vx * Rand(0.6f, 1.3f) + px * lateral, vy * Rand(0.6f, 1.3f) + py * lateral,
						Rand(0.2f, 0.45f), Rand(160, 240), Rand(0.16f, 0.26f), Rand(5, 7), Rand(0.7f, 1f) * info.RiseAlpha);
					p.Gravity = -Rand(0.002f, 0.005f);
					p.Drag = 0.02f;
					p.Kind = random.NextFloat() < 0.1f ? PxParticleKind.Smoke2 : PxParticleKind.Dye;
					Shade(ref p, Rand(0.95f, 1.02f));
					rise.Add(p);
				}
				else
				{
					// Heavy layer rolling along the ground: streams away downwind and spreads sideways, ragged at the edge
					var reach = random.NextFloat() < 0.15f ? Rand(1.4f, 2f) : Rand(0.4f, 1.2f);
					var p = Puff(Rand(-1.5f, 1.5f), Rand(-1, 1), Rand(0.3f, 2), vx * reach + px * lateral * 1.6f, vy * reach + py * lateral * 1.6f,
						Rand(0.01f, 0.06f), Rand(220, 320), Rand(0.2f, 0.32f), Rand(5, 7), Rand(0.7f, 0.9f) * info.FogAlpha);
					p.Gravity = -0.0012f;
					p.Drag = 0.012f;
					p.Wind = 0.7f;

					// Smoke along the ground sits in its own shadow: a touch darker and cooler than the lit top
					Shade(ref p, Rand(0.9f, 0.97f));
					fog.Add(p);
				}
			}

			// Hot, tinted core right at the vent
			if (random.NextFloat() < 0.5f * dt * output)
			{
				var puff = Puff(Rand(-1, 1), Rand(-0.5f, 0.5f), 1, Rand(-0.4f, 0.4f), Rand(-0.25f, 0.25f), Rand(0.15f, 0.35f),
					Rand(18, 30), Rand(0.1f, 0.14f), 2.5f, 0.9f);
				puff.Tint = Lerp(vent, color, 0.5f);
				puff.Drag = 0.06f;
				puff.Spin = Rand(-3, 3);
				air.Add(puff);
			}
		}

		/// <summary>Darkens a puff's colours by f (self-shadowing: low smoke is darker than the sunlit top).</summary>
		static void Shade(ref PxParticle p, float f)
		{
			p.Tint = new float3(Math.Min(1, p.Tint.X * f), Math.Min(1, p.Tint.Y * f), Math.Min(1, p.Tint.Z * f * 1.02f));
			p.TintEnd = new float3(Math.Min(1, p.TintEnd.X * f), Math.Min(1, p.TintEnd.Y * f), Math.Min(1, p.TintEnd.Z * f * 1.02f));
		}

		/// <summary>The launcher firing: a flash and a puff of propellant smoke at the helicopter.</summary>
		void LaunchFlash()
		{
			var o = launch - origin;
			var x = o.X * PixelsPerWorld;
			var y = o.Y * PixelsPerWorld;
			var z = o.Z * PixelsPerWorld;
			air.Add(new PxParticle { Kind = PxParticleKind.Glow, X = x, Y = y, Z = z, Life = 6, Size = 0.9f, Alpha = 0.9f, Tint = vent });
			for (var i = 0; i < 6; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				air.Add(Puff(x, y, z, MathF.Cos(a) * Rand(0.3f, 0.8f), MathF.Sin(a) * Rand(0.2f, 0.5f), Rand(-0.1f, 0.2f),
					Rand(35, 55), Rand(0.08f, 0.12f), Rand(3, 4), 0.75f));
			}
		}

		/// <summary>Ignition: a pop of hot gas, a ring of smoke rolling out and a few clods of dirt.</summary>
		void Burst(Actor self)
		{
			var clip = PxVideoEffect.Pick(self.World, info.Video, random);
			if (clip != null)
			{
				var at = self.CenterPosition - new WVec(0, 0, self.World.Map.DistanceAboveTerrain(self.CenterPosition).Length);
				var tint = new float3(info.Color.R, info.Color.G, info.Color.B) / 255f;
				self.World.AddFrameEndTask(w => w.Add(new PxVideoEffect(w, at, clip, clip.Scale * info.VideoScale, 600, tint)));
			}

			air.Add(new PxParticle { Kind = PxParticleKind.Glow, Z = 2, Life = 10, Size = 1.2f, Alpha = 0.8f, Tint = vent });

			for (var i = 0; i < 14; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				var v = Rand(0.8f, 1.6f);
				var puff = Puff(0, 0, 1, MathF.Cos(a) * v, MathF.Sin(a) * v * 0.78f, Rand(0.02f, 0.12f), Rand(90, 130),
					Rand(0.14f, 0.2f), Rand(4, 5), 0.8f * info.FogAlpha);
				puff.Drag = 0.05f;
				puff.Wind = 0.6f;
				fog.Add(puff);
			}

			for (var i = 0; i < 5; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				air.Add(new PxParticle
				{
					Kind = PxParticleKind.Debris,
					Z = 1,
					VX = MathF.Cos(a) * Rand(0.3f, 0.8f),
					VY = MathF.Sin(a) * Rand(0.2f, 0.5f),
					VZ = Rand(0.8f, 1.4f),
					Gravity = 0.12f,
					Life = Rand(14, 20),
					Size = Rand(0.05f, 0.08f),
					Alpha = 1,
					Tint = new float3(0.4f, 0.36f, 0.3f),
					Frame = random.Next(16),
					Angle = random.Next(1024),
					Spin = Rand(-20, 20),
				});
			}
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			var now = Game.RunTime;
			var white = new float3(1, 1, 1);
			var b = Burning;

			foreach (var r in fog.Render(origin, FogZ))
				yield return r;

			if (b < 0)
			{
				// The round tumbling through the air, its shadow sliding over the ground below it
				var t = Math.Clamp((float)age / Math.Max(1, flightTicks), 0, 1);
				var pos = FlightPosition(t);
				var ground = new WPos(pos.X, pos.Y, origin.Z);
				if (shadow != null)
					yield return new SpriteRenderable(shadow.GetSprite(0), ground, WVec.Zero, FlatZ, null, shadow.Scale * 0.25f, 0.45f,
						white, TintModifiers.None, false, WAngle.Zero);

				yield return new SpriteRenderable(spin.GetSprite((int)(now / 30) % spin.Length), pos, WVec.Zero, RiseZ, null,
					spin.Scale * info.CanisterScale, 1f, white, TintModifiers.None, false, WAngle.Zero);
			}
			else
			{
				var output = Output;
				if (output > 0)
				{
					var flicker = 0.85f + 0.15f * MathF.Sin(now * 0.031f) * MathF.Sin(now * 0.017f + 1);
					yield return new SpriteRenderable(light.GetSprite(0), origin, WVec.Zero, FlatZ, null, light.Scale * 0.45f,
						0.18f * output * flicker, vent, TintModifiers.None, false, WAngle.Zero);
				}

				// Lands with a hop: the canister bounces once before it settles
				var hop = b < 8 ? (int)(160 * MathF.Sin(b / 8f * MathF.PI)) : 0;
				var frame = output > 0 ? (int)(now / 60) % can.Length : 0;
				var dim = output > 0 ? 1f : 0.55f;
				yield return new SpriteRenderable(can.GetSprite(frame), origin + new WVec(0, 0, hop), WVec.Zero, 0, null,
					can.Scale * info.CanisterScale * 0.8f, 1f, new float3(dim, dim, dim), TintModifiers.None, false, new WAngle((int)canAngle));
			}

			foreach (var r in air.Render(origin, RiseZ))
				yield return r;

			foreach (var r in rise.Render(origin, RiseZ))
				yield return r;
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			var c = wr.ScreenPxPosition(origin);
			var l = wr.ScreenPxPosition(launch);
			yield return Rectangle.FromLTRB(Math.Min(c.X, l.X) - 240, Math.Min(c.Y, l.Y) - 320, Math.Max(c.X, l.X) + 240, Math.Max(c.Y, l.Y) + 180);
		}
	}
}
