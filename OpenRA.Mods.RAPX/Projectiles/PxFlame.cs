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
using OpenRA.Mods.Common;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Projectiles
{
	[Desc("High-definition flamethrower jet (cosmetic pxfx particles, the damage is the weapon's warheads): a white-hot",
		"core leaves the nozzle and throws rolling fireballs that expand, slow down, rise and turn into dark smoke.",
		"Fire one per tick in a Burst for a continuous stream.")]
	public class PxFlameInfo : IProjectileInfo
	{
		[Desc("Flight speed per tick.")]
		public readonly WDist Speed = new(170);

		[Desc("Maximum inaccuracy of the impact point (like Bullet).")]
		public readonly WDist Inaccuracy = WDist.Zero;

		[Desc("How the inaccuracy is applied (like Bullet).")]
		public readonly InaccuracyType InaccuracyType = InaccuracyType.Maximum;

		[Desc("Height of the flight arc, as a fraction of the distance.")]
		public readonly float Arc = 0.08f;

		[Desc("Fireballs thrown per tick of flight.")]
		public readonly int Density = 3;

		[Desc("Size of the fireballs at the nozzle; they grow to about three times this towards the target.")]
		public readonly float Size = 0.32f;

		[Desc("How long the fireballs burn, in ticks.")]
		public readonly int FireLife = 14;

		[Desc("How long the smoke they leave lingers, in ticks.")]
		public readonly int SmokeLife = 50;

		[Desc("Equivalent to sequence ZOffset. Controls Z sorting.")]
		public readonly int ZOffset = 1024;

		public IProjectile Create(ProjectileArgs args) { return new PxFlame(this, args); }
	}

	public class PxFlame : IProjectile, ISync
	{
		const float PixelPerWorld = 24f / 1024f;

		readonly PxFlameInfo info;
		readonly ProjectileArgs args;
		readonly WPos origin;
		readonly int flightTicks;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		PxParticles particles;
		int ticks;
		bool hit;
		int lingering;

		[Sync]
		readonly WPos target;

		[Sync]
		WPos pos;

		WPos lastPos;

		public PxFlame(PxFlameInfo info, ProjectileArgs args)
		{
			this.info = info;
			this.args = args;
			origin = args.Source;
			pos = lastPos = args.Source;
			var t = args.PassiveTarget;
			if (info.Inaccuracy.Length > 0)
			{
				var max = OpenRA.Mods.Common.Util.GetProjectileInaccuracy(info.Inaccuracy.Length, info.InaccuracyType, args);
				t += WVec.FromPDF(args.SourceActor.World.SharedRandom, 2) * max / 1024;
			}

			target = t;
			flightTicks = Math.Max(3, (target - origin).Length / Math.Max(1, info.Speed.Length));
		}

		float Rand(float min, float max) { return min + rng.NextFloat() * (max - min); }

		float3 Local(WPos p)
		{
			return new float3((p.X - origin.X) * PixelPerWorld, (p.Y - origin.Y) * PixelPerWorld, p.Z * PixelPerWorld);
		}

		void Emit(PxParticleKind kind, float3 at, float3 vel, float spread, float size, float grow, float life, float alpha,
			float3 tint, float drag)
		{
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = at.X + Rand(-0.5f, 0.5f) * spread,
				Y = at.Y + Rand(-0.5f, 0.5f) * spread * 0.6f,
				Z = at.Z + Rand(-0.3f, 0.3f) * spread,
				VX = vel.X + Rand(-0.25f, 0.25f),
				VY = vel.Y + Rand(-0.15f, 0.15f),
				VZ = vel.Z,
				Drag = drag,
				Life = life * Rand(0.75f, 1.25f),
				Size = size * Rand(0.8f, 1.2f),
				Grow = grow,
				Alpha = alpha,
				Tint = tint,
				Frame = rng.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = Rand(-4, 4),
				Angle = rng.Next(1024),
			});
		}

		public void Tick(World world)
		{
			particles ??= new PxParticles(world) { Max = 160 };
			particles.Update(1);

			if (hit)
			{
				if (--lingering <= 0 || particles.Items.Count == 0)
					world.AddFrameEndTask(w => w.Remove(this));

				return;
			}

			ticks++;
			var u = Math.Min(1f, (float)ticks / flightTicks);
			var dist = (target - origin).Length;
			lastPos = pos;
			pos = WPos.Lerp(origin, target, (int)(u * 1024), 1024) + new WVec(0, 0, (int)(Math.Sin(u * Math.PI) * dist * info.Arc));

			var here = Local(pos);
			var back = Local(lastPos);
			var dir = new float3(here.X - back.X, here.Y - back.Y, here.Z - back.Z);
			var hot = new float3(1f, 0.95f, 0.85f);

			if (ticks == 1)
				Emit(PxParticleKind.Glow, back, float3.Zero, 1, info.Size * 2.2f, 0.3f, 4, 0.9f, new float3(1f, 0.7f, 0.35f), 0);

			for (var i = 0; i < info.Density; i++)
			{
				var f = (i + 1f) / info.Density;
				var at = new float3(back.X + dir.X * f, back.Y + dir.Y * f, back.Z + dir.Z * f);

				// Fireballs keep some of the jet's speed, slow down in the air and rise as hot gas
				var vel = new float3(dir.X * 0.35f, dir.Y * 0.35f, 0.25f + u * 0.25f);
				var size = info.Size * (0.7f + u * 1.6f);
				Emit(PxParticleKind.Fireball, at, vel, 2 + u * 6, size, 1.1f, info.FireLife, 1f, hot, 0.14f);
			}

			// The white-hot core of the jet and a glow on the ground under it
			Emit(PxParticleKind.Glow, here, float3.Zero, 1, info.Size * (1.2f + u), 0.2f, 3, 0.6f, new float3(1f, 0.75f, 0.4f), 0);

			// Smoke builds up where the flames burn out, rising and drifting
			if (ticks % 2 == 0)
				Emit(PxParticleKind.Billow, back, new float3(dir.X * 0.1f, dir.Y * 0.1f, 0.35f), 6 + u * 6,
					info.Size * (1.1f + u * 1.4f), 1.8f, info.SmokeLife, 0.55f, new float3(0.3f, 0.29f, 0.28f), 0.05f);

			if (u >= 1)
			{
				args.Weapon.Impact(Target.FromPos(target), new WarheadArgs(args) { ImpactPosition = target });
				hit = true;
				lingering = info.SmokeLife * 2;
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			if (particles == null || wr.World.FogObscures(pos))
				yield break;

			foreach (var r in particles.Render(new WPos(origin.X, origin.Y, 0), info.ZOffset))
				yield return r;
		}
	}
}
