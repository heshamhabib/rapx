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
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Support;

namespace OpenRA.Mods.RAPX.Effects
{
	/// <summary>
	/// A soldier thrown by an explosion (WithPxBlastDeath), purely cosmetic: the limp body flies away from the blast in
	/// an arc, tumbling, with its shadow racing along the ground below it, bounces once in a puff of dust and lies
	/// where it fell until it fades. The body is the soldier's own prone sprite turned in the air.
	/// </summary>
	public class PxThrownBody : IEffect
	{
		const float WorldPerPixel = 1024f / 24f;
		const float Gravity = 0.2f;
		const int BodyZ = 512;
		const int ShadowZ = -1024;
		const int FadeTicks = 60;

		readonly World world;
		readonly WPos origin;
		readonly ISpriteSequence body;
		readonly ISpriteSequence shadow;
		readonly int bodyFrame;
		readonly WAngle bodyFacing;
		readonly string palette;
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly int corpseTicks;
		readonly float3 dust;

		float x, y, z, vx, vy, vz, angle, spin, time, landedAt;
		long lastTime = -1;
		bool landed;
		int bounces;

		public PxThrownBody(World world, WPos pos, PxBlast blast, string image, string bodySequence, string palette, WAngle facing, int corpseTicks)
		{
			this.world = world;
			this.palette = palette;
			this.corpseTicks = corpseTicks;
			origin = pos;

			var sequences = world.Map.Sequences;
			body = sequences.HasSequence(image, bodySequence) ? sequences.GetSequence(image, bodySequence) : sequences.GetSequence(image, "stand");
			bodyFrame = body.Length - 1;
			particles = new PxParticles(world) { Max = 80 };
			shadow = particles.Sequence("shadow");

			// Away from the blast (any direction when it went off right underneath), in screen pixels
			var d = pos - blast.Pos;
			var dx = d.X / WorldPerPixel;
			var dy = d.Y / WorldPerPixel;
			var dist = MathF.Sqrt(dx * dx + dy * dy);
			float ax, ay;
			if (dist < 2)
			{
				var a = Rand(0, MathF.PI * 2);
				ax = MathF.Cos(a);
				ay = MathF.Sin(a) * 0.6f;
				dist = 0;
			}
			else
			{
				ax = dx / dist;
				ay = dy / dist;
			}

			var reach = blast.Radius.Length / WorldPerPixel;
			var fall = 1 - 0.65f * Math.Clamp(dist / reach, 0, 1);
			var k = MathF.Pow(Math.Max(0.3f, blast.Size), 0.6f) * fall;
			var speed = Rand(1.7f, 2.9f) * k;
			vx = ax * speed;
			vy = ay * speed;
			vz = Rand(2.4f, 3.8f) * MathF.Pow(k, 0.8f);
			spin = Rand(22, 60) * (random.Next(2) == 0 ? -1 : 1) * Math.Clamp(k, 0.5f, 1.5f);
			angle = Rand(-60, 60);

			// Head first or feet first, along the flight
			var yaw = dist > 0 ? d.Yaw : facing;
			bodyFacing = random.Next(2) == 0 ? yaw : yaw + new WAngle(512);

			dust = world.Map.Tileset switch
			{
				"SNOW" => new float3(0.9f, 0.92f, 0.95f),
				"DESERT" => new float3(0.76f, 0.66f, 0.48f),
				_ => new float3(0.5f, 0.43f, 0.33f),
			};
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		void Puff(float strength)
		{
			var n = (int)(3 * strength) + 1;
			for (var i = 0; i < n; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				var s = Rand(0.1f, 0.4f) * strength;
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Smoke2,
					X = x + Rand(-1.5f, 1.5f),
					Y = y + Rand(-0.8f, 0.8f),
					Z = 0.5f,
					VX = MathF.Cos(a) * s + vx * 0.2f,
					VY = MathF.Sin(a) * s * 0.6f + vy * 0.2f,
					VZ = Rand(0.1f, 0.3f) * strength,
					Drag = 0.08f,
					Life = Rand(18, 32),
					Size = Rand(0.3f, 0.45f) * strength,
					Grow = 2.4f,
					Alpha = 0.55f,
					Tint = dust,
					Frame = random.Next(particles.FrameCount(PxParticleKind.Smoke2)),
					Spin = Rand(-1, 1),
					Angle = random.Next(1024),
				});
			}
		}

		public void Tick(World world)
		{
			if ((landed && time - landedAt > corpseTicks + FadeTicks) || time > 2000)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)world.Timestep;
			lastTime = now;
			if (!world.Paused)
			{
				time += dt;
				if (!landed)
				{
					vz -= Gravity * dt;
					x += vx * dt;
					y += vy * dt;
					z += vz * dt;
					angle += spin * dt;
					if (z <= 0 && vz < 0)
					{
						z = 0;
						if (vz < -1.2f && bounces < 1)
						{
							bounces++;
							Puff(0.7f);
							vz = -vz * 0.28f;
							vx *= 0.45f;
							vy *= 0.45f;
							spin *= 0.4f;
						}
						else
						{
							Puff(1f);
							landed = true;
							landedAt = time;
							vx = vy = vz = spin = 0;
						}
					}
				}

				particles.Update(dt);
			}

			var ground = origin + PxParticles.ToWorld(x, y);
			if (world.FogObscures(ground))
				yield break;

			var alpha = landed ? 1 - Math.Clamp((time - landedAt - corpseTicks) / FadeTicks, 0, 1) : 1;
			if (alpha <= 0)
				yield break;

			if (!landed && shadow != null)
			{
				var sa = Math.Clamp(0.42f - z * 0.005f, 0.14f, 0.42f);
				yield return new SpriteRenderable(shadow.GetSprite(0), ground, WVec.Zero, ShadowZ, null,
					shadow.Scale * (0.85f + z * 0.004f), sa, new float3(0, 0, 0), TintModifiers.None, false);
			}

			var lift = PxParticles.ToWorld(0, -z);
			yield return new SpriteRenderable(body.GetSprite(bodyFrame, bodyFacing), ground + lift, WVec.Zero, BodyZ - lift.Y,
				wr.Palette(palette), body.Scale, alpha, new float3(1, 1, 1), TintModifiers.None, false, new WAngle(((int)angle % 1024 + 1024) % 1024));

			foreach (var r in particles.Render(origin, 256))
				yield return r;
		}
	}
}
