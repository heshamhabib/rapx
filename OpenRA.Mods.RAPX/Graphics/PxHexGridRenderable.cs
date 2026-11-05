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
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Graphics
{
	/// <summary>
	/// An area drawn as a hologram hexagon grid lying on the ground: faint near the centre and stronger towards the edge,
	/// a glowing outline around the outer hexes, a pulse that lights the hexes as it rolls outwards, a few twinkling cells
	/// and a crisp ring at the exact radius. Drawn in view space during the annotation pass (alpha blending only).
	/// Lite = quieter version for showing several areas at once (no pulse or twinkle). The hex pattern is squashed
	/// vertically by <c>tilt</c> (sin of the camera elevation) so the cells look like they lie on the ground as the
	/// HD art camera sees it; the outer ring stays a true circle because that is the real radius in cells.
	/// </summary>
	public class PxHexGridRenderable : IRenderable, IFinalizedRenderable
	{
		const int RimSegments = 96;
		static readonly Color Shadow = Color.FromArgb(110, 0, 0, 0);

		// Axial hex neighbours in edge order: edge e joins corners e and e + 1 and faces neighbour e.
		static readonly int2[] Neighbours = { new(1, 0), new(0, 1), new(-1, 1), new(-1, 0), new(0, -1), new(1, -1) };

		readonly WDist radius;
		readonly WDist hexSize;
		readonly Color color;
		readonly float opacity;
		readonly bool lite;
		readonly float tilt;
		readonly float cellOpacity;
		readonly float rimWidth;

		// cellOpacity multiplies the cell fills and hex lines only (lower = more see-through grid);
		// rimWidth thickens the ring at the exact radius (bold outline).
		public PxHexGridRenderable(WPos centerPosition, WDist radius, WDist hexSize, Color color, float opacity, bool lite, float tilt = 1f,
			float cellOpacity = 1f, float rimWidth = 1f)
		{
			Pos = centerPosition;
			this.radius = radius;
			this.hexSize = hexSize;
			this.color = color;
			this.opacity = opacity;
			this.lite = lite;
			this.tilt = tilt;
			this.cellOpacity = cellOpacity;
			this.rimWidth = rimWidth;
		}

		public WPos Pos { get; }
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxHexGridRenderable(Pos + vec, radius, hexSize, color, opacity, lite, tilt, cellOpacity, rimWidth); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }

		public void Render(WorldRenderer wr)
		{
			// Linear world -> view mapping (see PxRangeDomeRenderable): per-vertex int projection would jitter.
			var scale = wr.Viewport.Zoom / Game.Settings.Graphics.UIScale;
			var o = wr.Viewport.WorldToViewPx(wr.ScreenPosition(Pos));
			var centre = new float2(o.X, o.Y);
			var ux = scale * wr.ScreenVectorComponents(new WVec(1024, 0, 0)) / 1024f;
			var uy = scale * wr.ScreenVectorComponents(new WVec(0, 1024, 0)) / 1024f;
			if (ux.X * radius.Length < 4)
				return;

			float3 Ground(float x, float y) => new(centre.X + x * ux.X + y * uy.X, centre.Y + x * ux.Y + y * uy.Y, 0);

			var time = Game.RunTime / 1000f;
			var cr = Game.Renderer.RgbaColorRenderer;
			var hot = Lerp(color, Color.White, 0.55f);
			var a = opacity;
			var r = (float)radius.Length;
			var s = (float)hexSize.Length;

			// Flat-topped hexes in axial coordinates; keep the ones whose centre lies inside the radius
			// (minus a little so no hex pokes far past the ring).
			var reach = (int)MathF.Ceiling(r / (MathF.Min(1.5f, tilt) * s)) + 2;
			var limit = r - 0.35f * s;
			var cells = new HashSet<int2>();
			for (var q = -reach; q <= reach; q++)
				for (var rr = -reach; rr <= reach; rr++)
					if (Length(HexCentre(q, rr, s, tilt)) <= limit)
						cells.Add(new int2(q, rr));

			var pulse = Frac(time / 2.6f);
			var pulseRadius = pulse * r;
			var corners = new float2[6];
			var view = new float3[6];
			var outline = Lerp(color, Color.Black, 0.7f);

			foreach (var cell in cells)
			{
				var c = HexCentre(cell.X, cell.Y, s, tilt);
				var d = Length(c) / r;
				for (var i = 0; i < 6; i++)
				{
					var angle = MathF.PI / 3 * i;
					corners[i] = new float2(c.X + 0.94f * s * MathF.Cos(angle), c.Y + 0.94f * s * tilt * MathF.Sin(angle));
					view[i] = Ground(corners[i].X, corners[i].Y);
				}

				// Cell fill: clear around the building (annotations draw over it), a faint base that grows towards the edge,
				// the pulse front and the odd twinkling cell.
				var clear = Math.Clamp((d - 0.12f) / 0.2f, 0, 1);
				var fill = 22 * d * d;
				if (!lite)
				{
					var front = 1 - MathF.Min(1, MathF.Abs(Length(c) - pulseRadius) / (1.2f * s));
					fill += 42 * front * front * (1 - pulse * 0.6f);

					var seed = Hash(cell.X, cell.Y);
					var twinkle = MathF.Sin(time * (0.7f + seed * 0.6f) + seed * 40);
					if (seed > 0.8f && twinkle > 0.96f)
						fill += 40 * (twinkle - 0.96f) / 0.04f;
				}

				fill *= clear;

				var fc = WithAlpha(color, fill * a * cellOpacity);
				cr.FillRect(view[0], view[1], view[2], view[3], fc, fc, fc, fc);
				cr.FillRect(view[3], view[4], view[5], view[0], fc, fc, fc, fc);

				// Edges (cells are inset, so neighbours never share a line); edges with no neighbour form the border.
				for (var e = 0; e < 6; e++)
				{
					var border = !cells.Contains(cell + Neighbours[e]);
					var p = view[e];
					var q = view[(e + 1) % 6];
					if (border)
					{
						cr.DrawLine(p, q, 5f, WithAlpha(color, 40 * a * cellOpacity));
						cr.DrawLine(p, q, 2.6f, WithAlpha(outline, 120 * a * cellOpacity));
						cr.DrawLine(p, q, 1.4f, WithAlpha(hot, 220 * a * cellOpacity));
					}
					else
					{
						// Dark underline so the bright line still reads on snow
						var edgeAlpha = ((lite ? 30 : 45) + (lite ? 80 : 130) * d * d) * (0.35f + 0.65f * clear);
						cr.DrawLine(p, q, 2.6f, WithAlpha(outline, edgeAlpha * 0.45f * a * cellOpacity));
						cr.DrawLine(p, q, 1.1f, WithAlpha(hot, edgeAlpha * a * cellOpacity));
					}
				}
			}

			// Exact radius: dark outline for contrast on snow, soft glow, bright core and (full mode) running highlights.
			var rim = new float3[RimSegments];
			for (var i = 0; i < RimSegments; i++)
			{
				var t = MathF.PI * 2 * i / RimSegments;
				rim[i] = Ground(r * MathF.Cos(t), r * MathF.Sin(t));
			}

			cr.DrawPolygon(rim, 6f * rimWidth, WithAlpha(color, 35 * a * MathF.Min(2, rimWidth)));
			cr.DrawPolygon(rim, 3f * rimWidth, WithAlpha(Shadow, Shadow.A * a));
			cr.DrawPolygon(rim, 1.4f * rimWidth, WithAlpha(hot, 210 * a));
			if (lite)
				return;

			for (var k = 0; k < 3; k++)
			{
				var t = -time * 0.4f + k * MathF.PI * 2 / 3;
				const int Arc = 10;
				for (var i = 0; i < Arc; i++)
				{
					var f = MathF.Sin(MathF.PI * (i + 0.5f) / Arc);
					var t0 = t + i * 0.035f;
					var t1 = t0 + 0.035f;
					cr.DrawLine(Ground(r * MathF.Cos(t0), r * MathF.Sin(t0)), Ground(r * MathF.Cos(t1), r * MathF.Sin(t1)),
						2.4f * rimWidth, WithAlpha(Color.White, 230 * a * f));
				}
			}
		}

		static float2 HexCentre(int q, int r, float size, float tilt)
		{
			return new float2(size * 1.5f * q, tilt * size * MathF.Sqrt(3) * (r + q / 2f));
		}

		static float Hash(int x, int y)
		{
			var h = (uint)(x * 374761393 + y * 668265263);
			h = (h ^ (h >> 13)) * 1274126177;
			return (h ^ (h >> 16)) / (float)uint.MaxValue;
		}

		static float Length(in float2 v) { return MathF.Sqrt(v.X * v.X + v.Y * v.Y); }
		static float Frac(float v) { return v - MathF.Floor(v); }
		static Color WithAlpha(Color c, float alpha) { return Color.FromArgb((int)Math.Clamp(alpha, 0, 255), c.R, c.G, c.B); }

		static Color Lerp(Color a, Color b, float t)
		{
			return Color.FromArgb(a.A, (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}
	}
}
