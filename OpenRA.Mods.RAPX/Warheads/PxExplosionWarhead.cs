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
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Warheads;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Warheads
{
	/// <summary>The look of a PxExplosion; each matches a kind of warhead.</summary>
	public enum PxExplosionStyle
	{
		/// <summary>Flash, rolling fireball, sparks, debris and a smoke column.</summary>
		Standard,

		/// <summary>Guided warhead: a sharp, tight flash, lots of sparks, little smoke.</summary>
		Precision,

		/// <summary>Big rocket or ballistic warhead: a wide dust ring, heavy debris and a tall smoke column.</summary>
		Heavy,

		/// <summary>Fuel-air blast: a pale pressure flash, two shock rings, a huge rising fireball and a dark mushroom.</summary>
		Thermobaric,

		/// <summary>Anti-ship hit: a fireball on the ship, burning fuel and thick black smoke, spray around it.</summary>
		Naval,

		/// <summary>Cluster bomblet: a small sharp pop with sparks and a puff of grey smoke.</summary>
		Bomblet,
	}

	[Desc("High-definition explosion (pxfx particles, cosmetic only): a white flash, a rolling fireball, a shock ring,",
		"sparks, debris and a column of smoke that rises and drifts. Air bursts skip the ground debris and scorch.",
		"Does nothing on open water (pair it with the classic splash warhead), but does explode on ships. Plays ImpactSounds like CreateEffect.")]
	public class PxExplosionWarhead : Warhead
	{
		[Desc("Overall size: 1 = a rocket hit, 0.6 = a grenade, 2 = a heavy shell or V2.")]
		public readonly float Size = 1f;

		[Desc("Amount of smoke, as a multiple of the default.")]
		public readonly float Smoke = 1f;

		[Desc("Look of the blast: Standard, Precision, Heavy, Thermobaric, Naval or Bomblet.")]
		public readonly PxExplosionStyle Style = PxExplosionStyle.Standard;

		[Desc("Fire colour (tint of the flames and fireball).")]
		public readonly Color FireColor = Color.FromArgb(255, 255, 209, 140);

		[Desc("Smoke colour.")]
		public readonly Color SmokeColor = Color.FromArgb(255, 204, 199, 191);

		[Desc("Only play when an actor with one of these target types is at the impact (e.g. Ship for a hit on a ship).",
			"Empty = always.")]
		public readonly BitSet<TargetableType> OnlyOn = default;

		[Desc("Do not play when an actor with one of these target types is at the impact.")]
		public readonly BitSet<TargetableType> NotOn = default;

		[Desc("Leave a short-lived scorch mark on the ground.")]
		public readonly bool Scorch = true;

		[Desc("Sounds to play on impact.")]
		public readonly string[] ImpactSounds = Array.Empty<string>();

		public override void DoImpact(in Target target, WarheadArgs args)
		{
			if (target.Type == TargetType.Invalid)
				return;

			var world = args.SourceActor.World;
			var pos = target.CenterPosition;
			var air = world.Map.DistanceAboveTerrain(pos) > AirThreshold;
			if (!air)
			{
				var cell = world.Map.CellContaining(pos);

				// On water only when something is hit there (a ship); plain water keeps the classic splash
				if (!world.Map.Contains(cell) ||
					(world.Map.GetTerrainInfo(cell).TargetTypes.Contains("Water") && !world.FindActorsOnCircle(pos, new WDist(256)).Any()))
					return;
			}

			if (!OnlyOn.IsEmpty || !NotOn.IsEmpty)
			{
				var types = world.FindActorsOnCircle(pos, new WDist(341))
					.SelectMany(a => a.GetEnabledTargetTypes()).ToHashSet();
				if (!OnlyOn.IsEmpty && !types.Any(t => OnlyOn.Contains(t)))
					return;

				if (types.Any(t => NotOn.Contains(t)))
					return;
			}

			world.AddFrameEndTask(w => w.Add(new PxExplosionEffect(w, pos, this, air)));

			var sound = ImpactSounds.RandomOrDefault(world.LocalRandom);
			if (sound != null)
				Game.Sound.Play(SoundType.World, sound, pos);
		}
	}

	public class PxExplosionEffect : IEffect
	{
		const int ScorchZ = -2048;

		readonly World world;
		readonly WPos pos;
		readonly WPos ground;
		readonly PxExplosionWarhead info;
		readonly bool air;
		readonly PxParticles particles;
		readonly ISpriteSequence scorch;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float height;
		float time;
		long lastTime = -1;
		bool started;

		public PxExplosionEffect(World world, WPos pos, PxExplosionWarhead info, bool air)
		{
			this.world = world;
			this.pos = pos;
			this.info = info;
			this.air = air;
			var above = world.Map.DistanceAboveTerrain(pos).Length;
			ground = pos - new WVec(0, 0, above);
			height = above * 24f / 1024f;
			particles = new PxParticles(world);
			scorch = particles.Sequence("scorch");
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		static float3 Shade(float3 c, float f) { return new float3(c.X * f, c.Y * f, c.Z * f); }

		void Add(PxParticleKind kind, float spread, float z, float size, float grow, float life, float alpha,
			float speed, float vz, float gravity, float drag, float3 tint)
		{
			var a = Rand(0, MathF.PI * 2);
			var r = Rand(0, spread);
			var s = Rand(0.4f, 1f) * speed;
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = MathF.Cos(a) * r,
				Y = MathF.Sin(a) * r * 0.6f,
				Z = z,
				VX = MathF.Cos(a) * s,
				VY = MathF.Sin(a) * s * 0.6f,
				VZ = vz,
				Gravity = gravity,
				Drag = drag,
				Life = life * Rand(0.75f, 1.25f),
				Size = size * Rand(0.8f, 1.2f),
				Grow = grow,
				Alpha = alpha,
				Tint = tint,
				Frame = random.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = Rand(-3, 3),
				Angle = random.Next(1024),
			});
		}

		static float3 Tint(Color c) { return new float3(c.R / 255f, c.G / 255f, c.B / 255f); }

		void Start()
		{
			started = true;
			var k = info.Size;
			var white = new float3(1, 1, 1);
			var fire = Tint(info.FireColor);
			var grey = Tint(info.SmokeColor);
			var dust = new float3(0.62f, 0.55f, 0.45f);

			switch (info.Style)
			{
				case PxExplosionStyle.Precision:
					Add(PxParticleKind.Glow, 0, height, 1.1f * k, 0.4f, 5, 1f, 0, 0, 0, 0, new float3(1f, 0.97f, 0.9f));
					if (!air)
						Add(PxParticleKind.Ring, 0, 0, 0.6f * k, 1.4f, 10, 0.9f, 0, 0, 0, 0, white);

					for (var i = 0; i < (int)(6 * k) + 3; i++)
						Add(PxParticleKind.Flame, 2 * k, height + Rand(0, 2 * k), Rand(0.4f, 0.7f) * k, 0.4f, Rand(8, 14), 1f,
							0.9f * k, Rand(0.3f, 1f), 0, 0.15f, fire);

					for (var i = 0; i < (int)(20 * k) + 6; i++)
						Add(PxParticleKind.Spark, 1.5f * k, height + 2, Rand(0.25f, 0.5f), 0, Rand(10, 20), 1f,
							4.5f * k, Rand(1.5f, 4f), air ? 0.05f : 0.22f, 0.03f, new float3(1f, 0.95f, 0.8f));

					for (var i = 0; i < (int)(5 * k * info.Smoke) + 2; i++)
						Add(PxParticleKind.Smoke, 3 * k, height + Rand(2, 5) * k, Rand(0.4f, 0.6f) * k, 2f, Rand(40, 70), 0.75f,
							0.4f * k, Rand(0.2f, 0.45f), 0, 0.03f, Shade(grey, Rand(0.35f, 0.6f)));
					break;

				case PxExplosionStyle.Heavy:
					Add(PxParticleKind.Glow, 0, height, 1.8f * k, 0.7f, 10, 1f, 0, 0, 0, 0, new float3(1f, 0.85f, 0.6f));
					if (!air)
					{
						Add(PxParticleKind.Ring, 0, 0, 1.2f * k, 1.8f, 20, 0.8f, 0, 0, 0, 0, white);

						// Dust thrown out low along the ground
						for (var i = 0; i < (int)(10 * k); i++)
							Add(PxParticleKind.Billow, 5 * k, 1, Rand(0.5f, 0.8f) * k, 2.2f, Rand(50, 80), 0.7f,
								1.6f * k, Rand(0.05f, 0.2f), 0, 0.05f, Shade(dust, Rand(0.75f, 1f)));

						for (var i = 0; i < (int)(12 * k); i++)
							Add(PxParticleKind.Chunk, 3 * k, 2, Rand(0.5f, 1f), 0, Rand(35, 60), 1f,
								2.8f * k, Rand(2f, 4.5f), 0.22f, 0.02f, new float3(0.5f, 0.45f, 0.4f));
					}

					for (var i = 0; i < (int)(8 * k) + 4; i++)
						Add(PxParticleKind.Fireball, 3 * k, height + Rand(1, 5 * k), Rand(0.6f, 1f) * k, 0.8f, Rand(16, 26), 1f,
							1f * k, Rand(0.6f, 1.4f), 0, 0.1f, fire);

					for (var i = 0; i < (int)(12 * k) + 4; i++)
						Add(PxParticleKind.Spark, 2 * k, height + 2, Rand(0.3f, 0.6f), 0, Rand(12, 22), 1f,
							4f * k, Rand(1.5f, 3.5f), air ? 0.05f : 0.2f, 0.04f, white);

					// Tall smoke column
					for (var i = 0; i < (int)(14 * k * info.Smoke) + 4; i++)
						Add(PxParticleKind.Plume, 3 * k, height + Rand(4, 16) * k, Rand(0.6f, 0.9f) * k, 2.6f, Rand(80, 130), 0.85f,
							0.3f * k, Rand(0.4f, 0.9f), 0, 0.03f, Shade(grey, Rand(0.4f, 0.7f)));
					break;

				case PxExplosionStyle.Thermobaric:
					// Pressure flash and two shock rings (the cloud lights, then the blast wave)
					Add(PxParticleKind.Glow, 0, height + 3, 2.6f * k, 0.9f, 14, 1f, 0, 0, 0, 0, new float3(1f, 0.95f, 0.75f));
					if (!air)
					{
						Add(PxParticleKind.Ring, 0, 0, 1.4f * k, 2.2f, 18, 0.9f, 0, 0, 0, 0, new float3(1f, 0.9f, 0.75f));
						Add(PxParticleKind.Ring, 0, 0, 0.8f * k, 3.2f, 30, 0.6f, 0, 0, 0, 0, white);
					}

					// Huge fireball that swells and rises
					for (var i = 0; i < (int)(16 * k) + 6; i++)
						Add(PxParticleKind.Fireball, 5 * k, height + Rand(1, 6 * k), Rand(0.8f, 1.3f) * k, 1.1f, Rand(22, 36), 1f,
							1.6f * k, Rand(0.8f, 1.8f), -0.01f, 0.08f, Shade(fire, Rand(0.9f, 1.05f)));

					for (var i = 0; i < (int)(10 * k) + 4; i++)
						Add(PxParticleKind.Flame, 6 * k, height + Rand(0, 3 * k), Rand(0.5f, 0.9f) * k, 0.6f, Rand(16, 26), 1f,
							2.2f * k, Rand(0.2f, 0.7f), 0, 0.1f, fire);

					// Dark mushroom of soot above it
					for (var i = 0; i < (int)(14 * k * info.Smoke) + 4; i++)
						Add(PxParticleKind.Billow, 4 * k, height + Rand(8, 18) * k, Rand(0.7f, 1.1f) * k, 2.8f, Rand(90, 140), 0.85f,
							0.7f * k, Rand(0.6f, 1.1f), 0, 0.04f, Shade(grey, Rand(0.25f, 0.45f)));
					break;

				case PxExplosionStyle.Naval:
					Add(PxParticleKind.Glow, 0, height, 1.6f * k, 0.6f, 9, 1f, 0, 0, 0, 0, new float3(1f, 0.88f, 0.65f));
					for (var i = 0; i < (int)(10 * k) + 4; i++)
						Add(PxParticleKind.Fireball, 3 * k, height + Rand(2, 6 * k), Rand(0.6f, 1f) * k, 0.8f, Rand(18, 30), 1f,
							0.9f * k, Rand(0.6f, 1.3f), 0, 0.1f, fire);

					// Spray thrown up around the hull
					for (var i = 0; i < (int)(10 * k); i++)
						Add(PxParticleKind.Foam, 6 * k, 1, Rand(0.4f, 0.7f) * k, 1.4f, Rand(30, 50), 0.85f,
							1.4f * k, Rand(1.5f, 3f), 0.15f, 0.04f, white);

					for (var i = 0; i < (int)(12 * k) + 4; i++)
						Add(PxParticleKind.Spark, 2 * k, height + 3, Rand(0.3f, 0.6f), 0, Rand(12, 22), 1f,
							3.5f * k, Rand(1.5f, 3.5f), 0.15f, 0.04f, white);

					// Burning fuel: thick black smoke
					for (var i = 0; i < (int)(14 * k * info.Smoke) + 4; i++)
						Add(PxParticleKind.Plume, 3 * k, height + Rand(4, 14) * k, Rand(0.6f, 0.9f) * k, 2.6f, Rand(90, 140), 0.9f,
							0.35f * k, Rand(0.4f, 0.9f), 0, 0.03f, Shade(grey, Rand(0.15f, 0.3f)));
					break;

				case PxExplosionStyle.Bomblet:
					Add(PxParticleKind.Glow, 0, height, 0.9f * k, 0.4f, 4, 1f, 0, 0, 0, 0, new float3(1f, 0.92f, 0.75f));
					for (var i = 0; i < 3; i++)
						Add(PxParticleKind.Flame, 1.5f * k, height + Rand(0, 1.5f * k), Rand(0.4f, 0.6f) * k, 0.3f, Rand(6, 10), 1f,
							0.8f * k, Rand(0.2f, 0.6f), 0, 0.15f, fire);

					for (var i = 0; i < 6; i++)
						Add(PxParticleKind.Spark, 1 * k, height + 1, Rand(0.2f, 0.4f), 0, Rand(8, 14), 1f,
							3f * k, Rand(1f, 2.5f), 0.25f, 0.04f, white);

					for (var i = 0; i < (int)(3 * info.Smoke) + 1; i++)
						Add(PxParticleKind.Smoke, 2 * k, height + Rand(1, 3) * k, Rand(0.4f, 0.6f) * k, 1.8f, Rand(30, 50), 0.7f,
							0.3f * k, Rand(0.15f, 0.35f), 0, 0.03f, Shade(grey, Rand(0.55f, 0.75f)));
					break;

				default:
					// Flash and shock ring
					Add(PxParticleKind.Glow, 0, height, 1.4f * k, 0.6f, 8, 1f, 0, 0, 0, 0, new float3(1f, 0.9f, 0.7f));
					if (!air)
						Add(PxParticleKind.Ring, 0, 0, 0.9f * k, 1.6f, 16, 0.8f, 0, 0, 0, 0, white);

					// Rolling fireball: flames pushed outwards and up, shrinking as they burn out
					for (var i = 0; i < (int)(10 * k) + 4; i++)
						Add(PxParticleKind.Flame, 4 * k, height + Rand(0, 4 * k), Rand(0.5f, 0.9f) * k, 0.5f, Rand(12, 20), 1f,
							1.2f * k, Rand(0.3f, 1.2f), 0, 0.12f, fire);

					// Sparks and debris
					for (var i = 0; i < (int)(10 * k) + 4; i++)
						Add(PxParticleKind.Spark, 2 * k, height + 2, Rand(0.3f, 0.6f), 0, Rand(10, 18), 1f,
							3.5f * k, Rand(1f, 3f), air ? 0.05f : 0.2f, 0.04f, white);

					if (!air)
						for (var i = 0; i < (int)(6 * k); i++)
							Add(PxParticleKind.Chunk, 3 * k, 2, Rand(0.4f, 0.9f), 0, Rand(30, 50), 1f,
								2.2f * k, Rand(1.5f, 3.5f), 0.22f, 0.02f, new float3(0.55f, 0.5f, 0.45f));

					// Smoke: dark and dense at first, rising and spreading
					for (var i = 0; i < (int)(10 * k * info.Smoke) + 3; i++)
						Add(PxParticleKind.Smoke, 6 * k, height + Rand(2, 8) * k, Rand(0.5f, 0.8f) * k, 2.4f, Rand(55, 95), 0.85f,
							0.5f * k, Rand(0.25f, 0.6f), 0, 0.03f, Shade(grey, Rand(0.55f, 0.85f)));
					break;
			}
		}

		float Total => info.Style is PxExplosionStyle.Heavy or PxExplosionStyle.Thermobaric or PxExplosionStyle.Naval ? 220 : 160;

		public void Tick(World world)
		{
			if (time > Total)
				world.AddFrameEndTask(w => w.Remove(this));
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
				particles.Update(dt);
			}

			if (world.FogObscures(pos))
				yield break;

			if (info.Scorch && !air && scorch != null)
			{
				var alpha = Math.Clamp(time / 4f, 0, 1) * (1 - Math.Clamp((time - 100) / 60f, 0, 1)) * 0.8f;
				if (alpha > 0)
					yield return new SpriteRenderable(scorch.GetSprite(0), ground, WVec.Zero, ScorchZ, null,
						scorch.Scale * 0.45f * info.Size, alpha, new float3(1, 1, 1), TintModifiers.None, false);
			}

			foreach (var r in particles.Render(ground, 1024))
				yield return r;
		}
	}
}
