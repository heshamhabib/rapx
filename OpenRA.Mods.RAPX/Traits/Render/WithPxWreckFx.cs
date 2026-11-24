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
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("One style for every destroyed vehicle: an HD fire (filmed or drawn flame loop) on the hull, a flickering glow on",
		"the ground, embers and a thick smoke plume drifting with the weather wind (steam in the rain). The fire follows",
		"the wreck's health: full blaze when it is fresh, fewer and smaller flames as it burns down, smouldering smoke at",
		"the end. Sprites: `pxfx` wfire / wsmoke (artsrc/fx/make_wreck_fx.py). Purely cosmetic.")]
	public class WithPxWreckFxInfo : TraitInfo, Requires<IHealthInfo>
	{
		[Desc("Fire spots on the hull, screen pixels relative to the centre (up is negative). The first burns longest.")]
		public readonly int2[] Spots = { new(0, -4), new(-8, 2), new(7, 3) };

		[Desc("Size multiplier for the flames and smoke (bigger wrecks burn bigger).")]
		public readonly float Size = 1f;

		[Desc("Filmed fire loop (sequence of image pxvideofx, artsrc/fx/make_video_fx.py) drawn instead of the `wfire`",
			"animation. Empty or missing = `wfire`.")]
		public readonly string Video = "fire-wreck-a";

		[Desc("Size of the filmed fire, as a multiple of Size.")]
		public readonly float VideoScale = 0.7f;

		public override object Create(ActorInitializer init) { return new WithPxWreckFx(init.Self, this); }
	}

	public class WithPxWreckFx : ITickRender, IRender, INotifyAddedToWorld
	{
		const int ZBias = 640;
		const string FireSequence = "wfire";

		readonly WithPxWreckFxInfo info;
		readonly IHealth health;
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float[] smokeTimers;
		readonly int[] phases;
		readonly ISpriteSequence fire, glow;
		readonly bool video;
		PxWeatherManager weather;
		bool weatherResolved, burst;
		long lastTime = -1;

		public WithPxWreckFx(Actor self, WithPxWreckFxInfo info)
		{
			this.info = info;
			health = self.Trait<IHealth>();
			particles = new PxParticles(self.World);
			var clip = PxVideoEffect.Find(self.World, info.Video);
			video = clip != null;
			fire = clip ?? particles.Sequence(FireSequence);
			glow = particles.Sequence("glow");
			smokeTimers = new float[info.Spots.Length];
			phases = new int[info.Spots.Length];
			for (var i = 0; i < phases.Length; i++)
				phases[i] = random.Next(fire.Length);
		}

		void INotifyAddedToWorld.AddedToWorld(Actor self) { burst = true; }

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		static float Smooth(float a, float b, float x)
		{
			var t = Math.Clamp((x - a) / (b - a), 0, 1);
			return t * t * (3 - 2 * t);
		}

		/// <summary>0 = burnt out, 1 = fresh wreck in full blaze.</summary>
		float Strength => Smooth(0.08f, 0.55f, (float)health.HP / health.MaxHP);

		/// <summary>How much of the fire one spot carries: the first spot burns longest.</summary>
		static float SpotStrength(int i, float s) => Math.Clamp((s - i * 0.28f) / (1 - i * 0.28f), 0, 1);

		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)self.World.Timestep;
			lastTime = now;
			if (self.World.Paused || dt <= 0)
				return;

			particles.Update(dt);

			if (!weatherResolved)
			{
				var manager = self.World.WorldActor.TraitOrDefault<PxWeatherManager>();
				weather = manager != null && manager.Enabled ? manager : null;
				weatherResolved = true;
			}

			// Wind pushes the smoke (screen pixels per tick); rain turns it into steam
			var drift = new float2(0.1f, -0.02f);
			var wet = 0f;
			if (weather != null)
			{
				var f = weather.Frame();
				drift = f.WindDir * (0.06f + 0.55f * f.Wind);
				wet = Math.Max(f.Rain, f.Snow * 0.5f);
			}

			if (burst)
			{
				burst = false;
				Burst(drift);
			}

			var s = Strength;
			for (var i = 0; i < info.Spots.Length; i++)
			{
				var spot = info.Spots[i];
				var k = SpotStrength(i, s);
				var smoulder = i == 0 && (float)health.HP / health.MaxHP > 0.01f;
				if (k <= 0 && !smoulder)
					continue;

				smokeTimers[i] -= dt;
				if (smokeTimers[i] <= 0)
				{
					smokeTimers[i] = k > 0 ? Rand(3.5f, 5.5f) / (0.4f + 0.6f * k) : Rand(9, 14);
					var grey = k > 0 ? Rand(0.07f, 0.16f) : Rand(0.32f, 0.45f);
					var steam = wet * Rand(0.4f, 0.8f);
					grey += (0.85f - grey) * steam;
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Plume,
						X = spot.X + Rand(-2, 2),
						Y = spot.Y + Rand(-1, 1),
						Z = info.Size * (6 + 8 * k),
						VX = drift.X * Rand(0.7f, 1.3f),
						VY = drift.Y * Rand(0.7f, 1.3f),
						VZ = Rand(0.42f, 0.62f) * (0.6f + 0.4f * k),
						Drag = 0.004f,
						Life = Rand(120, 175),
						Size = info.Size * Rand(0.18f, 0.26f) * (0.6f + 0.4f * Math.Max(k, 0.3f)),
						Grow = Rand(4f, 5.5f),
						Alpha = k > 0 ? Rand(0.75f, 0.92f) : Rand(0.4f, 0.55f),
						Tint = new float3(grey, grey * 0.97f, grey * 0.93f),
						Frame = random.Next(particles.FrameCount(PxParticleKind.Plume)),
						Angle = random.Next(1024),
						Spin = Rand(-2.5f, 2.5f),
					});
				}

				// Embers spiralling up out of the flames
				if (k > 0 && random.NextFloat() < 0.12f * k * dt)
				{
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Spark,
						X = spot.X + Rand(-3, 3),
						Y = spot.Y + Rand(-1, 1),
						Z = info.Size * Rand(4, 10),
						VX = drift.X * 2 + Rand(-0.25f, 0.25f),
						VY = drift.Y * 2 + Rand(-0.1f, 0.1f),
						VZ = Rand(0.7f, 1.4f),
						Drag = 0.02f,
						Life = Rand(18, 36),
						Size = Rand(0.18f, 0.32f),
						Alpha = 1,
						Tint = new float3(1, Rand(0.45f, 0.7f), 0.2f),
					});
				}
			}
		}

		/// <summary>The moment of destruction: a flash, a shower of sparks and a burst of black smoke.</summary>
		void Burst(float2 drift)
		{
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Glow,
				Z = 4,
				Life = 14,
				Size = info.Size * 3.2f,
				Alpha = 0.9f,
				Tint = new float3(1, 0.62f, 0.25f),
			});

			for (var i = 0; i < 14; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				var v = Rand(0.8f, 2.4f);
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Spark,
					Z = Rand(3, 8),
					VX = MathF.Cos(a) * v,
					VY = MathF.Sin(a) * v * 0.5f,
					VZ = Rand(1.2f, 2.6f),
					Gravity = 0.09f,
					Life = Rand(16, 30),
					Size = Rand(0.25f, 0.45f),
					Alpha = 1,
					Tint = new float3(1, Rand(0.55f, 0.85f), 0.3f),
				});
			}

			for (var i = 0; i < 6; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				var grey = Rand(0.06f, 0.14f);
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Plume,
					X = MathF.Cos(a) * Rand(2, 7),
					Y = MathF.Sin(a) * Rand(1, 4),
					Z = Rand(3, 9),
					VX = MathF.Cos(a) * Rand(0.2f, 0.5f) + drift.X,
					VY = MathF.Sin(a) * Rand(0.1f, 0.25f) + drift.Y,
					VZ = Rand(0.5f, 0.9f),
					Drag = 0.015f,
					Life = Rand(80, 130),
					Size = info.Size * Rand(0.28f, 0.4f),
					Grow = Rand(3, 4),
					Alpha = 0.9f,
					Tint = new float3(grey, grey, grey * 0.95f),
					Frame = random.Next(particles.FrameCount(PxParticleKind.Plume)),
					Angle = random.Next(1024),
					Spin = Rand(-3, 3),
				});
			}
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			var origin = self.CenterPosition;
			var now = Game.RunTime;
			var s = Strength;

			for (var i = 0; i < info.Spots.Length; i++)
			{
				var k = SpotStrength(i, s);
				if (k <= 0)
					continue;

				var spot = info.Spots[i];

				// Flickering firelight on the ground and the hull (additive, under the wreck)
				var flicker = 0.75f + 0.25f * MathF.Sin(now * 0.021f + i * 2.1f) * MathF.Sin(now * 0.013f + i);
				var glowSize = info.Size * (1.1f + 0.9f * k) * (0.95f + 0.05f * flicker);
				yield return new SpriteRenderable(glow.GetSprite(0), origin + PxParticles.ToWorld(spot.X, spot.Y + 3),
					WVec.Zero, -48, null, glow.Scale * glowSize, 0.42f * k * flicker, new float3(1, 0.5f, 0.16f),
					TintModifiers.None, false, WAngle.Zero);

				// The flame: a looping HD animation, its base pinned to the hull (a filmed loop has its origin at the foot
				// of the flames already)
				var frame = (int)(now / (video ? fire.Tick : 42) + phases[i]) % fire.Length;
				var sprite = fire.GetSprite(frame);
				var scale = video
					? fire.Scale * info.Size * info.VideoScale * (0.45f + 0.55f * k) * (i == 0 ? 1f : 0.7f)
					: fire.Scale * info.Size * (0.3f + 0.4f * k) * (i == 0 ? 1f : 0.75f) * (0.96f + 0.04f * flicker);
				var lift = video ? 0 : sprite.Size.Y * scale * 0.4f;
				var offset = PxParticles.ToWorld(spot.X, spot.Y - lift);
				yield return new SpriteRenderable(sprite, origin + offset, WVec.Zero, ZBias - offset.Y, null, scale,
					1f, new float3(1, 1, 1), TintModifiers.None, false, WAngle.Zero);
			}

			foreach (var r in particles.Render(origin, ZBias + 64))
				yield return r;
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			var c = wr.ScreenPxPosition(self.CenterPosition);
			yield return new Rectangle(c.X - 220, c.Y - 340, 440, 420);
		}
	}
}
