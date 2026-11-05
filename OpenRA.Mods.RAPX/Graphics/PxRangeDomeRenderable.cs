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
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Graphics
{
	public readonly struct PxRangeDomeStyle
	{
		public readonly Color Color;
		public readonly float DomeHeight;
		public readonly float Opacity;
		public readonly bool Lite;

		public PxRangeDomeStyle(Color color, float domeHeight, float opacity, bool lite)
		{
			Color = color;
			DomeHeight = domeHeight;
			Opacity = opacity;
			Lite = lite;
		}

		public PxRangeDomeStyle AsLite() { return new PxRangeDomeStyle(Color, DomeHeight, Opacity * 0.6f, true); }
	}

	/// <summary>
	/// Weapon coverage drawn as a translucent glass hemisphere: gradient ground footprint with a radar sweep and pulse,
	/// a Fresnel-lit shell with a specular highlight, faint meridians, a rising scan line and a crisp rim at the exact range.
	/// Drawn in view space during the annotation pass (alpha blending only, additive glow vanishes on snow).
	/// </summary>
	public class PxRangeDomeRenderable : IRenderable, IFinalizedRenderable
	{
		const int Segments = 64;
		const int Bands = 10;
		const int Meridians = 24;
		const int Latitudes = 6;

		static readonly float3 ViewDir = Normalize(new float3(0, 1, 1));
		static readonly float3 LightDir = Normalize(new float3(-0.55f, -0.35f, 0.75f));
		static readonly float3 HalfDir = Normalize(LightDir + ViewDir);
		static readonly Color Shadow = Color.FromArgb(110, 0, 0, 0);

		readonly WDist radius;
		readonly PxRangeDomeStyle style;

		public PxRangeDomeRenderable(WPos centerPosition, WDist radius, PxRangeDomeStyle style)
		{
			Pos = centerPosition;
			this.radius = radius;
			this.style = style;
		}

		public WPos Pos { get; }
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxRangeDomeRenderable(Pos + vec, radius, style); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }

		public void Render(WorldRenderer wr)
		{
			// Linear world -> view mapping; projecting every vertex through the int viewport API would make it jitter.
			var scale = wr.Viewport.Zoom / Game.Settings.Graphics.UIScale;
			var o = wr.Viewport.WorldToViewPx(wr.ScreenPosition(Pos));
			var centre = new float2(o.X, o.Y);
			var ex = scale * wr.ScreenVectorComponents(new WVec(radius.Length, 0, 0));
			var ey = scale * wr.ScreenVectorComponents(new WVec(0, radius.Length, 0));
			var ez = scale * wr.ScreenVectorComponents(new WVec(0, 0, radius.Length));
			var rx = ex.X;
			var ry = ey.Y;
			var rz = -ez.Y * style.DomeHeight;
			if (rx < 2)
				return;

			var time = Game.RunTime / 1000f;
			var cr = Game.Renderer.RgbaColorRenderer;
			var c = style.Color;
			var a = style.Opacity;
			var hot = Lerp(c, Color.White, 0.55f);

			float3 Ground(float r, float theta) => new(centre.X + r * rx * MathF.Cos(theta), centre.Y + r * ry * MathF.Sin(theta), 0);
			float3 Dome(float phi, float theta) => new(
				centre.X + rx * MathF.Cos(phi) * MathF.Cos(theta),
				centre.Y + ry * MathF.Cos(phi) * MathF.Sin(theta) - rz * MathF.Sin(phi), 0);

			// Ground footprint: clear centre, denser towards the edge so the covered disc reads at a glance.
			float[] rings = { 0f, 0.45f, 0.78f, 0.93f, 1f };
			float[] ringAlpha = { 6, 12, 24, 44, 70 };
			for (var k = 0; k < rings.Length - 1; k++)
			{
				var inner = WithAlpha(c, ringAlpha[k] * a);
				var outer = WithAlpha(c, ringAlpha[k + 1] * a);
				for (var i = 0; i < Segments; i++)
				{
					var t0 = Angle(i);
					var t1 = Angle(i + 1);
					cr.FillRect(Ground(rings[k], t0), Ground(rings[k], t1), Ground(rings[k + 1], t1), Ground(rings[k + 1], t0),
						inner, inner, outer, outer);
				}
			}

			// Range ticks at 1/3 and 2/3 of the reach.
			for (var k = 1; k <= 2; k++)
				cr.DrawPolygon(Ring(k / 3f, Ground), 1f, WithAlpha(c, 34 * a));

			if (!style.Lite)
			{
				// Radar sweep: a wedge that fades behind the leading edge.
				const float Sweep = 1.1f;
				var lead = time * 1.6f;
				const int SweepSteps = 18;
				for (var i = 0; i < SweepSteps; i++)
				{
					var t0 = lead - Sweep * i / SweepSteps;
					var t1 = lead - Sweep * (i + 1) / SweepSteps;
					var f0 = 1 - (float)i / SweepSteps;
					var f1 = 1 - (float)(i + 1) / SweepSteps;
					var e0 = WithAlpha(c, 70 * a * f0 * f0);
					var e1 = WithAlpha(c, 70 * a * f1 * f1);
					var mid = Ground(0, 0);
					cr.FillRect(mid, Ground(1, t0), Ground(1, t1), mid, WithAlpha(c, 0), e0, e1, WithAlpha(c, 0));
				}

				cr.DrawLine(Ground(0.05f, lead), Ground(1, lead), 1.4f, WithAlpha(hot, 0), WithAlpha(hot, 200 * a));

				// Pulse expanding from the weapon to the rim.
				var p = Frac(time / 2.4f);
				cr.DrawPolygon(Ring(p, Ground), 2.2f, WithAlpha(hot, 110 * a * (1 - p) * MathF.Min(1, p * 6)));
			}

			// Glass shell: back faces first, then front faces with Fresnel rim and specular highlight.
			if (!style.Lite && rz > 1)
			{
				DrawShell(cr, Dome, false, c, a);
				DrawShell(cr, Dome, true, c, a);

				DrawGrid(cr, Dome, hot, a);

				// Silhouette: where the shell turns away from the camera (n.v = 0, i.e. tan(phi) = -k sin(theta)) on the far side.
				var k = Math.Max(0.05f, style.DomeHeight);
				var edge = new float3[Segments / 2 + 1];
				for (var i = 0; i <= Segments / 2; i++)
				{
					var theta = MathF.PI + Angle(i);
					edge[i] = Dome(MathF.Atan(-k * MathF.Sin(theta)), theta);
				}

				cr.DrawLine(edge, 6f, WithAlpha(c, 40 * a), true);
				cr.DrawLine(edge, 1.4f, WithAlpha(hot, 200 * a), true);

				// Scan line climbing the dome.
				var s = Frac(time / 3.2f);
				DrawLatitude(cr, Dome, s * MathF.PI / 2 * 0.92f, 1.8f, Color.White, 170 * a * MathF.Sin(MathF.PI * s));
			}

			// Exact range: dark outline for contrast on snow, soft glow, bright core and running highlights.
			var rim = Ring(1, Ground);
			cr.DrawPolygon(rim, 7f, WithAlpha(c, 45 * a));
			cr.DrawPolygon(rim, 3.2f, WithAlpha(Shadow, Shadow.A * a));
			cr.DrawPolygon(rim, 1.6f, WithAlpha(hot, 235 * a));
			for (var k = 0; k < 3; k++)
			{
				var t = -time * 0.5f + k * MathF.PI * 2 / 3;
				const int Arc = 8;
				for (var i = 0; i < Arc; i++)
				{
					var f = MathF.Sin(MathF.PI * (i + 0.5f) / Arc);
					cr.DrawLine(Ground(1, t + i * 0.04f), Ground(1, t + (i + 1) * 0.04f), 2.4f, WithAlpha(Color.White, 230 * a * f));
				}
			}
		}

		void DrawShell(RgbaColorRenderer cr, Func<float, float, float3> dome, bool front, Color c, float a)
		{
			for (var b = 0; b < Bands; b++)
			{
				var p0 = MathF.PI / 2 * b / Bands;
				var p1 = MathF.PI / 2 * (b + 1) / Bands;
				for (var i = 0; i < Segments; i++)
				{
					var t0 = Angle(i);
					var t1 = Angle(i + 1);
					if (Facing((p0 + p1) / 2, (t0 + t1) / 2) >= 0 != front)
						continue;

					cr.FillRect(dome(p0, t0), dome(p0, t1), dome(p1, t1), dome(p1, t0),
						Shade(p0, t0, c, a), Shade(p0, t1, c, a), Shade(p1, t1, c, a), Shade(p1, t0, c, a));
				}
			}
		}

		// Latitude/longitude grid: lines on the near side are bright with a dark outline, lines seen through the glass are dim.
		void DrawGrid(RgbaColorRenderer cr, Func<float, float, float3> dome, Color color, float a)
		{
			var outline = WithAlpha(Lerp(style.Color, Color.Black, 0.7f), 0);
			void Segment(float3 p, float3 q, float phi, float theta, float weight)
			{
				var front = Facing(phi, theta) >= 0;
				var fresnel = 1 - MathF.Abs(Facing(phi, theta));
				var alpha = (front ? 120 + 110 * fresnel : 48) * weight * a;
				if (front)
					cr.DrawLine(p, q, 3f, WithAlpha(outline, alpha * 0.55f));

				cr.DrawLine(p, q, front ? 1.4f : 1f, WithAlpha(color, alpha));
			}

			for (var l = 1; l < Latitudes; l++)
			{
				var phi = MathF.PI / 2 * l / Latitudes;
				for (var i = 0; i < Segments; i++)
				{
					var t0 = Angle(i);
					var t1 = Angle(i + 1);
					Segment(dome(phi, t0), dome(phi, t1), phi, (t0 + t1) / 2, 1);
				}
			}

			const int Steps = 18;
			for (var m = 0; m < Meridians; m++)
			{
				// Every other meridian stops short of the pole so the top does not turn into a solid knot.
				var theta = MathF.PI * 2 * m / Meridians;
				var top = m % 2 == 0 ? MathF.PI / 2 : MathF.PI / 2 * (Latitudes - 1) / Latitudes;
				for (var j = 0; j < Steps; j++)
				{
					var p0 = top * j / Steps;
					var p1 = top * (j + 1) / Steps;
					var weight = 0.45f + 0.55f * MathF.Cos((p0 + p1) / 2);
					Segment(dome(p0, theta), dome(p1, theta), (p0 + p1) / 2, theta, weight);
				}
			}
		}

		void DrawLatitude(RgbaColorRenderer cr, Func<float, float, float3> dome, float phi, float width, Color color, float alpha)
		{
			if (alpha < 1)
				return;

			for (var i = 0; i < Segments; i++)
			{
				var t0 = Angle(i);
				var t1 = Angle(i + 1);
				var f = Facing(phi, (t0 + t1) / 2) >= 0 ? 1f : 0.35f;
				cr.DrawLine(dome(phi, t0), dome(phi, t1), width, WithAlpha(color, alpha * f));
			}
		}

		// Normal of the flattened hemisphere (an ellipsoid with z scaled by DomeHeight).
		float3 Normal(float phi, float theta)
		{
			var k = Math.Max(0.05f, style.DomeHeight);
			return Normalize(new float3(MathF.Cos(phi) * MathF.Cos(theta), MathF.Cos(phi) * MathF.Sin(theta), MathF.Sin(phi) / k));
		}

		float Facing(float phi, float theta) { return Dot(Normal(phi, theta), ViewDir); }

		Color Shade(float phi, float theta, Color c, float a)
		{
			var n = Normal(phi, theta);
			var ndv = Dot(n, ViewDir);
			var fresnel = MathF.Pow(1 - MathF.Abs(ndv), 2.2f);
			var fresnel2 = MathF.Pow(1 - MathF.Abs(ndv), 2.6f);
			var spec = MathF.Pow(MathF.Max(0, Dot(n, HalfDir)), 48);
			var light = MathF.Max(0, Dot(n, LightDir));
			var alpha = (5 + 85 * fresnel2 + 22 * light) * (ndv >= 0 ? 1f : 0.4f) + 95 * spec;
			var lit = Lerp(Lerp(c, Color.Black, 0.45f * (1 - light)), Color.White, MathF.Min(1, 0.1f + 0.4f * fresnel * light + spec));
			return WithAlpha(lit, alpha * a);
		}

		static float3[] Ring(float r, Func<float, float, float3> ground)
		{
			var points = new float3[Segments];
			for (var i = 0; i < Segments; i++)
				points[i] = ground(r, Angle(i));

			return points;
		}

		static float Angle(int i) { return MathF.PI * 2 * i / Segments; }
		static float Frac(float v) { return v - MathF.Floor(v); }
		static float Dot(in float3 a, in float3 b) { return a.X * b.X + a.Y * b.Y + a.Z * b.Z; }
		static float3 Normalize(in float3 v) { return v / MathF.Sqrt(Dot(v, v)); }

		static Color WithAlpha(Color c, float alpha) { return Color.FromArgb((int)Math.Clamp(alpha, 0, 255), c.R, c.G, c.B); }

		static Color Lerp(Color a, Color b, float t)
		{
			return Color.FromArgb(a.A, (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}
	}
}
