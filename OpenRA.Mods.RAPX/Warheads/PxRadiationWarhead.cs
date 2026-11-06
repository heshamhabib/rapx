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
using OpenRA.Effects;
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Warheads;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Warheads
{
	[Desc("Nuclear aftermath: a blinding ground flash and racing shock rings, then a radiation field that glows green",
		"for Duration ticks and keeps damaging the actors inside Radius (infantry by default), strongest at the centre.",
		"The damage is synced; the look is cosmetic (pxfx particles).")]
	public class PxRadiationWarhead : Warhead
	{
		[Desc("Radius of the radiation field.")]
		public readonly WDist Radius = new(5120);

		[Desc("How long the field stays deadly, in ticks (25 ticks = 1 second).")]
		public readonly int Duration = 75;

		[Desc("Ticks between damage pulses.")]
		public readonly int Interval = 5;

		[Desc("Damage per pulse at the centre; it falls off to EdgeDamage percent at the rim.")]
		public readonly int Damage = 2500;

		[Desc("Damage at the rim, in percent of Damage.")]
		public readonly int EdgeDamage = 50;

		[Desc("Only actors with one of these target types are hurt.")]
		public readonly BitSet<TargetableType> AffectedTypes = new("Infantry");

		[Desc("Damage types of the pulses (picks the death animation).")]
		public readonly BitSet<DamageType> DamageTypes = default;

		[Desc("Colour of the radiation glow.")]
		public readonly Color GlowColor = Color.FromArgb(255, 110, 255, 80);

		[Desc("Draw the ground flash and the shock rings.")]
		public readonly bool Shockwave = true;

		public override void DoImpact(in Target target, WarheadArgs args)
		{
			if (target.Type == TargetType.Invalid)
				return;

			var world = args.SourceActor.World;
			var pos = target.CenterPosition;
			var ground = pos - new WVec(0, 0, world.Map.DistanceAboveTerrain(pos).Length);
			var source = args.SourceActor;
			world.AddFrameEndTask(w => w.Add(new PxRadiationEffect(w, ground, this, source)));
		}
	}

	public class PxRadiationEffect : IEffect
	{
		// World units per screen pixel (1024 per 24 pixel cell), as in PxParticles
		const float WorldPerPixel = 1024f / 24f;
		const float FadeTicks = 40;

		readonly World world;
		readonly WPos pos;
		readonly PxRadiationWarhead info;
		readonly Actor source;
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float radius;
		readonly float3 green;
		readonly List<WPos> hurt = new();
		int ticks;
		float time, emitted, nextRing;
		long lastTime = -1;
		bool started;

		public PxRadiationEffect(World world, WPos pos, PxRadiationWarhead info, Actor source)
		{
			this.world = world;
			this.pos = pos;
			this.info = info;
			this.source = source;
			radius = info.Radius.Length / WorldPerPixel;
			green = new float3(info.GlowColor.R / 255f, info.GlowColor.G / 255f, info.GlowColor.B / 255f);
			particles = new PxParticles(world) { Max = 900 };
		}

		public void Tick(World world)
		{
			if (ticks < info.Duration && ticks % Math.Max(1, info.Interval) == 0)
			{
				lock (hurt)
					hurt.Clear();

				foreach (var a in world.FindActorsInCircle(pos, info.Radius).ToList())
				{
					if (a.IsDead || !a.IsInWorld || !a.GetEnabledTargetTypes().Overlaps(info.AffectedTypes))
						continue;

					var distance = (a.CenterPosition - pos).HorizontalLength;
					if (distance > info.Radius.Length)
						continue;

					var percent = 100 - (100 - info.EdgeDamage) * distance / Math.Max(1, info.Radius.Length);
					a.InflictDamage(source, new Damage(info.Damage * percent / 100, info.DamageTypes));
					lock (hurt)
						hurt.Add(a.CenterPosition);
				}
			}

			if (++ticks > info.Duration + FadeTicks)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		void Add(PxParticleKind kind, float x, float y, float z, float size, float grow, float life, float alpha,
			float vx, float vy, float vz, float drag, float3 tint)
		{
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = x,
				Y = y,
				Z = z,
				VX = vx,
				VY = vy,
				VZ = vz,
				Drag = drag,
				Life = life,
				Size = size,
				Grow = grow,
				Alpha = alpha,
				Tint = tint,
				Frame = random.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = Rand(-2, 2),
				Angle = random.Next(1024),
			});
		}

		void Start()
		{
			started = true;
			if (!info.Shockwave)
				return;

			var white = new float3(1f, 0.97f, 0.88f);

			// Blinding flash on the ground and a hot glow pool where the fireball touched down
			Add(PxParticleKind.Glow, 0, 0, 4, radius / 8, 1.2f, 14, 1f, 0, 0, 0, 0, white);
			Add(PxParticleKind.Glow, 0, 0, 2, radius / 12, 0.6f, 60, 0.9f, 0, 0, 0, 0, new float3(1f, 0.62f, 0.2f));
		}

		/// <summary>A point on the ground inside the field, denser towards the centre.</summary>
		(float X, float Y) Spot(float spread)
		{
			var a = Rand(0, MathF.PI * 2);
			var r = MathF.Sqrt(random.NextFloat()) * radius * spread;
			return (MathF.Cos(a) * r, MathF.Sin(a) * r * 0.78f);
		}

		void Emit(float dt)
		{
			// Shock rings racing outwards over the first second
			if (info.Shockwave && time >= nextRing && nextRing < 30)
			{
				var big = nextRing == 0;
				Add(PxParticleKind.Ring, 0, 0, 0, radius / 21, big ? 5.5f : 4f, big ? 24 : 30, big ? 1f : 0.6f, 0, 0, 0, 0,
					big ? new float3(1f, 0.95f, 0.85f) : new float3(1f, 0.75f, 0.45f));
				nextRing += big ? 9 : 14;
			}

			if (time > info.Duration)
				return;

			// Radiation: a breathing green light pool, drifting motes and a pale, sickly haze
			var fadeIn = Math.Clamp((time - 8) / 12f, 0, 1);
			emitted += dt * fadeIn;
			while (emitted >= 1)
			{
				emitted--;
				var (x, y) = Spot(0.95f);
				Add(PxParticleKind.Glow, x, y, 2, Rand(2.2f, 4f), 0.4f, Rand(18, 30), Rand(0.25f, 0.45f), 0, 0, 0, 0, green);
				for (var i = 0; i < 3; i++)
				{
					(x, y) = Spot(1f);
					Add(PxParticleKind.Spark, x, y, Rand(0, 6), Rand(0.5f, 1.1f), 0, Rand(20, 40), Rand(0.6f, 1f),
						Rand(-0.15f, 0.15f), Rand(-0.1f, 0.1f), Rand(0.25f, 0.7f), 0.01f, green);
				}

				if (random.Next(2) == 0)
				{
					(x, y) = Spot(0.9f);
					Add(PxParticleKind.Smoke, x, y, Rand(2, 8), Rand(1.2f, 2.2f), 1.2f, Rand(40, 60), 0.3f,
						Rand(-0.1f, 0.1f), 0, Rand(0.1f, 0.25f), 0.02f, new float3(0.62f, 0.82f, 0.55f));
				}
			}

			// Each soldier the field is killing flickers green
			lock (hurt)
			{
				foreach (var p in hurt)
				{
					if (random.Next(3) != 0)
						continue;

					var x = (p.X - pos.X) / WorldPerPixel;
					var y = (p.Y - pos.Y) / WorldPerPixel;
					Add(PxParticleKind.Glow, x, y, Rand(4, 9), Rand(0.5f, 0.8f), 0.3f, 6, 0.8f, 0, 0, 0.2f, 0, green);
					Add(PxParticleKind.Spark, x + Rand(-2, 2), y, Rand(3, 10), 0.7f, 0, 10, 1f, Rand(-0.3f, 0.3f), 0,
						Rand(0.5f, 1.2f), 0, new float3(0.85f, 1f, 0.75f));
				}
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)world.Timestep;
			lastTime = now;
			if (!world.Paused)
			{
				if (!started)
					Start();

				time += dt;
				Emit(dt);
				particles.Update(dt);
			}

			if (world.FogObscures(pos))
				return Enumerable.Empty<IRenderable>();

			return particles.Render(pos, -512).ToList();
		}
	}
}
