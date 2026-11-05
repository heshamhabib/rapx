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
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Projectiles
{
	[Desc("High-definition small-arms burst (replaces InstantHit for rifles and machine guns): per round a star-shaped",
		"muzzle flash with a glow, a glowing tracer streak flying to the target, an ejected brass casing, and an impact",
		"with dust, sparks and a flash; a wisp of gun smoke lingers. Damage like InstantHit (once, on the first tick).")]
	public class PxTracerInfo : IProjectileInfo
	{
		[Desc("Rounds drawn per shot (cosmetic; the weapon's warheads apply once).")]
		public readonly int Rounds = 3;

		[Desc("Ticks between rounds.")]
		public readonly int RoundInterval = 2;

		[Desc("Tracer speed per tick.")]
		public readonly WDist Speed = new(1400);

		[Desc("Length of the tracer streak.")]
		public readonly WDist TracerLength = new(420);

		[Desc("Width of the tracer core.")]
		public readonly WDist Width = new(14);

		[Desc("Tracer core / hot colour.")]
		public readonly Color CoreColor = Color.FromArgb(255, 255, 250, 215);

		[Desc("Tracer and flash colour.")]
		public readonly Color Color = Color.FromArgb(255, 255, 190, 70);

		[Desc("Radius of the muzzle flash.")]
		public readonly WDist MuzzleFlare = new(150);

		[Desc("Scatter of the impacts around the target.")]
		public readonly WDist Inaccuracy = new(170);

		[Desc("Eject brass casings.")]
		public readonly bool Casings = true;

		[Desc("Kick up dust at the impacts.")]
		public readonly bool ImpactDust = true;

		[Desc("Equivalent to sequence ZOffset. Controls Z sorting.")]
		public readonly int ZOffset = 1024;

		public IProjectile Create(ProjectileArgs args) { return new PxTracer(this, args); }
	}

	public class PxTracer : IProjectile, ISync
	{
		const float PixelPerWorld = 24f / 1024f;

		readonly PxTracerInfo info;
		readonly ProjectileArgs args;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		readonly List<Round> rounds = new();
		readonly WPos origin;
		PxParticles particles;
		int ticks;

		[Sync]
		WPos target;

		sealed class Round
		{
			public int Start;
			public WPos From;
			public WPos To;
			public int Flight;
			public float FlareAngle;
			public bool Landed;
		}

		public PxTracer(PxTracerInfo info, ProjectileArgs args)
		{
			this.info = info;
			this.args = args;
			origin = args.Source;
			target = args.PassiveTarget;
		}

		float Rand(float a, float b) { return a + rng.NextFloat() * (b - a); }

		float3 Local(WPos p)
		{
			return new float3((p.X - origin.X) * PixelPerWorld, (p.Y - origin.Y) * PixelPerWorld, p.Z * PixelPerWorld);
		}

		void Add(PxParticleKind kind, float3 at, float vx, float vy, float vz, float gravity, float drag, float life, float size,
			float grow, float alpha, float3 tint)
		{
			particles.Add(new PxParticle
			{
				Kind = kind, X = at.X, Y = at.Y, Z = at.Z, VX = vx, VY = vy, VZ = vz, Gravity = gravity, Drag = drag,
				Life = life, Size = size, Grow = grow, Alpha = alpha, Tint = tint,
				Frame = rng.Next(Math.Max(1, particles.FrameCount(kind))), Spin = Rand(-6, 6), Angle = rng.Next(1024),
			});
		}

		public void Tick(World world)
		{
			particles ??= new PxParticles(world);
			particles.Update(1);

			if (ticks == 0)
				args.Weapon.Impact(Target.FromPos(target), new WarheadArgs(args) { ImpactPosition = target });

			if (args.GuidedTarget.IsValidFor(args.SourceActor))
				target = args.GuidedTarget.CenterPosition;

			// Fire the next round of the burst
			if (rounds.Count < info.Rounds && ticks == rounds.Count * info.RoundInterval)
			{
				var from = args.CurrentSource();
				var to = target + new WVec((int)(Rand(-1, 1) * info.Inaccuracy.Length), (int)(Rand(-1, 1) * info.Inaccuracy.Length), 0);
				var dist = (to - from).Length;
				rounds.Add(new Round
				{
					Start = ticks, From = from, To = to, Flight = Math.Max(1, dist / Math.Max(1, info.Speed.Length)),
					FlareAngle = Rand(0, MathF.PI),
				});

				var muzzle = Local(from);
				var dir = to - from;
				var len = Math.Max(1, dir.Length);
				var fx = dir.X / (float)len;
				var fy = dir.Y / (float)len;

				// Gun smoke wisp drifting forward and up
				Add(PxParticleKind.Smoke, muzzle, fx * 0.25f + Rand(-0.05f, 0.05f), fy * 0.15f, Rand(0.15f, 0.3f), 0, 0.06f,
					Rand(22, 34), 0.12f, 2.2f, 0.45f, new float3(0.85f, 0.85f, 0.85f));

				// Brass casing thrown out to the right of the firing direction, bouncing on the ground
				if (info.Casings)
					Add(PxParticleKind.Spark, muzzle - new float3(fx * 6, fy * 6, 2), -fy * Rand(0.8f, 1.3f), fx * Rand(0.8f, 1.3f),
						Rand(1.2f, 1.8f), 0.25f, 0.02f, Rand(26, 36), 0.22f, 0, 1f, new float3(1f, 0.78f, 0.35f));
			}

			// Impacts: dust, sparks and a flash when a tracer arrives
			foreach (var r in rounds)
			{
				if (r.Landed || ticks < r.Start + r.Flight)
					continue;

				r.Landed = true;
				var at = Local(r.To);
				var cell = world.Map.CellContaining(r.To);
				var water = world.Map.Contains(cell) && world.Map.GetTerrainInfo(cell).TargetTypes.Contains("Water");
				if (info.ImpactDust && !water)
					for (var i = 0; i < 3; i++)
						Add(PxParticleKind.Smoke, at, Rand(-0.3f, 0.3f), Rand(-0.2f, 0.2f), Rand(0.2f, 0.5f), 0, 0.08f, Rand(14, 24),
							0.13f, 1.8f, 0.6f, new float3(0.62f, 0.52f, 0.4f));

				for (var i = 0; i < 4; i++)
					Add(PxParticleKind.Spark, at, Rand(-1.4f, 1.4f), Rand(-1f, 1f), Rand(0.6f, 1.8f), 0.18f, 0.03f, Rand(6, 11), 0.2f,
						0, 1f, new float3(1f, 0.85f, 0.55f));
			}

			ticks++;
			var last = (info.Rounds - 1) * info.RoundInterval + 40;
			if (ticks > last && particles.Items.Count == 0)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			if (particles != null)
				foreach (var r in particles.Render(new WPos(origin.X, origin.Y, 0), info.ZOffset))
					yield return r;

			if (wr.World.FogObscures(origin) && wr.World.FogObscures(target))
				yield break;

			foreach (var r in rounds)
			{
				var age = ticks - r.Start;
				if (age <= r.Flight + 2)
					yield return new PxTracerRenderable(info, r.From, r.To, age, r.Flight, r.FlareAngle);
			}
		}
	}

	public class PxTracerRenderable : IRenderable, IFinalizedRenderable
	{
		readonly PxTracerInfo info;
		readonly WPos to;
		readonly int age;
		readonly int flight;
		readonly float flareAngle;

		public PxTracerRenderable(PxTracerInfo info, WPos from, WPos to, int age, int flight, float flareAngle)
		{
			this.info = info;
			Pos = from;
			this.to = to;
			this.age = age;
			this.flight = flight;
			this.flareAngle = flareAngle;
		}

		public WPos Pos { get; }
		public int ZOffset => info.ZOffset;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxTracerRenderable(info, Pos + vec, to + vec, age, flight, flareAngle); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		static Color Alpha(Color c, float a) { return Color.FromArgb((int)Math.Clamp(c.A * a, 0, 255), c.R, c.G, c.B); }

		public void Render(WorldRenderer wr)
		{
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			var start = wr.Screen3DPosition(Pos);
			var end = wr.Screen3DPosition(to);
			var d = end - start;
			var len = (float)Math.Sqrt(d.X * d.X + d.Y * d.Y);
			if (len < 1)
				return;

			var dir = new float3(d.X / len, d.Y / len, 0);
			var w = Math.Max(1f, wr.ScreenVector(new WVec(info.Width, WDist.Zero, WDist.Zero))[0]);

			// Muzzle flash: two frames of a star flare with a glow and a forward cone
			if (age < 2)
			{
				var r = wr.ScreenVector(new WVec(info.MuzzleFlare, WDist.Zero, WDist.Zero))[0] * (age == 0 ? 1f : 0.6f);
				var a = age == 0 ? 1f : 0.55f;
				cr.FillEllipse(start - new float3(r * 1.6f, r * 1.2f, 0), start + new float3(r * 1.6f, r * 1.2f, 0), Alpha(info.Color, 0.28f * a));
				cr.FillEllipse(start - new float3(r * 0.7f, r * 0.55f, 0), start + new float3(r * 0.7f, r * 0.55f, 0), Alpha(info.Color, 0.75f * a));
				for (var i = 0; i < 4; i++)
				{
					var ang = flareAngle + i * MathF.PI / 4;
					var spike = (r * (i % 2 == 0 ? 1.4f : 0.8f)) * new float3(MathF.Cos(ang), MathF.Sin(ang) * 0.75f, 0);
					cr.DrawLine(start - spike, start + spike, Math.Max(1, w * 0.6f), Alpha(info.CoreColor, 0.9f * a));
				}

				cr.DrawLine(start, start + (r * 2.6f) * dir, w * 2.2f, Alpha(info.Color, 0.8f * a));
				cr.DrawLine(start, start + (r * 1.8f) * dir, w, Alpha(info.CoreColor, a));
				cr.FillEllipse(start - new float3(r * 0.3f, r * 0.25f, 0), start + new float3(r * 0.3f, r * 0.25f, 0), Alpha(info.CoreColor, a));
			}

			// Tracer: a glowing streak travelling to the target
			if (age <= flight)
			{
				var t = Math.Min(1f, (age + 0.5f) / Math.Max(1, flight));
				var head = start + t * d;
				var tracerLen = Math.Min(len * t, wr.ScreenVector(new WVec(info.TracerLength, WDist.Zero, WDist.Zero))[0]);
				var tail = head - tracerLen * dir;
				cr.DrawLine(tail, head, w * 4f, Alpha(info.Color, 0.18f));
				cr.DrawLine(tail, head, w * 2f, Alpha(info.Color, 0.5f));
				cr.DrawLine(tail + (tracerLen * 0.4f) * dir, head, w, Alpha(info.CoreColor, 1f));
			}

			// Impact flash
			if (age >= flight && age <= flight + 2)
			{
				var r = wr.ScreenVector(new WVec(info.MuzzleFlare, WDist.Zero, WDist.Zero))[0] * (age == flight ? 0.9f : 0.5f);
				cr.FillEllipse(end - new float3(r, r * 0.7f, 0), end + new float3(r, r * 0.7f, 0), Alpha(info.Color, 0.5f));
				cr.FillEllipse(end - new float3(r * 0.4f, r * 0.3f, 0), end + new float3(r * 0.4f, r * 0.3f, 0), Alpha(info.CoreColor, 0.9f));
			}
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
