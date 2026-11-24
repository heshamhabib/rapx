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
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Damaged HD buildings smoke and burn: light smoke when damaged, black smoke and flames when",
		"heavily damaged, more fires at critical health.")]
	public class WithPxDamageFxInfo : ConditionalTraitInfo, Requires<IHealthInfo>
	{
		[FieldLoader.Require]
		[Desc("Spots on the building (screen pixels relative to its centre) where fires can start. The first burns first.")]
		public readonly int2[] Points = Array.Empty<int2>();

		[Desc("Size multiplier for smoke and flames.")]
		public readonly float Size = 1f;

		[Desc("Filmed fire loops (sequences of image pxvideofx, artsrc/fx/make_video_fx.py, one picked per spot) burning on",
			"each fire spot when heavily damaged, instead of flame particles. Empty or missing = particles.")]
		public readonly string[] Video = { "fire-small-loop-1", "fire-small-loop-2" };

		[Desc("The fire catching (its last frame matches the loops' first).")]
		public readonly string VideoStart = "fire-small-start";

		[Desc("The fire burning out when the building is repaired (its first frame matches the loops' first).")]
		public readonly string VideoEnd = "fire-small-end";

		[Desc("Filmed fire for the first spot at critical health: loops, start and end.")]
		public readonly string[] CriticalVideo = { "fire-big-loop-1" };

		public readonly string CriticalVideoStart = "fire-big-start";

		public readonly string CriticalVideoEnd = "fire-big-end";

		[Desc("Size of the filmed fires, as a multiple of Size.")]
		public readonly float VideoScale = 0.65f;

		public override object Create(ActorInitializer init) { return new WithPxDamageFx(init.Self, this); }
	}

	public class WithPxDamageFx : ConditionalTrait<WithPxDamageFxInfo>, ITickRender, IRender
	{
		const int ZBias = 640;

		readonly IHealth health;
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float[] timers;
		readonly World world;
		readonly bool video;

		// Filmed fires: what each spot burns with (0 none, 1 small, 2 big) and its fire; fires going out keep playing
		// their end until they are done
		readonly int[] kinds;
		readonly PxClipCycle[] fires;
		readonly List<(int Spot, PxClipCycle Fire)> dying = new();
		long lastTime = -1;

		public WithPxDamageFx(Actor self, WithPxDamageFxInfo info)
			: base(info)
		{
			health = self.Trait<IHealth>();
			particles = new PxParticles(self.World);
			timers = new float[info.Points.Length];
			world = self.World;
			kinds = new int[info.Points.Length];
			fires = new PxClipCycle[info.Points.Length];
			video = PxVideoEffect.Pick(world, info.Video, random) != null;
		}

		PxClipCycle Fire(int kind)
		{
			return kind == 2
				? PxClipCycle.Create(world, Info.CriticalVideoStart, Info.CriticalVideo, Info.CriticalVideoEnd, random)
				: PxClipCycle.Create(world, Info.VideoStart, Info.Video, Info.VideoEnd, random);
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)self.World.Timestep;
			lastTime = now;
			if (self.World.Paused || dt <= 0)
				return;

			particles.Update(dt);
			if (IsTraitDisabled)
				return;

			// How many spots burn, and how hard
			var state = health.DamageState;
			var spots = state switch
			{
				DamageState.Medium => 1,
				DamageState.Heavy => Math.Min(2, Info.Points.Length),
				DamageState.Critical => Info.Points.Length,
				_ => 0,
			};

			// Filmed fires catch when the building is heavily damaged (the first spot grows into a big fire at critical
			// health) and burn out on camera when it is repaired
			if (video)
			{
				var burning = state >= DamageState.Heavy ? spots : 0;
				for (var i = 0; i < kinds.Length; i++)
				{
					var want = i >= burning ? 0 : i == 0 && state == DamageState.Critical ? 2 : 1;
					if (want == kinds[i])
						continue;

					if (fires[i] != null)
					{
						fires[i].Extinguish();
						dying.Add((i, fires[i]));
					}

					kinds[i] = want;
					fires[i] = want > 0 ? Fire(want) : null;
					fires[i]?.Ignite();
				}

				foreach (var f in fires)
					f?.Update(dt);
				foreach (var d in dying)
					d.Fire.Update(dt);
				dying.RemoveAll(d => d.Fire.Done);
			}

			for (var i = 0; i < spots; i++)
			{
				timers[i] -= dt;
				if (timers[i] > 0)
					continue;

				var heavy = state >= DamageState.Heavy;
				timers[i] = heavy ? Rand(2.5f, 4.5f) : Rand(6, 10);
				var p = Info.Points[i];
				var grey = heavy ? Rand(0.12f, 0.22f) : Rand(0.45f, 0.6f);
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Smoke,
					X = p.X + Rand(-2, 2),
					Y = p.Y + Rand(-1, 1),
					Z = heavy ? 4 : 0,
					VX = Rand(0.08f, 0.22f),
					VZ = Rand(0.4f, 0.65f),
					Drag = 0.008f,
					Life = Rand(70, 110),
					Size = Info.Size * Rand(0.35f, 0.5f),
					Grow = heavy ? 2.8f : 2f,
					Alpha = heavy ? 0.85f : 0.55f,
					Tint = new float3(grey, grey * 0.97f, grey * 0.94f),
					Frame = random.Next(particles.FrameCount(PxParticleKind.Smoke)),
					Angle = random.Next(1024),
					Spin = Rand(-3, 3),
				});

				if (heavy && !video)
				{
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Flame,
						X = p.X + Rand(-2, 2),
						Y = p.Y + Rand(-1, 1),
						Z = Info.Size * 7,
						VZ = Rand(0.05f, 0.15f),
						Life = Rand(12, 20),
						Size = Info.Size * Rand(0.45f, 0.7f),
						Grow = -0.3f,
						Alpha = 1,
						Tint = new float3(1, 1, 1),
						Frame = random.Next(particles.FrameCount(PxParticleKind.Flame)),
					});
				}

				if (heavy)
				{
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Glow,
						X = p.X,
						Y = p.Y,
						Z = 3,
						Life = Rand(5, 9),
						Size = Info.Size * Rand(1.2f, 1.8f),
						Alpha = 0.35f,
						Tint = new float3(1, 0.5f, 0.15f),
					});
				}
			}
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			var origin = self.CenterPosition;
			var white = new float3(1, 1, 1);
			IEnumerable<IRenderable> Draw(int i, PxClipCycle fire)
			{
				var offset = PxParticles.ToWorld(Info.Points[i].X, Info.Points[i].Y);
				return fire.Render(origin + offset, ZBias - offset.Y, Info.Size * Info.VideoScale * (i == 0 ? 1f : 0.8f), 1f, white);
			}

			for (var i = 0; i < fires.Length; i++)
				if (fires[i] != null)
					foreach (var r in Draw(i, fires[i]))
						yield return r;

			foreach (var d in dying)
				foreach (var r in Draw(d.Spot, d.Fire))
					yield return r;

			foreach (var r in particles.Render(origin, ZBias))
				yield return r;
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			var c = wr.ScreenPxPosition(self.CenterPosition);
			yield return new Rectangle(c.X - 160, c.Y - 260, 320, 380);
		}
	}
}
