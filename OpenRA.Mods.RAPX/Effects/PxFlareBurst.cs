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
	/// <summary>Standard: a quick salvo fanning out behind the jet. Angel: the big "angel wings" salvo of heavy aircraft
	/// and helicopters, released in pairs both sides at once, with large twinkling flares and long white smoke wings.</summary>
	public enum PxFlareStyle { Standard, Angel }

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

		// Angel salvo: lighter drag and gravity, so the flares sail out in wide arcs and burn longer
		const float AngelGravity = 1.1f;
		const float AngelDrag = 0.95f;
		const int AngelLift = 20;

		sealed class Flare
		{
			public float X, Y, Z;
			public float VX, VY, VZ;
			public int Age, Life;
			public float Phase;
			public bool Released, Out;
		}

		readonly Actor jet;
		readonly WPos anchor;
		readonly List<Flare> flares = new();
		readonly PxParticles particles;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		readonly PxFlareStyle style;
		float forwardX, forwardY;
		WVec jetVelocity;
		WPos jetLast;
		int ticks;

		public PxFlareBurst(Actor jet, WVec velocity, int count, PxFlareStyle style = PxFlareStyle.Standard)
		{
			this.jet = jet;
			this.style = style;
			jetLast = jet.CenterPosition;
			jetVelocity = velocity;
			anchor = new WPos(jetLast.X, jetLast.Y, 0);
			particles = new PxParticles(jet.World) { Max = style == PxFlareStyle.Angel ? 5200 : 2400 };

			// A hovering helicopter has no speed: the salvo goes off its nose direction instead
			var nose = new WVec(0, -1024, 0).Rotate(WRot.FromYaw(jet.Orientation.Yaw));
			forwardX = nose.X / 1024f;
			forwardY = nose.Y / 1024f;
			SetForward(velocity);
			for (var i = 0; i < count; i++)
				flares.Add(new Flare
				{
					Life = style == PxFlareStyle.Angel ? 95 + rng.Next(30) : 48 + rng.Next(24),
					Phase = Rand(0, MathF.PI * 2)
				});

			if (style == PxFlareStyle.Angel)
				Ignite();
		}

		bool Angel => style == PxFlareStyle.Angel;

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
		public static WVec Drift(WVec jetVelocity, int t, PxFlareStyle style = PxFlareStyle.Standard)
		{
			// Integer steps (fixed point x1024): the result aims synced missiles, so no float maths here
			var angel = style == PxFlareStyle.Angel;
			var drag = angel ? 95 : 93;
			var gravity = (long)((angel ? AngelGravity : Gravity) * 1024);
			long vx = jetVelocity.X * 512L, vy = jetVelocity.Y * 512L, vz = (long)(angel ? AngelLift : AverageLift) * 1024;
			long x = 0, y = 0, z = 0;
			for (var i = 0; i < t; i++)
			{
				vx = vx * drag / 100;
				vy = vy * drag / 100;
				vz = vz * drag / 100 - gravity;
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
					// Angel flares leave in pairs, one each side on the same tick, so the wings stay symmetrical
					if (ticks >= (Angel ? i / 2 : i * ReleaseInterval))
						Release(f, i % 2 == 0 ? 1 : -1, Angel ? (float)(i / 2) / Math.Max(1, (flares.Count - 1) / 2) : 0);
					else
					{
						burning = true;
						continue;
					}
				}

				if (f.Out)
					continue;

				burning = true;
				var drag = Angel ? AngelDrag : Drag;
				f.VX *= drag;
				f.VY *= drag;
				f.VZ = f.VZ * drag - (Angel ? AngelGravity : Gravity);
				f.X += f.VX;
				f.Y += f.VY;
				f.Z += f.VZ;
				if (++f.Age >= f.Life || f.Z <= 0)
				{
					f.Out = true;
					if (Angel)
						BurnOut(f);

					continue;
				}

				if (Angel)
					EmitAngel(f);
				else
					Emit(f);
			}

			particles.Update(1);
			ticks++;
			if (!burning && particles.Items.Count == 0)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		void Release(Flare f, int side, float order)
		{
			f.Released = true;
			f.X = jetLast.X;
			f.Y = jetLast.Y;
			f.Z = jetLast.Z;

			// Kicked out sideways and a little back and up, keeping part of the jet's speed
			var rightX = -forwardY;
			var rightY = forwardX;
			float sideways, back;
			if (Angel)
			{
				// Early pairs go up and out, later ones wider and flatter: together they draw the curved wings
				sideways = side * (34 + 84 * order + Rand(-6, 6));
				back = -(10 + 22 * order);
				f.VZ = 30 - 16 * order + Rand(-3, 3);
			}
			else
			{
				sideways = side * Rand(38, 78);
				back = -Rand(8, 30);
				f.VZ = Rand(14, 34);
			}

			f.VX = jetVelocity.X * 0.5f + rightX * sideways + forwardX * back;
			f.VY = jetVelocity.Y * 0.5f + rightY * sideways + forwardY * back;

			// Ignition flash
			var at = Local(f);
			Add(PxParticleKind.Glow, at, Angel ? 2.6f : 1.7f, Angel ? 5 : 4, 0.9f, new float3(1f, 0.92f, 0.75f));
			for (var i = 0; i < (Angel ? 7 : 4); i++)
				Spark(at, Angel ? 2.2f : 1.6f);
		}

		void Ignite()
		{
			// The whole dispenser fires at once: a white flash round the aircraft and a hot shock ring
			var at = new float3((jetLast.X - anchor.X) * PixelPerWorld, (jetLast.Y - anchor.Y) * PixelPerWorld, jetLast.Z * PixelPerWorld);
			Add(PxParticleKind.Glow, at, 5.5f, 7, 0.85f, new float3(1f, 0.95f, 0.85f));
			Add(PxParticleKind.Glow, at, 9f, 10, 0.3f, new float3(1f, 0.62f, 0.25f));
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Ring,
				X = at.X,
				Y = at.Y,
				Z = at.Z,
				Life = 16,
				Size = 0.6f,
				Grow = 5f,
				Alpha = 0.7f,
				Tint = new float3(1f, 0.85f, 0.6f),
				Frame = rng.Next(Math.Max(1, particles.FrameCount(PxParticleKind.Ring))),
				Angle = rng.Next(1024),
			});

			for (var i = 0; i < 18; i++)
				Spark(at, 3f);
		}

		void EmitAngel(Flare f)
		{
			var at = Local(f);
			var t = (float)f.Age / f.Life;
			var heat = t < 0.75f ? 1f : (1 - t) / 0.25f;
			var twinkle = 0.75f + 0.25f * MathF.Sin(f.Age * 1.9f + f.Phase);

			// Big flickering white-hot core, a gold halo and a wide warm bloom that lights up the sky around it
			Add(PxParticleKind.Glow, at, Rand(0.6f, 0.8f) * twinkle * (0.5f + 0.5f * heat), 1.6f, 1f, new float3(1f, 0.98f, 0.92f));
			Add(PxParticleKind.Glow, at, 2.1f * heat * twinkle, 1.6f, 0.55f * heat, new float3(1f, 0.7f, 0.3f));
			Add(PxParticleKind.Glow, at, 3.8f * heat, 1.6f, 0.16f * heat, new float3(1f, 0.5f, 0.2f));

			// Thick white smoke: the lingering "angel wings"
			if ((f.Age & 1) == 0)
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Smoke,
					X = at.X + Rand(-0.5f, 0.5f),
					Y = at.Y + Rand(-0.4f, 0.4f),
					Z = at.Z,
					VX = Rand(-0.03f, 0.03f),
					VY = Rand(-0.02f, 0.02f),
					VZ = Rand(0, 0.02f),
					Drag = 0.04f,
					Life = Rand(150, 190),
					Size = Rand(0.28f, 0.36f),
					Grow = 3.6f,
					Alpha = 0.62f * (0.4f + 0.6f * heat),
					Tint = new float3(0.95f, 0.93f, 0.9f),
					Frame = rng.Next(Math.Max(1, particles.FrameCount(PxParticleKind.Smoke))),
					Spin = Rand(-1.2f, 1.2f),
					Angle = rng.Next(1024),
				});

			if (rng.NextFloat() < 0.6f * heat)
				Spark(at, 0.8f);
		}

		void BurnOut(Flare f)
		{
			// Each flare dies with a last pop of sparks
			var at = Local(f);
			Add(PxParticleKind.Glow, at, 1.4f, 4, 0.6f, new float3(1f, 0.75f, 0.4f));
			for (var i = 0; i < 5; i++)
				Spark(at, 1.2f);
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
