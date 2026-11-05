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
	[Desc("High-definition Tesla lightning (replaces TeslaZap): a jagged bolt that re-forms every few ticks, a second strand,",
		"forked branches, layered glow around a white-hot core, strobe flicker, a glowing orb at the emitter and crawling arcs,",
		"sparks and a light pool at the impact. Damage like TeslaZap (applied in the first DamageDuration ticks).")]
	public class PxLightningInfo : IProjectileInfo
	{
		[Desc("Width of the bright bolt.")]
		public readonly WDist Width = new(48);

		[Desc("Width of the outermost glow, as a multiple of Width.")]
		public readonly float GlowScale = 6f;

		[Desc("Number of glow layers between the core and the outer glow.")]
		public readonly int GlowLayers = 4;

		[Desc("Colour of the white-hot core.")]
		public readonly Color CoreColor = Color.FromArgb(255, 235, 245, 255);

		[Desc("Main bolt colour.")]
		public readonly Color Color = Color.FromArgb(255, 120, 180, 255);

		[Desc("Colour of the outer glow (its alpha is the outermost layer's).")]
		public readonly Color GlowColor = Color.FromArgb(60, 40, 90, 255);

		[Desc("Ticks the lightning is visible.")]
		public readonly int Duration = 12;

		[Desc("The bolt's shape is re-rolled every this many ticks (its crackle).")]
		public readonly int ReshapeInterval = 2;

		[Desc("Sideways jaggedness of the bolt, as a fraction of its length.")]
		public readonly float Jaggedness = 0.14f;

		[Desc("Number of forked branches off the main bolt.")]
		public readonly int Branches = 4;

		[Desc("Number of extra, thinner strands next to the main bolt.")]
		public readonly int Strands = 1;

		[Desc("Radius of the glowing orb at the emitter.")]
		public readonly WDist MuzzleFlare = new(280);

		[Desc("Radius of the flare and crawling arcs at the impact point.")]
		public readonly WDist ImpactFlare = new(420);

		[Desc("Number of small arcs crawling over the impact point.")]
		public readonly int ImpactArcs = 5;

		[Desc("Number of sparks thrown from the impact point.")]
		public readonly int Sparks = 12;

		[Desc("Equivalent to sequence ZOffset. Controls Z sorting.")]
		public readonly int ZOffset = 2048;

		[Desc("Follow the targeted actor when it moves.")]
		public readonly bool TrackTarget = true;

		[Desc("How long (in ticks) damage is applied, once per tick.")]
		public readonly int DamageDuration = 1;

		public IProjectile Create(ProjectileArgs args) { return new PxLightning(this, args); }
	}

	public class PxLightning : IProjectile, ISync
	{
		readonly PxLightningInfo info;
		readonly ProjectileArgs args;
		readonly int seed;
		int ticks;

		[Sync]
		WPos target;

		[Sync]
		WPos source;

		public PxLightning(PxLightningInfo info, ProjectileArgs args)
		{
			this.info = info;
			this.args = args;
			target = args.PassiveTarget;
			source = args.Source;
			seed = Game.CosmeticRandom.Next();
		}

		public void Tick(World world)
		{
			source = args.CurrentSource();
			if (info.TrackTarget && args.GuidedTarget.IsValidFor(args.SourceActor))
				target = args.Weapon.TargetActorCenter ? args.GuidedTarget.CenterPosition : args.GuidedTarget.Positions.ClosestToIgnoringPath(source);

			if (ticks < info.DamageDuration)
				args.Weapon.Impact(Target.FromPos(target), new WarheadArgs(args) { ImpactPosition = target });

			if (++ticks >= info.Duration)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			if (ticks >= info.Duration || (wr.World.FogObscures(target) && wr.World.FogObscures(source)))
				yield break;

			yield return new PxLightningRenderable(info, source, target, ticks, seed);
		}
	}

	public class PxLightningRenderable : IRenderable, IFinalizedRenderable
	{
		readonly PxLightningInfo info;
		readonly WPos target;
		readonly int ticks;
		readonly int seed;

		public PxLightningRenderable(PxLightningInfo info, WPos source, WPos target, int ticks, int seed)
		{
			this.info = info;
			Pos = source;
			this.target = target;
			this.ticks = ticks;
			this.seed = seed;
		}

		public WPos Pos { get; }
		public int ZOffset => info.ZOffset;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxLightningRenderable(info, Pos + vec, target + vec, ticks, seed); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		static Color Alpha(Color c, float a) { return Color.FromArgb((int)Math.Clamp(c.A * a, 0, 255), c.R, c.G, c.B); }

		static Color Mix(Color a, Color b, float t)
		{
			return Color.FromArgb(
				(int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}

		// Jagged path from a to b by midpoint displacement; the ends stay fixed
		static List<float3> Bolt(Random rng, float3 a, float3 b, float jag, int depth)
		{
			var pts = new List<float3> { a, b };
			var amp = jag;
			for (var level = 0; level < depth; level++)
			{
				var next = new List<float3>(pts.Count * 2);
				for (var i = 0; i < pts.Count - 1; i++)
				{
					var p = pts[i];
					var q = pts[i + 1];
					var d = q - p;
					var normal = new float3(-d.Y, d.X, 0);
					var nlen = (float)Math.Sqrt(normal.X * normal.X + normal.Y * normal.Y);
					if (nlen > 0)
						normal /= nlen;

					next.Add(p);
					next.Add(0.5f * (p + q) + ((float)rng.NextDouble() - 0.5f) * 2 * amp * normal);
				}

				next.Add(pts[^1]);
				pts = next;
				amp *= 0.55f;
			}

			return pts;
		}

		void Stroke(RgbaColorRenderer cr, List<float3> pts, float width, Color color, Color glow, float intensity)
		{
			for (var i = info.GlowLayers; i >= 1; i--)
			{
				var f = (float)i / info.GlowLayers;
				cr.DrawLine(pts, width * (1 + (info.GlowScale - 1) * f), Alpha(Mix(color, glow, f), (1.2f - f) * intensity * 0.6f), true);
			}

			cr.DrawLine(pts, width, Alpha(color, intensity), true);
			cr.DrawLine(pts, Math.Max(1, width * 0.4f), Alpha(info.CoreColor, Math.Min(1, intensity * 1.3f)), true);
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

			var px = wr.ScreenVector(new WVec(info.Width, WDist.Zero, WDist.Zero))[0];
			var t = (float)ticks / info.Duration;

			// Flash, then a fading strobe: some ticks drop to a dim afterglow
			var flicker = new Random(seed + ticks * 31);
			var strobe = ticks < 2 ? 1f : flicker.NextDouble() < 0.3 ? 0.35f : 0.8f + 0.2f * (float)flicker.NextDouble();
			var intensity = (ticks < 2 ? 1f : (float)Math.Pow(1 - t, 1.3)) * strobe;
			var width = px * (0.6f + 0.4f * intensity);

			// The shape re-forms every ReshapeInterval ticks
			var shape = new Random(seed + ticks / Math.Max(1, info.ReshapeInterval) * 7919);
			var depth = Math.Clamp((int)Math.Log2(Math.Max(2, len / 6)), 3, 7);
			var main = Bolt(shape, start, end, len * info.Jaggedness, depth);

			for (var s = 0; s < info.Strands; s++)
				Stroke(cr, Bolt(shape, start, end, len * info.Jaggedness * 1.3f, depth), width * 0.45f, info.Color, info.GlowColor, intensity * 0.6f);

			Stroke(cr, main, width, info.Color, info.GlowColor, intensity);

			// Forked branches: start somewhere on the bolt and veer off, thinner and fainter
			for (var b = 0; b < info.Branches; b++)
			{
				var at = main[1 + shape.Next(Math.Max(1, main.Count - 2))];
				var ang = Math.Atan2(d.Y, d.X) + (shape.NextDouble() - 0.5) * 2.2;
				var reach = len * (0.12f + 0.22f * (float)shape.NextDouble());
				var tip = at + reach * new float3((float)Math.Cos(ang), (float)Math.Sin(ang), 0);
				Stroke(cr, Bolt(shape, at, tip, reach * 0.25f, 3), width * 0.4f, info.Color, info.GlowColor, intensity * 0.7f);
			}

			// Emitter orb
			var muzzle = wr.ScreenVector(new WVec(info.MuzzleFlare, WDist.Zero, WDist.Zero))[0];
			Flare(cr, start, muzzle * (0.8f + 0.25f * strobe), intensity);

			// Impact: light pool on the ground, flare, crawling arcs and sparks
			var impact = wr.ScreenVector(new WVec(info.ImpactFlare, WDist.Zero, WDist.Zero))[0];
			var pool = impact * 1.6f;
			cr.FillEllipse(end - new float3(pool, pool * 0.55f, 0), end + new float3(pool, pool * 0.55f, 0), Alpha(info.GlowColor, intensity * 0.6f));
			Flare(cr, end, impact * (0.7f + 0.3f * strobe), intensity);

			for (var i = 0; i < info.ImpactArcs; i++)
			{
				var ang = shape.NextDouble() * Math.PI * 2;
				var r = impact * (0.5f + 0.7f * (float)shape.NextDouble());
				var tip = end + r * new float3((float)Math.Cos(ang), (float)Math.Sin(ang) * 0.6f, 0);
				Stroke(cr, Bolt(shape, end, tip, r * 0.35f, 3), width * 0.3f, info.Color, info.GlowColor, intensity * 0.8f);
			}

			for (var i = 0; i < info.Sparks; i++)
			{
				var sr = new Random(seed + i * 104729);
				var a = sr.NextDouble() * Math.PI * 2;
				var speed = 0.4f + (float)sr.NextDouble() * 0.6f;
				var reach = impact * (0.4f + 1.6f * t) * speed;
				var sdir = new float3((float)Math.Cos(a), (float)Math.Sin(a) * 0.6f + 0.25f * t, 0);
				var tail = end + reach * sdir;
				var head = end + (reach + impact * 0.2f * speed) * sdir;
				cr.DrawLine(tail, head, Math.Max(1, width * 0.2f), Alpha(info.CoreColor, (1 - t) * 0.9f));
			}
		}

		void Flare(RgbaColorRenderer cr, float3 at, float radius, float intensity)
		{
			const int Rings = 5;
			for (var i = Rings; i >= 1; i--)
			{
				var f = (float)i / Rings;
				var r = radius * f;
				var c = Alpha(Mix(info.Color, info.GlowColor, f), (1.15f - f) * intensity * 0.75f);
				cr.FillEllipse(at - new float3(r, r * 0.75f, 0), at + new float3(r, r * 0.75f, 0), c);
			}

			var core = radius * 0.25f;
			cr.FillEllipse(at - new float3(core, core * 0.75f, 0), at + new float3(core, core * 0.75f, 0), Alpha(info.CoreColor, intensity));
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
