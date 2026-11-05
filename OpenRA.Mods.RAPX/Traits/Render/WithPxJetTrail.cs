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
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Real-looking jet trails instead of the flat Contrail lines: a soft exhaust plume from each engine that grows,",
		"drifts and fades, an afterburner glow at the nozzle, and wingtip vapour that thickens when the jet turns hard.",
		"Cosmetic only (pxfx particles). Offsets are generated per aircraft by artsrc/jets/make_trails.py.")]
	public class WithPxJetTrailInfo : ConditionalTraitInfo, Requires<BodyOrientationInfo>
	{
		[Desc("Engine nozzle positions (forward, right, up) relative to the aircraft centre.")]
		public readonly WVec[] Engines = { new(-600, 0, 0) };

		[Desc("Wingtip positions for vapour trails. Empty for none.")]
		public readonly WVec[] Wingtips = Array.Empty<WVec>();

		[Desc("Exhaust puffs per engine per tick (spread along the path flown).")]
		public readonly int Density = 3;

		[Desc("How long exhaust smoke lingers, in ticks.")]
		public readonly int Life = 55;

		[Desc("Exhaust puff size (pxfx scale) at the nozzle; it grows as it spreads.")]
		public readonly float Size = 0.26f;

		[Desc("Exhaust opacity at the nozzle.")]
		public readonly float Opacity = 0.32f;

		[Desc("Exhaust tint (1 = the sprite's own white).")]
		public readonly float3 Tint = new(0.9f, 0.9f, 0.92f);

		[Desc("Afterburner glow at the nozzles (jets; off for propeller planes).")]
		public readonly bool Afterburner = true;

		[Desc("Wingtip vapour: opacity when flying straight and at the hardest turn.")]
		public readonly float VapourMin = 0.05f;

		public readonly float VapourMax = 0.5f;

		[Desc("Turn rate (WAngle per tick) that gives full wingtip vapour.")]
		public readonly int FullVapourTurn = 24;

		public override object Create(ActorInitializer init) { return new WithPxJetTrail(init.Self, this); }
	}

	public class WithPxJetTrail : ConditionalTrait<WithPxJetTrailInfo>, ITick, INotifyAddedToWorld, INotifyRemovedFromWorld
	{
		readonly BodyOrientation body;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		PxJetTrailEffect effect;
		WPos[] lastEngines;
		WPos[] lastTips;
		WAngle lastYaw;
		float vapour;

		public WithPxJetTrail(Actor self, WithPxJetTrailInfo info)
			: base(info)
		{
			body = self.Trait<BodyOrientation>();
		}

		void INotifyAddedToWorld.AddedToWorld(Actor self)
		{
			effect = new PxJetTrailEffect(self.World, self.CenterPosition);
			self.World.AddFrameEndTask(w => w.Add(effect));
		}

		void INotifyRemovedFromWorld.RemovedFromWorld(Actor self)
		{
			// The smoke stays in the sky and fades on its own after the aircraft is gone
			if (effect != null)
				effect.Orphaned = true;
			effect = null;
		}

		WPos Point(Actor self, WVec offset)
		{
			return self.CenterPosition + body.LocalToWorld(offset.Rotate(self.Orientation));
		}

		void ITick.Tick(Actor self)
		{
			if (effect == null)
				return;

			effect.SortPosition = self.CenterPosition;
			if (IsTraitDisabled)
			{
				lastEngines = lastTips = null;
				return;
			}

			var engines = Array.ConvertAll(Info.Engines, o => Point(self, o));
			var tips = Array.ConvertAll(Info.Wingtips, o => Point(self, o));

			// Vapour follows how hard the jet turns, eased so it builds up and dies away smoothly
			var yaw = self.Orientation.Yaw;
			var turn = Math.Abs((yaw - lastYaw).Angle > 512 ? 1024 - (yaw - lastYaw).Angle : (yaw - lastYaw).Angle);
			lastYaw = yaw;
			var target = Math.Clamp((float)turn / Info.FullVapourTurn, 0, 1);
			vapour += (target - vapour) * 0.15f;

			if (lastEngines != null)
			{
				for (var e = 0; e < engines.Length; e++)
				{
					for (var i = 0; i < Info.Density; i++)
					{
						var f = (i + rng.NextFloat()) / Info.Density;
						var at = WPos.Lerp(lastEngines[e], engines[e], (int)(f * 1024), 1024);
						effect.Exhaust(at, Info.Size, Info.Life, Info.Opacity, Info.Tint, rng);
					}

					if (Info.Afterburner)
						effect.Glow(engines[e], rng);
				}

				var vapourAlpha = Info.VapourMin + (Info.VapourMax - Info.VapourMin) * vapour;
				if (vapourAlpha > 0.02f)
					for (var t = 0; t < tips.Length; t++)
						for (var i = 0; i < 2; i++)
							effect.Vapour(WPos.Lerp(lastTips[t], tips[t], i * 512 + 256, 1024), vapourAlpha, rng);
			}

			lastEngines = engines;
			lastTips = tips;
		}
	}

	/// <summary>The trail particles of one aircraft, as a world effect so the smoke outlives its emitter's screen
	/// bounds and the aircraft itself.</summary>
	public class PxJetTrailEffect : IEffect
	{
		const float PixelPerWorld = 24f / 1024f;

		readonly WPos anchor;
		readonly PxParticles particles;
		public WPos SortPosition;
		public bool Orphaned;

		public PxJetTrailEffect(World world, WPos anchor)
		{
			this.anchor = new WPos(anchor.X, anchor.Y, 0);
			SortPosition = anchor;
			particles = new PxParticles(world);
		}

		float3 Local(WPos p)
		{
			return new float3((p.X - anchor.X) * PixelPerWorld, (p.Y - anchor.Y) * PixelPerWorld, p.Z * PixelPerWorld);
		}

		void Add(PxParticleKind kind, WPos at, float spread, float size, float grow, float life, float alpha, float3 tint,
			float drift, MersenneTwister rng)
		{
			var p = Local(at);
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = p.X + (rng.NextFloat() - 0.5f) * spread,
				Y = p.Y + (rng.NextFloat() - 0.5f) * spread * 0.6f,
				Z = p.Z + (rng.NextFloat() - 0.5f) * spread * 0.3f,

				// A light breeze carries the smoke east; it settles a little as it cools
				VX = drift + (rng.NextFloat() - 0.5f) * drift,
				VY = (rng.NextFloat() - 0.5f) * drift * 0.6f,
				VZ = -0.01f,
				Drag = 0.02f,
				Life = life * (0.8f + 0.4f * rng.NextFloat()),
				Size = size * (0.85f + 0.3f * rng.NextFloat()),
				Grow = grow,
				Alpha = alpha,
				Tint = tint,
				Frame = rng.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = (rng.NextFloat() - 0.5f) * 3,
				Angle = rng.Next(1024),
			});
		}

		public void Exhaust(WPos at, float size, int life, float alpha, float3 tint, MersenneTwister rng)
		{
			Add(PxParticleKind.Smoke, at, 1.2f, size, 2.6f, life, alpha, tint, 0.06f, rng);
		}

		public void Glow(WPos at, MersenneTwister rng)
		{
			Add(PxParticleKind.Glow, at, 0.3f, 0.22f, 0.4f, 3, 0.55f + 0.25f * rng.NextFloat(), new float3(1f, 0.62f, 0.3f), 0, rng);
		}

		public void Vapour(WPos at, float alpha, MersenneTwister rng)
		{
			Add(PxParticleKind.Smoke, at, 0.3f, 0.09f, 1.4f, 26, alpha, new float3(1f, 1f, 1f), 0.02f, rng);
		}

		public void Tick(World world)
		{
			particles.Update(1);
			if (Orphaned && particles.Items.Count == 0)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			// Sorted just under the aircraft (key = Y + Z of its position), so it trails behind and below the jet
			var zBias = SortPosition.Y + SortPosition.Z - anchor.Y - 64;
			return particles.Render(anchor, zBias, p => wr.World.FogObscures(p));
		}
	}
}
