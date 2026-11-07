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
	/// Building placement footprint drawn as a hologram pad of small hexagons lying on the ground: a dark contact
	/// shadow, hex cells cut to the footprint rectangle, a scan band that sweeps across the pad, a glowing outline
	/// around the cells and (optionally) bright corner brackets around the whole building footprint.
	/// Blocked cells pulse. Drawn in world space (above-shroud pass), so the caller's yield order decides whether it
	/// sits under or over the building preview. The hex lattice is anchored to the footprint's top-left corner so the
	/// pattern moves with the building, and squashed vertically by <c>tilt</c> like the other RAPX hex grids.
	/// </summary>
	public class PxFootprintHexRenderable : IRenderable, IFinalizedRenderable
	{
		readonly (int X, int Y, bool Invalid, float Alpha)[] cells;
		readonly int2 bounds;
		readonly WDist hexSize;
		readonly Color validColor;
		readonly Color invalidColor;
		readonly float tilt;
		readonly bool brackets;

		// origin = ground position of the top-left corner of the footprint's bounding box; cells = the cells to draw,
		// as offsets from it; bounds = size of the whole footprint's box in cells (hex clip and brackets).
		public PxFootprintHexRenderable(WPos origin, (int X, int Y, bool Invalid, float Alpha)[] cells, int2 bounds, WDist hexSize,
			Color validColor, Color invalidColor, float tilt, bool brackets)
		{
			Pos = origin;
			this.cells = cells;
			this.bounds = bounds;
			this.hexSize = hexSize;
			this.validColor = validColor;
			this.invalidColor = invalidColor;
			this.tilt = tilt;
			this.brackets = brackets;
		}

		public WPos Pos { get; }
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec)
		{
			return new PxFootprintHexRenderable(Pos + vec, cells, bounds, hexSize, validColor, invalidColor, tilt, brackets);
		}

		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }

		public void Render(WorldRenderer wr)
		{
			if (cells.Length == 0)
				return;

			var cr = Game.Renderer.WorldRgbaColorRenderer;
			var o = wr.Screen3DPosition(Pos);
			var ux = wr.Screen3DPosition(Pos + new WVec(1024, 0, 0)) - o;
			var uy = wr.Screen3DPosition(Pos + new WVec(0, 1024, 0)) - o;
			var cellPx = ux.X;
			if (cellPx < 2)
				return;

			// Ground position in cell units (x right, y down) -> world screen position
			float3 Ground(float x, float y) => new(o.X + x * ux.X + y * uy.X, o.Y + x * ux.Y + y * uy.Y, o.Z + x * ux.Z + y * uy.Z);

			var time = Game.RunTime / 1000f;
			var px = cellPx / 24f;
			var lookup = new Dictionary<int2, (bool Invalid, float Alpha)>(cells.Length);
			foreach (var (x, y, invalid, alpha) in cells)
				lookup[new int2(x, y)] = (invalid, alpha);

			// Contact shadow under each cell so the pad reads on bright snow
			foreach (var (x, y, _, alpha) in cells)
				cr.FillRect(Ground(x, y), Ground(x + 1, y), Ground(x + 1, y + 1), Ground(x, y + 1), Color.FromArgb((int)(70 * alpha), 4, 8, 14));

			// Flat-topped hexes in cell units, anchored at the footprint origin. Keep every hex that touches a drawn cell
			// (by its centre clamped into the box), and cut its corners to the footprint box so the edge rows are flush.
			var s = hexSize.Length / 1024f;
			var rowStep = tilt * s * MathF.Sqrt(3);
			var cols = (int)MathF.Ceiling(bounds.X / (1.5f * s)) + 1;
			var rows = (int)MathF.Ceiling(bounds.Y / rowStep) + 2;
			var corners = new float3[6];
			var scan = Frac(time / 2.4f) * (bounds.X + bounds.Y + 2) - 1;
			var pulse = 0.5f + 0.5f * MathF.Sin(time * 7f);

			for (var q = 0; q <= cols; q++)
			{
				for (var r = -1; r <= rows; r++)
				{
					var cx = 1.5f * s * q;
					var cy = rowStep * (r + (q & 1) * 0.5f);
					var kx = Math.Clamp(cx, 0.001f, bounds.X - 0.001f);
					var ky = Math.Clamp(cy, 0.001f, bounds.Y - 0.001f);
					if (MathF.Abs(kx - cx) > s || MathF.Abs(ky - cy) > rowStep * 0.5f)
						continue;

					if (!lookup.TryGetValue(new int2((int)kx, (int)ky), out var cell))
						continue;

					var color = cell.Invalid ? invalidColor : validColor;
					var hot = Lerp(color, Color.White, 0.6f);
					var dark = Lerp(color, Color.Black, 0.75f);
					for (var i = 0; i < 6; i++)
					{
						var angle = MathF.PI / 3 * i;
						var x = Math.Clamp(cx + 0.9f * s * MathF.Cos(angle), 0, bounds.X);
						var y = Math.Clamp(cy + 0.9f * s * tilt * MathF.Sin(angle), 0, bounds.Y);
						corners[i] = Ground(x, y);
					}

					// Fill: base tint brighter towards the pad edge, the diagonal scan band, a rare twinkle; blocked cells pulse.
					var edge = 1 - MathF.Min(1, MathF.Min(MathF.Min(cx, bounds.X - cx), MathF.Min(cy, bounds.Y - cy)) / 1.2f);
					var band = 1 - MathF.Min(1, MathF.Abs(cx + cy - scan) / 0.6f);
					var fill = 34 + 30 * edge + 70 * band * band;
					var seed = Hash(q, r);
					var twinkle = MathF.Sin(time * (0.8f + seed) + seed * 40);
					if (seed > 0.75f && twinkle > 0.9f)
						fill += 60 * (twinkle - 0.9f) / 0.1f;

					if (cell.Invalid)
						fill = 70 + 40 * edge + 60 * pulse + 40 * band;

					var fc = WithAlpha(color, fill * cell.Alpha);
					cr.FillRect(corners[0], corners[1], corners[2], corners[3], fc);
					cr.FillRect(corners[3], corners[4], corners[5], corners[0], fc);

					var lineAlpha = (120 + 100 * edge + 35 * band) * cell.Alpha;
					cr.DrawPolygon(corners, 2.2f * px, WithAlpha(dark, lineAlpha * 0.5f));
					cr.DrawPolygon(corners, 0.9f * px, WithAlpha(hot, lineAlpha));
				}
			}

			// Outline: cell edges with no drawn neighbour. Wide soft glow, dark contour for contrast, bright core.
			var outline = new List<(float3 A, float3 B, Color C, float Alpha)>();
			foreach (var (x, y, invalid, alpha) in cells)
			{
				var color = invalid ? invalidColor : validColor;
				if (!lookup.ContainsKey(new int2(x, y - 1)))
					outline.Add((Ground(x, y), Ground(x + 1, y), color, alpha));
				if (!lookup.ContainsKey(new int2(x + 1, y)))
					outline.Add((Ground(x + 1, y), Ground(x + 1, y + 1), color, alpha));
				if (!lookup.ContainsKey(new int2(x, y + 1)))
					outline.Add((Ground(x + 1, y + 1), Ground(x, y + 1), color, alpha));
				if (!lookup.ContainsKey(new int2(x - 1, y)))
					outline.Add((Ground(x, y + 1), Ground(x, y), color, alpha));
			}

			foreach (var (a, b, c, alpha) in outline)
				cr.DrawLine(a, b, 7f * px, WithAlpha(c, 45 * alpha));
			foreach (var (a, b, _, alpha) in outline)
				cr.DrawLine(a, b, 3.2f * px, WithAlpha(Color.Black, 110 * alpha));
			foreach (var (a, b, c, alpha) in outline)
				cr.DrawLine(a, b, 1.6f * px, WithAlpha(Lerp(c, Color.White, 0.45f), 235 * alpha));

			if (!brackets)
				return;

			// Corner brackets around the whole footprint, slightly outside it, breathing in and out
			var anyInvalid = Array.Exists(cells, c => c.Invalid);
			var bracketColor = Lerp(anyInvalid ? invalidColor : validColor, Color.White, 0.7f);
			var gap = 0.12f + 0.04f * MathF.Sin(time * 3f);
			var arm = MathF.Min(0.45f, 0.3f * MathF.Min(bounds.X, bounds.Y) + 0.15f);
			var x0 = -gap;
			var y0 = -gap;
			var x1 = bounds.X + gap;
			var y1 = bounds.Y + gap;
			foreach (var (cx, cy, dx, dy) in new[] { (x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1) })
			{
				var corner = Ground(cx, cy);
				var h = Ground(cx + dx * arm, cy);
				var v = Ground(cx, cy + dy * arm);
				cr.DrawLine(h, corner, 4.2f * px, WithAlpha(Color.Black, 120));
				cr.DrawLine(corner, v, 4.2f * px, WithAlpha(Color.Black, 120));
				cr.DrawLine(h, corner, 2f * px, WithAlpha(bracketColor, 250));
				cr.DrawLine(corner, v, 2f * px, WithAlpha(bracketColor, 250));
			}
		}

		static float Hash(int x, int y)
		{
			var h = (uint)(x * 374761393 + y * 668265263);
			h = (h ^ (h >> 13)) * 1274126177;
			return (h ^ (h >> 16)) / (float)uint.MaxValue;
		}

		static float Frac(float v) { return v - MathF.Floor(v); }
		static Color WithAlpha(Color c, float alpha) { return Color.FromArgb((int)Math.Clamp(alpha, 0, 255), c.R, c.G, c.B); }

		static Color Lerp(Color a, Color b, float t)
		{
			return Color.FromArgb(a.A, (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}
	}
}
