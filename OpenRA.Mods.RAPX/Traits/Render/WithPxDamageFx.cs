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

		public override object Create(ActorInitializer init) { return new WithPxDamageFx(init.Self, this); }
	}

	public class WithPxDamageFx : ConditionalTrait<WithPxDamageFxInfo>, ITickRender, IRender
	{
		const int ZBias = 640;

		readonly IHealth health;
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float[] timers;
		long lastTime = -1;

		public WithPxDamageFx(Actor self, WithPxDamageFxInfo info)
			: base(info)
		{
			health = self.Trait<IHealth>();
			particles = new PxParticles(self.World);
			timers = new float[info.Points.Length];
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

				if (heavy)
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
			return particles.Render(self.CenterPosition, ZBias);
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			var c = wr.ScreenPxPosition(self.CenterPosition);
			yield return new Rectangle(c.X - 160, c.Y - 260, 320, 380);
		}
	}
}
