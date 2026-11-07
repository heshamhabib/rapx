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
using OpenRA.Mods.RAPX.Traits.Render;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Graphics
{
	public readonly struct PxAmmoBarRow
	{
		public readonly string Label;
		public readonly Color Color;
		public readonly int Current;
		public readonly int Max;

		// Progress of the round being added (0..1), or -1 when not refilling.
		public readonly float Refill;

		public PxAmmoBarRow(string label, Color color, int current, int max, float refill)
		{
			Label = label;
			Color = color;
			Current = current;
			Max = max;
			Refill = refill;
		}
	}

	/// <summary>
	/// Ammo panel under a selected aircraft (WithPxAmmoBars): a dark chamfered plate with one row per ammo type:
	/// coloured label, slanted bar (one cell per round, or continuous for big magazines) in the style of the
	/// health bars, round counter, a filling ghost cell while refilling and a red blink when a type is empty.
	/// </summary>
	public class PxAmmoBarsRenderable : IRenderable, IFinalizedRenderable
	{
		const int Pad = 3;
		const int Chamfer = 3;
		const int ColumnGap = 4;
		const int RowGap = 2;

		static readonly Color Plate = Color.FromArgb(170, 8, 10, 14);
		static readonly Color PlateRim = Color.FromArgb(200, 70, 76, 86);
		static readonly Color Shadow = Color.FromArgb(120, 0, 0, 0);
		static readonly Color RimTop = Color.FromArgb(240, 120, 128, 140);
		static readonly Color RimBottom = Color.FromArgb(240, 18, 20, 24);
		static readonly Color TrackTop = Color.FromArgb(235, 6, 8, 10);
		static readonly Color TrackBottom = Color.FromArgb(235, 34, 38, 44);
		static readonly Color Gloss = Color.FromArgb(110, 255, 255, 255);
		static readonly Color Tick = Color.FromArgb(150, 0, 0, 0);
		static readonly Color Empty = Color.FromArgb(255, 235, 45, 35);
		static readonly Color CountColor = Color.FromArgb(230, 225, 230, 238);

		readonly Rectangle decorationBounds;
		readonly PxAmmoBarRow[] rows;
		readonly SpriteFont font;
		readonly WithPxAmmoBarsInfo info;
		readonly float slope;

		public PxAmmoBarsRenderable(WPos pos, Rectangle decorationBounds, PxAmmoBarRow[] rows, SpriteFont font, WithPxAmmoBarsInfo info)
		{
			Pos = pos;
			this.decorationBounds = decorationBounds;
			this.rows = rows;
			this.font = font;
			this.info = info;
			slope = 0.5f;
		}

		public WPos Pos { get; }
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxAmmoBarsRenderable(Pos + vec, decorationBounds, rows, font, info); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		public void Render(WorldRenderer wr)
		{
			var bl = wr.Viewport.WorldToViewPx(new int2(decorationBounds.Left, decorationBounds.Bottom));
			var br = wr.Viewport.WorldToViewPx(new int2(decorationBounds.Right, decorationBounds.Bottom));

			// Columns: label | bar | counter. Rows are as tall as the font's capitals.
			var labelWidth = 0;
			var countWidth = 0;
			foreach (var r in rows)
			{
				labelWidth = Math.Max(labelWidth, font.Measure(r.Label).X);
				countWidth = Math.Max(countWidth, font.Measure(r.Max.ToString()).X);
			}

			var textHeight = font.Measure("0").Y;
			var rowHeight = Math.Max(textHeight - 2, info.BarHeight + 2);
			var width = Pad + labelWidth + ColumnGap + info.BarWidth + ColumnGap + countWidth + Pad;
			var height = Pad + rows.Length * rowHeight + (rows.Length - 1) * RowGap + Pad;

			var x0 = (bl.X + br.X) / 2 - width / 2;
			var y0 = bl.Y + info.Margin;
			DrawPlate(x0, y0, x0 + width, y0 + height);

			var blink = (float)(0.5 + 0.5 * Math.Sin(Game.RunTime / 110.0));
			var y = y0 + Pad;
			foreach (var r in rows)
			{
				var empty = r.Current == 0;
				var labelColor = empty ? Mix(Empty, Color.White, 0.2f * blink) : Lighten(r.Color, 0.2f);
				if (empty)
					labelColor = Color.FromArgb((int)(140 + 115 * blink), labelColor.R, labelColor.G, labelColor.B);

				var textY = y + (rowHeight - textHeight) / 2;
				font.DrawTextWithShadow(r.Label, new float2(x0 + Pad, textY), labelColor, Shadow, 1);

				var barX = x0 + Pad + labelWidth + ColumnGap;
				var barTop = y + (rowHeight - info.BarHeight) / 2;
				DrawBar(r, barX, barX + info.BarWidth, barTop, barTop + info.BarHeight, empty ? blink : 0);

				var count = r.Current.ToString();
				var countColor = empty ? labelColor : CountColor;
				font.DrawTextWithShadow(count, new float2(x0 + width - Pad - font.Measure(count).X, textY), countColor, Shadow, 1);

				y += rowHeight + RowGap;
			}
		}

		void DrawPlate(int x0, int y0, int x1, int y1)
		{
			var cr = Game.Renderer.RgbaColorRenderer;

			// Chamfered top-left and bottom-right corners.
			var o = new[]
			{
				new float3(x0 + Chamfer, y0, 0), new float3(x1, y0, 0), new float3(x1, y1 - Chamfer, 0),
				new float3(x1 - Chamfer, y1, 0), new float3(x0, y1, 0), new float3(x0, y0 + Chamfer, 0)
			};

			// The hexagon is convex: two quads cover it.
			cr.FillRect(o[0], o[1], o[2], o[3], Plate);
			cr.FillRect(o[0], o[3], o[4], o[5], Plate);
			cr.DrawPolygon(o, 1, PlateRim);
		}

		void DrawBar(in PxAmmoBarRow r, int x0, int x1, int top, int bottom, float emptyPulse)
		{
			var slantBase = bottom;

			Quad(x0 + 1, x1 + 1, top + 1, bottom + 1, slantBase, Shadow, Shadow);
			Quad(x0, x1, top, bottom, slantBase, RimTop, RimBottom);

			var it = top + 1;
			var ib = bottom - 1;
			var ix0 = x0 + 1;
			var ix1 = x1 - 1;
			var track0 = TrackTop;
			var track1 = TrackBottom;
			if (emptyPulse > 0)
			{
				track0 = Mix(TrackTop, Empty, 0.25f * emptyPulse);
				track1 = Mix(TrackBottom, Empty, 0.45f * emptyPulse);
			}

			Quad(ix0, ix1, it, ib, slantBase, track0, track1);

			if (r.Max <= 0)
				return;

			var width = ix1 - ix0;
			if (r.Max <= info.MaxCells)
			{
				// One cell per round, 1 px apart; the cell being refilled fills up as a ghost.
				var step = (float)(width + 1) / r.Max;
				for (var i = 0; i < r.Max; i++)
				{
					var c0 = ix0 + i * step;
					var c1 = ix0 + (i + 1) * step - 1;
					if (i < r.Current)
						DrawFill(c0, c1, it, ib, slantBase, r.Color);
					else if (i == r.Current && r.Refill >= 0)
						DrawGhost(c0, c0 + (c1 - c0) * r.Refill, it, ib, slantBase, r.Color);
				}

				return;
			}

			var fillEnd = ix0 + width * (float)r.Current / r.Max;
			DrawFill(ix0, fillEnd, it, ib, slantBase, r.Color);
			if (r.Refill >= 0)
				DrawGhost(fillEnd, fillEnd + width * r.Refill / r.Max, it, ib, slantBase, r.Color);

			// Quarter ticks on continuous bars.
			for (var q = 1; q < 4; q++)
			{
				var x = (float)Math.Round(ix0 + width * q / 4f);
				Quad(x, x + 1, it, ib, slantBase, Tick, Tick);
			}
		}

		void DrawFill(float x0, float x1, int top, int bottom, int slantBase, Color color)
		{
			if (x1 <= x0)
				return;

			var mid = top + (bottom - top) / 2f;
			Quad(x0, x1, top, mid, slantBase, Lighten(color, 0.45f), color);
			Quad(x0, x1, mid, bottom, slantBase, color, Darken(color, 0.45f));
			Quad(x0, x1, top, top + 1, slantBase, Gloss, Gloss);
		}

		void DrawGhost(float x0, float x1, int top, int bottom, int slantBase, Color color)
		{
			if (x1 <= x0)
				return;

			var pulse = (float)(0.5 + 0.5 * Math.Sin(Game.RunTime / 90.0));
			var c = Color.FromArgb((int)(90 + 70 * pulse), color.R, color.G, color.B);
			Quad(x0, x1, top, bottom, slantBase, Lighten(c, 0.3f), Darken(c, 0.3f));
			Quad(x1 - 1, x1, top, bottom, slantBase, Color.FromArgb(200, 255, 255, 255), Color.FromArgb(200, 255, 255, 255));
		}

		// Fills a slanted quad between base x positions x0..x1; each row is shifted right by slope * (slantBase - y).
		void Quad(float x0, float x1, float top, float bottom, int slantBase, Color topColor, Color bottomColor)
		{
			if (x1 <= x0 || bottom <= top)
				return;

			Game.Renderer.RgbaColorRenderer.FillRect(
				Point(x0, top, slantBase), Point(x1, top, slantBase), Point(x1, bottom, slantBase), Point(x0, bottom, slantBase),
				topColor, topColor, bottomColor, bottomColor);
		}

		float3 Point(float x, float y, int slantBase) { return new float3(x + slope * (slantBase - y), y, 0); }

		static Color Mix(Color a, Color b, float t)
		{
			t = Math.Clamp(t, 0, 1);
			return Color.FromArgb(
				(int)(a.A + (b.A - a.A) * t),
				(int)(a.R + (b.R - a.R) * t),
				(int)(a.G + (b.G - a.G) * t),
				(int)(a.B + (b.B - a.B) * t));
		}

		static Color Lighten(Color c, float t) { return Mix(c, Color.FromArgb(c.A, 255, 255, 255), t); }
		static Color Darken(Color c, float t) { return Mix(c, Color.FromArgb(c.A, 0, 0, 0), t); }

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
