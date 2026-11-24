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
using OpenRA.Primitives;
using OpenRA.Graphics;
using OpenRA.Effects;
using OpenRA.Mods.Common.Warheads;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Warheads
{
	[Desc("High-definition fire impact (pxfx particles, cosmetic only): a burst of rolling fireballs and embers, then the",
		"ground keeps burning for a while with flickering flames and a column of dark smoke. Plays ImpactSounds like",
		"CreateEffect. Does nothing on open water.")]
	public class PxFireWarhead : Warhead
	{
		[Desc("Overall size: 0.5 = a flamethrower splash, 1 = a flame tower fireball, 2 = napalm.")]
		public readonly float Size = 1f;

		[Desc("How long the ground keeps burning, in ticks.")]
		public readonly int Duration = 60;

		[Desc("Amount of smoke, as a multiple of the default.")]
		public readonly float Smoke = 1f;

		[Desc("Colour of the smoke (white phosphorus burns with thick white smoke).")]
		public readonly Color SmokeColor = Color.FromArgb(255, 71, 69, 66);

		[Desc("Leave a short-lived scorch mark on the ground.")]
		public readonly bool Scorch = true;

		[Desc("Sounds to play on impact.")]
		public readonly string[] ImpactSounds = Array.Empty<string>();

		[Desc("Filmed impacts (sequences of image pxvideofx, artsrc/fx/make_video_fx.py), one picked at random and played",
			"once in place of the particle fireballs and flames.")]
		public readonly string[] Video = Array.Empty<string>();

		[Desc("Filmed fire loops (one picked at random) that take over from Video and burn for the rest of Duration.")]
		public readonly string[] BurnVideo = Array.Empty<string>();

		[Desc("Filmed clip of the fire burning out, played when Duration is over (its first frame matches the loop's).")]
		public readonly string BurnVideoEnd = null;

		[Desc("Size of the filmed fire, as a multiple of Size.")]
		public readonly float VideoScale = 1f;

		public override void DoImpact(in Target target, WarheadArgs args)
		{
			if (target.Type == TargetType.Invalid)
				return;

			var world = args.SourceActor.World;
			var pos = target.CenterPosition;
			var cell = world.Map.CellContaining(pos);
			if (!world.Map.Contains(cell) || world.Map.GetTerrainInfo(cell).TargetTypes.Contains("Water"))
				return;

			world.AddFrameEndTask(w => w.Add(new PxFireEffect(w, pos, this)));

			var sound = ImpactSounds.RandomOrDefault(world.LocalRandom);
			if (sound != null)
				Game.Sound.Play(SoundType.World, sound, pos);
		}
	}

	public class PxFireEffect : IEffect
	{
		const int ScorchZ = -2048;

		/// <summary>Ticks over which the impact clip dissolves into the fire loop.</summary>
		const float Handover = 10;

		readonly World world;
		readonly WPos ground;
		readonly PxFireWarhead info;
		readonly PxParticles particles;
		readonly ISpriteSequence scorch;
		readonly ISpriteSequence clip;
		readonly PxClipCycle burn;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		float time;
		float emit;
		long lastTime = -1;
		bool started;

		public PxFireEffect(World world, WPos pos, PxFireWarhead info)
		{
			this.world = world;
			this.info = info;
			ground = pos - new WVec(0, 0, world.Map.DistanceAboveTerrain(pos).Length);
			particles = new PxParticles(world) { Max = 220 };
			scorch = particles.Sequence("scorch");
			clip = PxVideoEffect.Pick(world, info.Video, random);
			burn = PxClipCycle.Create(world, null, info.BurnVideo, info.BurnVideoEnd, random);
		}

		/// <summary>Ticks until the filmed impact's last frame (40 ms game ticks).</summary>
		float ClipEnd => clip == null ? 0 : PxVideoEffect.Duration(clip);

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		void Add(PxParticleKind kind, float spread, float z, float size, float grow, float life, float alpha,
			float speed, float vz, float drag, float3 tint)
		{
			var a = Rand(0, MathF.PI * 2);
			var r = Rand(0, spread);
			var s = Rand(0.3f, 1f) * speed;
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = MathF.Cos(a) * r,
				Y = MathF.Sin(a) * r * 0.6f,
				Z = z,
				VX = MathF.Cos(a) * s,
				VY = MathF.Sin(a) * s * 0.6f,
				VZ = vz,
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

		void Start()
		{
			started = true;
			var k = info.Size;
			var hot = new float3(1f, 0.95f, 0.85f);

			Add(PxParticleKind.Glow, 0, 2 * k, 1.6f * k, 0.5f, 7, 1f, 0, 0, 0, new float3(1f, 0.7f, 0.35f));

			// Burst: fireballs roll outwards and up (the filmed impact has its own)
			for (var i = 0; i < (clip != null ? 0 : (int)(8 * k) + 3); i++)
				Add(PxParticleKind.Fireball, 3 * k, Rand(0, 3) * k, Rand(0.45f, 0.75f) * k, 1.1f, Rand(12, 20), 1f,
					1.1f * k, Rand(0.3f, 0.9f), 0.12f, hot);

			// Embers thrown up
			for (var i = 0; i < (int)(6 * k) + 2; i++)
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Spark,
					X = Rand(-2, 2) * k,
					Y = Rand(-1, 1) * k,
					Z = 2,
					VX = Rand(-1.5f, 1.5f) * k,
					VY = Rand(-0.8f, 0.8f) * k,
					VZ = Rand(1.2f, 2.6f),
					Gravity = 0.08f,
					Drag = 0.03f,
					Life = Rand(14, 26),
					Size = Rand(0.18f, 0.3f),
					Alpha = 1f,
					Tint = new float3(1f, 0.7f, 0.3f),
				});
		}

		float Total => Math.Max(info.Duration + 90, ClipEnd + 2);

		public void Tick(World world)
		{
			if (time > Total && (burn == null || !burn.Active))
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
				var k = info.Size;

				// The ground keeps burning: flickering tongues and rising smoke, dying down towards the end
				if (time < info.Duration)
				{
					var left = 1 - time / info.Duration;
					emit += dt;
					while (emit >= 1)
					{
						emit -= 1;
						if (clip == null && burn == null)
							Add(PxParticleKind.Flame, 3.5f * k, 0, Rand(0.35f, 0.6f) * k * (0.5f + 0.5f * left), 0.2f, Rand(10, 16),
							0.95f, 0.05f, Rand(0.35f, 0.7f), 0.1f, new float3(1f, 0.85f, 0.6f));
						if (clip == null && burn == null && random.NextFloat() < 0.5f * left + 0.15f)
							Add(PxParticleKind.Fireball, 2.5f * k, Rand(0, 2), Rand(0.25f, 0.4f) * k * (0.5f + 0.5f * left), 0.6f,
								Rand(8, 12), 0.9f, 0.05f, Rand(0.4f, 0.8f), 0.1f, new float3(1f, 0.95f, 0.85f));
						if (random.NextFloat() < 0.35f * info.Smoke)
							Add(PxParticleKind.Billow, 3 * k, Rand(4, 8) * k, Rand(0.4f, 0.6f) * k, 2.2f, Rand(50, 80), 0.6f,
								0.12f, Rand(0.3f, 0.55f), 0.03f, new float3(info.SmokeColor.R / 255f, info.SmokeColor.G / 255f, info.SmokeColor.B / 255f));
					}
				}

				particles.Update(dt);
				if (burn != null)
				{
					// The fire takes over as the impact clip ends, burns for Duration, then burns out on camera
					if (time >= ClipEnd - Handover && time < info.Duration && !burn.Burning && !burn.Active)
						burn.Ignite(false);
					if (time >= Math.Max(info.Duration, ClipEnd) && burn.Burning)
						burn.Extinguish();
					burn.Update(dt);
				}
			}

			if (world.FogObscures(ground))
				yield break;

			if (info.Scorch && scorch != null)
			{
				var alpha = Math.Clamp(time / 4f, 0, 1) * (1 - Math.Clamp((time - info.Duration - 30) / 60f, 0, 1)) * 0.75f;
				if (alpha > 0)
					yield return new SpriteRenderable(scorch.GetSprite(0), ground, WVec.Zero, ScorchZ, null,
						scorch.Scale * 0.32f * info.Size, alpha, new float3(1, 1, 1), TintModifiers.None, false);
			}

			var white = new float3(1, 1, 1);
			var k2 = info.Size * info.VideoScale;
			if (burn != null)
				foreach (var r in burn.Render(ground, 510, k2 * 0.8f, 1f, white))
					yield return r;

			// The impact clip plays to its end; with a fire to hand over to, its last moments dissolve into the fire
			if (clip != null && time <= ClipEnd + 1)
			{
				var alpha = burn != null ? 1 - Math.Clamp((time - (ClipEnd - Handover)) / Handover, 0, 1) : 1;
				foreach (var r in PxVideoEffect.Draw(clip, time * 40 / clip.Tick, ground, 512, clip.Scale * k2, alpha, white))
					yield return r;
			}

			foreach (var r in particles.Render(ground, 1024))
				yield return r;
		}
	}
}
