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
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Traits.Render;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Graphics
{
	/// <summary>
	/// Draws the whole rally point in one pass so the layers always stack correctly: ground emblem, pulse rings,
	/// the energy beam (shadow, glow, core, running pulses and chevrons, waypoint diamonds) and the waving banner on top.
	/// </summary>
	public class PxRallyPointRenderable : IRenderable, IFinalizedRenderable
	{
		const int EllipseSegments = 48;

		static readonly Color BeamShadow = Color.FromArgb(70, 0, 0, 0);

		readonly WPos[] nodes;
		readonly PxRallyPointInfo info;
		readonly ISpriteSequence flag;
		readonly ISpriteSequence emblem;
		readonly PaletteReference palette;
		readonly Color color;
		readonly bool showLine;

		public PxRallyPointRenderable(WPos[] nodes, PxRallyPointInfo info, ISpriteSequence flag, ISpriteSequence emblem,
			PaletteReference palette, Color color, bool showLine)
		{
			this.nodes = nodes;
			this.info = info;
			this.flag = flag;
			this.emblem = emblem;
			this.palette = palette;
			this.color = color;
			this.showLine = showLine;
		}

		public WPos Pos => nodes[^1];
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec)
		{
			var offset = vec;
			return new PxRallyPointRenderable(nodes.Select(n => n + offset).ToArray(), info, flag, emblem, palette, color, showLine);
		}

		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		public void Render(WorldRenderer wr)
		{
			var points = nodes.Select(wr.Screen3DPxPosition).ToArray();
			var end = points[^1];
			var time = Game.RunTime / 1000f;
			var wsr = Game.Renderer.WorldSpriteRenderer;

			var baseSprite = emblem.GetSprite(0);
			wsr.DrawSprite(baseSprite, palette, end - 0.5f * emblem.Scale * baseSprite.Size, emblem.Scale);

			DrawPulseRings(end, time);

			if (showLine)
				DrawBeam(points, time);

			var frame = (int)(Game.RunTime / Math.Max(1, flag.Tick)) % flag.Length;
			var flagSprite = flag.GetSprite(frame);
			wsr.DrawSprite(flagSprite, palette, end - flag.Scale * new float3(info.FlagAnchor.X, info.FlagAnchor.Y, 0), flag.Scale);
		}

		void DrawPulseRings(float3 centre, float time)
		{
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			for (var k = 0; k < 2; k++)
			{
				var p = Frac(time / 1.8f + k * 0.5f);
				var rx = info.RingRadius * (0.55f + 0.85f * p);
				var fade = (1 - p) * (1 - p);
				var ellipse = Ellipse(centre, rx, rx * info.RingRatio);
				cr.DrawPolygon(ellipse, 2.6f * (1 - p) + 0.8f, WithAlpha(color, (int)(150 * fade)));
				cr.DrawPolygon(ellipse, 0.7f, WithAlpha(Lerp(color, Color.White, 0.6f), (int)(200 * fade)));
			}
		}

		void DrawBeam(float3[] points, float time)
		{
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			var w = info.LineWidth;
			var core = Lerp(color, Color.White, 0.3f);
			var hot = Lerp(color, Color.White, 0.8f);
			var outline = Lerp(color, Color.Black, 0.65f);

			// The last segment stops at the emblem rim so it never crosses the banner or the pole.
			var last = points.Length - 1;
			var tail = points[last - 1];
			var head = points[last];
			var d = head - tail;
			var len = d.XY.Length;
			var rimDistance = len > 0 ? RimDistance(d.X / len, d.Y / len) : 0;
			if (len <= rimDistance + 1)
				return;

			var trimmed = (float3[])points.Clone();
			trimmed[last] = head - rimDistance / len * d;

			var travelled = 0f;
			var shadowOffset = new float3(1f, 1.5f, 0);
			for (var i = 0; i < last; i++)
			{
				var a = trimmed[i];
				var b = trimmed[i + 1];
				var segment = b - a;
				var segmentLength = segment.XY.Length;
				if (segmentLength < 0.5f)
					continue;

				var dir = segment / segmentLength;
				var normal = new float3(-dir.Y, dir.X, 0);

				// Layers: ground shadow, coloured halo, dark outline (contrast on snow), core and hot centre.
				var fadeIn = i == 0 ? 0.25f : 1f;
				cr.DrawLine(a + shadowOffset, b + shadowOffset, w + 2f, Fade(BeamShadow, fadeIn), BeamShadow);
				cr.DrawLine(a, b, w * 4.5f, Fade(WithAlpha(color, 50), fadeIn), WithAlpha(color, 50));
				cr.DrawLine(a, b, w + 1.6f, Fade(WithAlpha(outline, 220), fadeIn), WithAlpha(outline, 220));
				cr.DrawLine(a, b, w, Fade(core, fadeIn), core);
				cr.DrawLine(a, b, w * 0.35f, Fade(WithAlpha(hot, 210), fadeIn), WithAlpha(hot, 210));

				// Energy pulses run from the building towards the flag; every third one is a chevron.
				var spacing = info.PulseSpacing;
				var shift = Frac(time * info.PulseSpeed / spacing) * spacing;
				var first = (int)Math.Ceiling((travelled - shift) / spacing);
				for (var n = first; n * spacing + shift <= travelled + segmentLength; n++)
				{
					var s = n * spacing + shift - travelled;
					if (s < 0)
						continue;

					var p = a + s * dir;
					var edgeFade = Math.Min(1f, Math.Min(travelled + s, segmentLength - s + (i < last - 1 ? spacing : 0)) / 8f);
					var alpha = (int)(230 * Math.Clamp(edgeFade, 0, 1));
					if (alpha <= 0)
						continue;

					if (n % 3 == 0)
					{
						const float Arm = 2.6f;
						var back = p - Arm * dir;
						cr.DrawLine(back + Arm * normal, p, 2.1f, WithAlpha(outline, alpha));
						cr.DrawLine(back - Arm * normal, p, 2.1f, WithAlpha(outline, alpha));
						cr.DrawLine(back + Arm * normal, p, 0.9f, WithAlpha(Color.White, alpha));
						cr.DrawLine(back - Arm * normal, p, 0.9f, WithAlpha(Color.White, alpha));
					}
					else
					{
						var trail = Math.Min(7f, s);
						cr.DrawLine(p - trail * dir, p, w * 1.1f, WithAlpha(hot, 0), WithAlpha(Color.White, alpha));
					}
				}

				travelled += segmentLength;
			}

			// Exit node at the building and diamonds on intermediate waypoints.
			var glow = 0.5f + 0.5f * (float)Math.Sin(time * 4);
			DrawDiamond(cr, trimmed[0], 2.4f, WithAlpha(core, (int)(160 + 80 * glow)), outline);
			for (var i = 1; i < last; i++)
				DrawDiamond(cr, trimmed[i], 3f + 0.6f * glow, core, outline);
		}

		static void DrawDiamond(RgbaColorRenderer cr, float3 c, float r, Color fill, Color edge)
		{
			var top = c + new float3(0, -r * 0.8f, 0);
			var right = c + new float3(r, 0, 0);
			var bottom = c + new float3(0, r * 0.8f, 0);
			var left = c + new float3(-r, 0, 0);
			cr.FillRect(top, right, bottom, left, fill);
			cr.DrawPolygon(new[] { top, right, bottom, left }, 0.9f, edge);
		}

		// Distance from the ellipse centre to its rim along a unit screen direction.
		float RimDistance(float dx, float dy)
		{
			var rx = info.RingRadius;
			var ry = info.RingRadius * info.RingRatio;
			return 1f / (float)Math.Sqrt(dx * dx / (rx * rx) + dy * dy / (ry * ry));
		}

		static float3[] Ellipse(float3 c, float rx, float ry)
		{
			var points = new float3[EllipseSegments];
			for (var i = 0; i < EllipseSegments; i++)
			{
				var t = i * 2 * Math.PI / EllipseSegments;
				points[i] = c + new float3((float)(rx * Math.Cos(t)), (float)(ry * Math.Sin(t)), 0);
			}

			return points;
		}

		static float Frac(float x) { return x - (float)Math.Floor(x); }

		static Color Fade(Color c, float f) { return WithAlpha(c, (int)(c.A * f)); }

		static Color WithAlpha(Color c, int a) { return Color.FromArgb(Math.Clamp(a, 0, 255), c.R, c.G, c.B); }

		static Color Lerp(Color a, Color b, float t)
		{
			return Color.FromArgb(
				(int)(a.A + (b.A - a.A) * t),
				(int)(a.R + (b.R - a.R) * t),
				(int)(a.G + (b.G - a.G) * t),
				(int)(a.B + (b.B - a.B) * t));
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
