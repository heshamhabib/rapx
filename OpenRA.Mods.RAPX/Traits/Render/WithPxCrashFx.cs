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
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("A shot-down aircraft's crash (on the falling husk, cosmetic pxfx particles): a mid-air fireball with a flash,",
		"shock ring, sparks and pieces breaking off; fire and thick black smoke trailing the wreck as it spins down; on",
		"impact burning debris thrown out and bouncing, and fires that keep burning under a rising smoke column.")]
	public class WithPxCrashFxInfo : TraitInfo
	{
		[Desc("Size of the effects: 1 = a fighter, larger for bombers.")]
		public readonly float Size = 1f;

		[Desc("How long the crash site keeps burning and smoking, in ticks.")]
		public readonly int BurnTicks = 260;

		[Desc("Filmed impact (sequence of image pxvideofx, artsrc/fx/make_video_fx.py): a fiery skid from left to right,",
			"with a mirrored copy <Video>-m for wrecks coming down heading left. Empty or missing = particles only.")]
		public readonly string Video = "crash-a";

		[Desc("Size of the filmed impact. It grows with the square root of Size, so a bomber's skid stays on screen.")]
		public readonly float VideoScale = 0.7f;

		public override object Create(ActorInitializer init) { return new WithPxCrashFx(this); }
	}

	public class WithPxCrashFx : ITick, INotifyAddedToWorld, INotifyRemovedFromWorld
	{
		readonly WithPxCrashFxInfo info;
		PxCrashEffect effect;
		WPos last;
		int heading;

		public WithPxCrashFx(WithPxCrashFxInfo info)
		{
			this.info = info;
		}

		void INotifyAddedToWorld.AddedToWorld(Actor self)
		{
			last = self.CenterPosition;
			effect = new PxCrashEffect(self.World, self.CenterPosition, info.Size, info.BurnTicks);
			effect.Burst(self.CenterPosition);
			self.World.AddFrameEndTask(w => w.Add(effect));
		}

		void ITick.Tick(Actor self)
		{
			if (effect == null)
				return;

			var pos = self.CenterPosition;
			effect.Falling(last, pos);
			if (pos.X != last.X)
				heading = Math.Sign(pos.X - last.X);
			last = pos;
		}

		void INotifyRemovedFromWorld.RemovedFromWorld(Actor self)
		{
			// FallsToEarth removes the husk when it hits the ground: the crash site takes over
			if (effect == null)
				return;

			var ground = new WPos(last.X, last.Y, 0);
			var world = self.World;
			var clip = PxVideoEffect.Find(world, heading < 0 ? info.Video + "-m" : info.Video) ?? PxVideoEffect.Find(world, info.Video);
			effect.Impact(ground, clip != null);
			if (clip != null)
				world.AddFrameEndTask(w => w.Add(new PxVideoEffect(w, ground, clip, clip.Scale * MathF.Sqrt(info.Size) * info.VideoScale, 90, 512)));

			effect = null;
		}
	}

	public class PxCrashEffect : IEffect
	{
		const float PixelPerWorld = 24f / 1024f;

		readonly WPos anchor;
		readonly float size;
		readonly int burnTicks;
		readonly PxParticles particles;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		WPos sort;
		float3 site;
		int burning = -1;

		static readonly float3 Fire = new(1f, 0.6f, 0.25f);
		static readonly float3 HotFire = new(1f, 0.85f, 0.55f);
		static readonly float3 BlackSmoke = new(0.16f, 0.15f, 0.14f);
		static readonly float3 GreySmoke = new(0.42f, 0.4f, 0.38f);
		static readonly float3 Metal = new(0.35f, 0.34f, 0.33f);

		public PxCrashEffect(World world, WPos at, float size, int burnTicks)
		{
			anchor = new WPos(at.X, at.Y, 0);
			sort = at;
			this.size = size;
			this.burnTicks = burnTicks;
			particles = new PxParticles(world) { Max = 900 };
		}

		float3 Local(WPos p)
		{
			return new float3((p.X - anchor.X) * PixelPerWorld, (p.Y - anchor.Y) * PixelPerWorld, p.Z * PixelPerWorld);
		}

		float R(float a, float b) { return a + (b - a) * rng.NextFloat(); }

		void Add(PxParticleKind kind, float3 at, float spread, float3 v, float gravity, float drag, float life, float sz,
			float grow, float alpha, float3 tint, float spin = 3)
		{
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = at.X + R(-0.5f, 0.5f) * spread,
				Y = at.Y + R(-0.5f, 0.5f) * spread * 0.6f,
				Z = at.Z + R(-0.5f, 0.5f) * spread * 0.5f,
				VX = v.X, VY = v.Y, VZ = v.Z,
				Gravity = gravity,
				Drag = drag,
				Life = life * R(0.8f, 1.2f),
				Size = sz * size * R(0.8f, 1.2f),
				Grow = grow,
				Alpha = alpha,
				Tint = tint,
				Frame = rng.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = R(-spin, spin),
				Angle = rng.Next(1024),
			});
		}

		float3 Out(float speed, float up)
		{
			var a = R(0, MathF.PI * 2);
			var sp = speed * R(0.4f, 1f) * size;
			return new float3(MathF.Cos(a) * sp, MathF.Sin(a) * sp * 0.6f, up * R(0.3f, 1f));
		}

		/// <summary>The hit: flash, fireball, shock ring, sparks and the first pieces breaking off.</summary>
		public void Burst(WPos at)
		{
			var p = Local(at);
			Add(PxParticleKind.Glow, p, 0, default, 0, 0, 7, 1.6f, 0.6f, 1f, HotFire, 0);
			Add(PxParticleKind.Ring, p, 0, default, 0, 0, 14, 0.9f, 1.5f, 0.7f, new float3(1f, 0.9f, 0.8f), 0);
			for (var i = 0; i < 16; i++)
				Add(PxParticleKind.Flame, p, 6 * size, Out(0.9f, 0.4f), 0, 0.12f, 16, 0.55f, 1.2f, 1f, i % 3 == 0 ? HotFire : Fire);
			for (var i = 0; i < 10; i++)
				Add(PxParticleKind.Plume, p, 6 * size, Out(0.5f, 0.2f), 0, 0.06f, 70, 0.4f, 2.2f, 0.75f, BlackSmoke);
			for (var i = 0; i < 18; i++)
				Add(PxParticleKind.Spark, p, 2, Out(2.6f, 1.2f), 0.09f, 0.03f, 22, 0.35f, 0, 1f, HotFire, 0);
			for (var i = 0; i < 8; i++)
				Add(PxParticleKind.Chunk, p, 3, Out(1.6f, 1.4f), 0.1f, 0.01f, 90, 0.5f, 0, 1f, Metal, 18);
		}

		/// <summary>One tick of the fall: fire and black smoke along the path flown, now and then sparks and debris.</summary>
		public void Falling(WPos from, WPos to)
		{
			sort = to;
			var a = Local(from);
			var b = Local(to);
			for (var i = 0; i < 3; i++)
			{
				var f = (i + rng.NextFloat()) / 3;
				var at = new float3(a.X + (b.X - a.X) * f, a.Y + (b.Y - a.Y) * f, a.Z + (b.Z - a.Z) * f);
				Add(PxParticleKind.Plume, at, 2.5f, new float3(R(0.02f, 0.08f), 0, R(0.05f, 0.15f)), 0, 0.03f, 85, 0.3f, 2.8f, 0.6f, BlackSmoke);
				if (i < 2)
					Add(PxParticleKind.Flame, at, 1.5f, new float3(0, 0, R(0, 0.1f)), 0, 0.1f, 9, 0.42f, 0.8f, 0.95f, i == 0 ? HotFire : Fire);
			}

			if (rng.NextFloat() < 0.25f)
				Add(PxParticleKind.Spark, b, 1, Out(1.4f, 0.6f), 0.08f, 0.03f, 14, 0.3f, 0, 1f, HotFire, 0);
			if (rng.NextFloat() < 0.06f)
				Add(PxParticleKind.Chunk, b, 1, Out(1f, 0.8f), 0.1f, 0.01f, 80, 0.4f, 0, 1f, Metal, 18);
		}

		/// <summary>The impact: burning debris thrown out, ground fires, and the crash site starts to burn. With a filmed
		/// impact (video) the burst of flames and smoke is left to the film.</summary>
		public void Impact(WPos at, bool video = false)
		{
			site = Local(at);
			sort = at;
			burning = burnTicks;
			Add(PxParticleKind.Glow, site, 0, default, 0, 0, 8, 2.2f, 0.5f, 1f, HotFire, 0);
			Add(PxParticleKind.Ring, site, 0, default, 0, 0, 16, 1.2f, 1.8f, 0.6f, new float3(0.9f, 0.85f, 0.75f), 0);
			for (var i = 0; i < 22; i++)
				Add(PxParticleKind.Chunk, site, 4, Out(2.2f, 2.4f), 0.12f, 0.01f, R(120, 220), 0.5f, 0, 1f, i % 4 == 0 ? Fire : Metal, 20);
			for (var i = 0; i < (video ? 0 : 14); i++)
				Add(PxParticleKind.Flame, site, 14 * size, new float3(0, 0, R(0.05f, 0.2f)), 0, 0.1f, R(40, 90), 0.5f, 0.6f, 1f, Fire);
			for (var i = 0; i < (video ? 4 : 12); i++)
				Add(PxParticleKind.Plume, site, 10 * size, Out(0.4f, 0.5f), 0, 0.04f, 110, 0.55f, 2.5f, 0.8f, BlackSmoke);
			for (var i = 0; i < 24; i++)
				Add(PxParticleKind.Spark, site, 3, Out(3f, 2.4f), 0.1f, 0.02f, 26, 0.35f, 0, 1f, HotFire, 0);
		}

		public void Tick(World world)
		{
			particles.Update(1);
			if (burning > 0)
			{
				// The crash site burns down: flickering fires and a smoke column that thins as the fire dies
				var t = (float)burning / burnTicks;
				burning--;
				if (rng.NextFloat() < 0.4f + 0.6f * t)
					Add(PxParticleKind.Flame, site, 12 * size * (0.5f + t), new float3(0, 0, R(0.05f, 0.18f)), 0, 0.1f, R(14, 26), 0.45f * (0.5f + t), 0.6f, 0.9f, Fire);
				if (rng.NextFloat() < 0.5f + 0.5f * t)
					Add(PxParticleKind.Plume, site, 8 * size, new float3(R(0.03f, 0.1f), R(-0.02f, 0.02f), R(0.25f, 0.45f)), 0, 0.01f, 130,
						0.35f, 3f, 0.55f * (0.4f + 0.6f * t), t > 0.4f ? BlackSmoke : GreySmoke);
			}

			if (burning <= 0 && particles.Items.Count == 0 && burning != -1)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			// While falling: just under the wreck; on the ground: over the crater (a little south of it)
			var zBias = burning >= 0 ? 256 + (sort.Y - anchor.Y) : sort.Y + sort.Z - anchor.Y - 64;
			return particles.Render(anchor, zBias, p => wr.World.FogObscures(p));
		}
	}
}
