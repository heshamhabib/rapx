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
using OpenRA.Effects;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Support;

namespace OpenRA.Mods.RAPX.Effects
{
	/// <summary>
	/// One salvo of countermeasure flares (PxFlareDispenser), purely cosmetic: the jet drops them one after another,
	/// alternating left and right, so they fan out behind it like wings. Each flare is a flickering white-hot core in an
	/// orange glow that sheds sparks and leaves a curling smoke streak while it falls and burns out.
	/// </summary>
	public class PxFlareBurst : IEffect
	{
		const float PixelPerWorld = 24f / 1024f;
		const float Gravity = 1.6f;
		const float Drag = 0.93f;
		const int ReleaseInterval = 1;
		const int ZBias = 1536;
		const int AverageLift = 24;

		sealed class Flare
		{
			public float X, Y, Z;
			public float VX, VY, VZ;
			public int Age, Life;
			public bool Released, Out;
		}

		readonly Actor jet;
		readonly WPos anchor;
		readonly List<Flare> flares = new();
		readonly PxParticles particles;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		float forwardX, forwardY;
		WVec jetVelocity;
		WPos jetLast;
		int ticks;

		public PxFlareBurst(Actor jet, WVec velocity, int count)
		{
			this.jet = jet;
			jetLast = jet.CenterPosition;
			jetVelocity = velocity;
			anchor = new WPos(jetLast.X, jetLast.Y, 0);
			particles = new PxParticles(jet.World) { Max = 2400 };
			SetForward(velocity);
			for (var i = 0; i < count; i++)
				flares.Add(new Flare { Life = 48 + rng.Next(24) });
		}

		void SetForward(WVec v)
		{
			var len = MathF.Sqrt((float)v.X * v.X + (float)v.Y * v.Y);
			if (len > 1)
			{
				forwardX = v.X / len;
				forwardY = v.Y / len;
			}
			else if (forwardX == 0 && forwardY == 0)
				forwardY = -1;
		}

		float Rand(float lo, float hi) { return lo + (hi - lo) * rng.NextFloat(); }

		/// <summary>Where the middle of a salvo is t ticks after release, relative to the release point (same flight
		/// model as the flares, average kick): used to aim the missiles the flares fool.</summary>
		public static WVec Drift(WVec jetVelocity, int t)
		{
			// Integer steps (fixed point x1024): the result aims synced missiles, so no float maths here
			long vx = jetVelocity.X * 512L, vy = jetVelocity.Y * 512L, vz = (long)AverageLift * 1024;
			long x = 0, y = 0, z = 0;
			for (var i = 0; i < t; i++)
			{
				vx = vx * 93 / 100;
				vy = vy * 93 / 100;
				vz = vz * 93 / 100 - (long)(Gravity * 1024);
				x += vx;
				y += vy;
				z += vz;
			}

			return new WVec((int)(x / 1024), (int)(y / 1024), (int)(z / 1024));
		}

		public void Tick(World world)
		{
			// The jet keeps flying: new flares leave from where it is now
			if (jet.IsInWorld)
			{
				var now = jet.CenterPosition;
				jetVelocity = now - jetLast;
				jetLast = now;
				SetForward(jetVelocity);
			}

			var burning = false;
			for (var i = 0; i < flares.Count; i++)
			{
				var f = flares[i];
				if (!f.Released)
				{
					if (ticks >= i * ReleaseInterval)
						Release(f, i % 2 == 0 ? 1 : -1);
					else
					{
						burning = true;
						continue;
					}
				}

				if (f.Out)
					continue;

				burning = true;
				f.VX *= Drag;
				f.VY *= Drag;
				f.VZ = f.VZ * Drag - Gravity;
				f.X += f.VX;
				f.Y += f.VY;
				f.Z += f.VZ;
				if (++f.Age >= f.Life || f.Z <= 0)
				{
					f.Out = true;
					continue;
				}

				Emit(f);
			}

			particles.Update(1);
			ticks++;
			if (!burning && particles.Items.Count == 0)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		void Release(Flare f, int side)
		{
			f.Released = true;
			f.X = jetLast.X;
			f.Y = jetLast.Y;
			f.Z = jetLast.Z;

			// Kicked out sideways and a little back and up, keeping part of the jet's speed
			var rightX = -forwardY;
			var rightY = forwardX;
			var sideways = side * Rand(38, 78);
			var back = -Rand(8, 30);
			f.VX = jetVelocity.X * 0.5f + rightX * sideways + forwardX * back;
			f.VY = jetVelocity.Y * 0.5f + rightY * sideways + forwardY * back;
			f.VZ = Rand(14, 34);

			// Ignition flash
			var at = Local(f);
			Add(PxParticleKind.Glow, at, 1.7f, 4, 0.9f, new float3(1f, 0.92f, 0.75f));
			for (var i = 0; i < 4; i++)
				Spark(at, 1.6f);
		}

		void Emit(Flare f)
		{
			var at = Local(f);
			var t = (float)f.Age / f.Life;
			var heat = t < 0.8f ? 1f : (1 - t) / 0.2f;

			// Flickering magnesium core inside a soft orange glow
			Add(PxParticleKind.Glow, at, Rand(0.26f, 0.42f) * (0.5f + 0.5f * heat), 1.6f, 1f, new float3(1f, 0.97f, 0.88f));
			Add(PxParticleKind.Glow, at, Rand(0.9f, 1.3f) * heat, 1.6f, 0.42f * heat, new float3(1f, 0.58f, 0.22f));

			// Thick white smoke streak, slowly spreading and drifting
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Smoke,
				X = at.X + Rand(-0.4f, 0.4f),
				Y = at.Y + Rand(-0.3f, 0.3f),
				Z = at.Z,
				VX = Rand(-0.03f, 0.03f),
				VY = Rand(-0.02f, 0.02f),
				VZ = Rand(0, 0.025f),
				Drag = 0.04f,
				Life = Rand(70, 95),
				Size = Rand(0.16f, 0.22f),
				Grow = 3.2f,
				Alpha = 0.55f * (0.4f + 0.6f * heat),
				Tint = new float3(0.92f, 0.9f, 0.86f),
				Frame = rng.Next(Math.Max(1, particles.FrameCount(PxParticleKind.Smoke))),
				Spin = Rand(-1.5f, 1.5f),
				Angle = rng.Next(1024),
			});

			if (rng.NextFloat() < 0.45f * heat)
				Spark(at, 0.6f);
		}

		void Spark(float3 at, float speed)
		{
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Spark,
				X = at.X,
				Y = at.Y,
				Z = at.Z,
				VX = Rand(-speed, speed),
				VY = Rand(-speed, speed) * 0.6f,
				VZ = Rand(-0.2f, speed),
				Gravity = 0.06f,
				Drag = 0.08f,
				Life = Rand(5, 11),
				Size = Rand(0.12f, 0.2f),
				Alpha = 1f,
				Tint = new float3(1f, 0.82f, 0.45f),
				Frame = rng.Next(Math.Max(1, particles.FrameCount(PxParticleKind.Spark))),
				Angle = rng.Next(1024),
			});
		}

		void Add(PxParticleKind kind, float3 at, float size, float life, float alpha, float3 tint)
		{
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = at.X,
				Y = at.Y,
				Z = at.Z,
				Life = life,
				Size = size,
				Alpha = alpha,
				Tint = tint,
				Frame = rng.Next(Math.Max(1, particles.FrameCount(kind))),
				Angle = rng.Next(1024),
			});
		}

		float3 Local(Flare f)
		{
			return new float3((f.X - anchor.X) * PixelPerWorld, (f.Y - anchor.Y) * PixelPerWorld, f.Z * PixelPerWorld);
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			return particles.Render(anchor, ZBias, p => wr.World.FogObscures(p));
		}
	}
}
