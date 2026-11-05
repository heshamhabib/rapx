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
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Projectiles
{
	[Desc("High-definition energy beam: layered glow around a white-hot core, a flickering pulse, crackling filaments",
		"along the beam, glowing flares at the emitter and the impact point, and impact sparks. Damage like LaserZap.")]
	public class PxGlowLaserInfo : IProjectileInfo
	{
		[Desc("Width of the bright inner beam.")]
		public readonly WDist Width = new(64);

		[Desc("Width of the outermost glow, as a multiple of Width.")]
		public readonly float GlowScale = 5f;

		[Desc("Number of glow layers between the core and the outer glow.")]
		public readonly int GlowLayers = 5;

		[Desc("Colour of the white-hot core.")]
		public readonly Color CoreColor = Color.FromArgb(255, 255, 236, 230);

		[Desc("Main beam colour.")]
		public readonly Color Color = Color.FromArgb(255, 255, 40, 30);

		[Desc("Colour of the outer glow (its alpha is the outermost layer's).")]
		public readonly Color GlowColor = Color.FromArgb(70, 255, 0, 0);

		[Desc("Use the owner's colour for the beam and glow instead (the core stays CoreColor).")]
		public readonly bool UsePlayerColor = false;

		[Desc("Ticks the beam is visible.")]
		public readonly int Duration = 16;

		[Desc("Number of crackling filaments wound around the beam.")]
		public readonly int Filaments = 2;

		[Desc("Radius of the glowing flare at the emitter.")]
		public readonly WDist MuzzleFlare = new(320);

		[Desc("Radius of the glowing flare at the impact point.")]
		public readonly WDist ImpactFlare = new(520);

		[Desc("Number of sparks thrown from the impact point.")]
		public readonly int Sparks = 10;

		[Desc("Equivalent to sequence ZOffset. Controls Z sorting.")]
		public readonly int ZOffset = 2048;

		[Desc("Beam follows the target.")]
		public readonly bool TrackTarget = true;

		[Desc("Total time-frame in ticks that the beam deals damage every DamageInterval.")]
		public readonly int DamageDuration = 1;

		[Desc("The number of ticks between the beam causing warhead impacts.")]
		public readonly int DamageInterval = 1;

		public IProjectile Create(ProjectileArgs args) { return new PxGlowLaser(this, args); }
	}

	public class PxGlowLaser : IProjectile, ISync
	{
		readonly PxGlowLaserInfo info;
		readonly ProjectileArgs args;
		readonly Color color;
		readonly Color glow;
		readonly int seed;
		int ticks;
		int interval;

		[Sync]
		WPos target;

		[Sync]
		WPos source;

		public PxGlowLaser(PxGlowLaserInfo info, ProjectileArgs args)
		{
			this.info = info;
			this.args = args;
			var owner = args.SourceActor.OwnerColor();
			color = info.UsePlayerColor ? owner : info.Color;
			glow = info.UsePlayerColor ? Color.FromArgb(info.GlowColor.A, owner) : info.GlowColor;
			target = args.PassiveTarget;
			source = args.Source;
			seed = Game.CosmeticRandom.Next();
		}

		public void Tick(World world)
		{
			source = args.CurrentSource();
			if (info.TrackTarget && args.GuidedTarget.IsValidFor(args.SourceActor))
				target = args.Weapon.TargetActorCenter ? args.GuidedTarget.CenterPosition : args.GuidedTarget.Positions.ClosestToIgnoringPath(source);

			if (ticks < info.DamageDuration && --interval <= 0)
			{
				var warheadArgs = new WarheadArgs(args)
				{
					ImpactOrientation = new WRot(WAngle.Zero, OpenRA.Mods.Common.Util.GetVerticalAngle(source, target), args.CurrentMuzzleFacing()),
					ImpactPosition = target,
				};

				args.Weapon.Impact(Target.FromPos(target), warheadArgs);
				interval = info.DamageInterval;
			}

			if (++ticks >= info.Duration)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			if (ticks >= info.Duration || (wr.World.FogObscures(target) && wr.World.FogObscures(source)))
				yield break;

			yield return new PxGlowLaserRenderable(info, source, target, color, glow, ticks, seed);
		}
	}

	public class PxGlowLaserRenderable : IRenderable, IFinalizedRenderable
	{
		readonly PxGlowLaserInfo info;
		readonly WPos target;
		readonly Color color;
		readonly Color glow;
		readonly int ticks;
		readonly int seed;

		public PxGlowLaserRenderable(PxGlowLaserInfo info, WPos source, WPos target, Color color, Color glow, int ticks, int seed)
		{
			this.info = info;
			Pos = source;
			this.target = target;
			this.color = color;
			this.glow = glow;
			this.ticks = ticks;
			this.seed = seed;
		}

		public WPos Pos { get; }
		public int ZOffset => info.ZOffset;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxGlowLaserRenderable(info, Pos + vec, target + vec, color, glow, ticks, seed); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		static Color Alpha(Color c, float a) { return Color.FromArgb((int)Math.Clamp(c.A * a, 0, 255), c.R, c.G, c.B); }

		static Color Mix(Color a, Color b, float t)
		{
			return Color.FromArgb(
				(int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}

		public void Render(WorldRenderer wr)
		{
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			var start = wr.Screen3DPosition(Pos);
			var end = wr.Screen3DPosition(target);
			var d = end - start;
			var len = (float)Math.Sqrt(d.X * d.X + d.Y * d.Y);
			if (len < 1)
				return;

			var dir = new float3(d.X / len, d.Y / len, 0);
			var normal = new float3(-dir.Y, dir.X, 0);
			var px = wr.ScreenVector(new WVec(info.Width, WDist.Zero, WDist.Zero))[0];

			// Envelope: a quick flash to full strength, a short hold, then an eased fade; the width shrinks as it fades
			var t = (float)ticks / info.Duration;
			var intensity = t < 0.12f ? 0.6f + t / 0.12f * 0.4f : (float)Math.Pow(1 - (t - 0.12f) / 0.88f, 1.6);
			var rng = new Random(seed + ticks * 7919);
			var flicker = 0.85f + 0.15f * (float)rng.NextDouble();
			var pulse = 1f + 0.12f * (float)Math.Sin(ticks * 1.9 + seed % 7);
			var width = px * pulse * (0.55f + 0.45f * intensity);

			// Glow layers, widest and faintest first
			for (var i = info.GlowLayers; i >= 1; i--)
			{
				var f = (float)i / info.GlowLayers;
				var w = width * (1 + (info.GlowScale - 1) * f);
				var c = Alpha(Mix(color, glow, f), (1.2f - f) * intensity * flicker * 0.7f);
				cr.DrawLine(start, end, w, c);
			}

			cr.DrawLine(start, end, width, Alpha(color, intensity * flicker));
			cr.DrawLine(start, end, width * 0.45f, Alpha(info.CoreColor, Math.Min(1, intensity * 1.2f)));

			// Crackling filaments: jagged threads wound around the beam, re-rolled every tick
			var segments = Math.Max(4, (int)(len / 18));
			for (var f = 0; f < info.Filaments; f++)
			{
				var prev = start;
				var phase = (float)rng.NextDouble() * 6.28f;
				for (var s = 1; s <= segments; s++)
				{
					var u = (float)s / segments;
					var taper = (float)Math.Sin(u * Math.PI);
					var off = (float)Math.Sin(u * 9 + phase + f * 2.1f) * width * 0.9f + ((float)rng.NextDouble() - 0.5f) * width * 0.8f;
					var p = start + u * d + off * taper * normal;
					cr.DrawLine(prev, p, Math.Max(1, width * 0.12f), Alpha(Mix(info.CoreColor, color, 0.35f), intensity * 0.8f));
					prev = p;
				}
			}

			// Flares: soft concentric discs with a hot centre
			Flare(cr, start, wr.ScreenVector(new WVec(info.MuzzleFlare, WDist.Zero, WDist.Zero))[0] * (0.7f + 0.3f * pulse), intensity);
			var impactRadius = wr.ScreenVector(new WVec(info.ImpactFlare, WDist.Zero, WDist.Zero))[0];
			Flare(cr, end, impactRadius * (0.8f + 0.4f * (1 - t)) * pulse, intensity);

			// Impact sparks fly outward and fade
			for (var i = 0; i < info.Sparks; i++)
			{
				var sr = new Random(seed + i * 104729);
				var a = sr.NextDouble() * Math.PI * 2;
				var speed = 0.4f + (float)sr.NextDouble() * 0.6f;
				var reach = impactRadius * (0.3f + 1.2f * t) * speed;
				var sdir = new float3((float)Math.Cos(a), (float)Math.Sin(a) * 0.6f, 0);
				var tail = end + reach * sdir;
				var head = end + (reach + impactRadius * 0.25f * speed) * sdir;
				cr.DrawLine(tail, head, Math.Max(1, width * 0.18f), Alpha(Mix(info.CoreColor, color, 0.5f), (1 - t) * flicker));
			}
		}

		void Flare(RgbaColorRenderer cr, float3 at, float radius, float intensity)
		{
			const int Rings = 5;
			for (var i = Rings; i >= 1; i--)
			{
				var f = (float)i / Rings;
				var r = radius * f;
				var c = Alpha(Mix(color, glow, f), (1.15f - f) * intensity * 0.75f);
				cr.FillEllipse(at - new float3(r, r * 0.7f, 0), at + new float3(r, r * 0.7f, 0), c);
			}

			var core = radius * 0.22f;
			cr.FillEllipse(at - new float3(core, core * 0.7f, 0), at + new float3(core, core * 0.7f, 0), Alpha(info.CoreColor, intensity));
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
