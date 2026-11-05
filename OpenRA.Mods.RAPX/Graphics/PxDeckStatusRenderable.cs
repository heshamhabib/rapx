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
	/// <summary>What the flight-deck HUD shows (IDEA-08 2c A1), captured when the carrier's annotations are collected.</summary>
	public readonly struct PxDeckStatus
	{
		public readonly int Mode; // 0 Launch, 1 Recover, 2 Mixed
		public readonly string ModeText;
		public readonly string Title;
		public readonly Color Accent;
		public readonly int Slots, Parked, Airborne, Holding, Queued;

		/// <summary>0..1: how far the catapult (Launch) or the wires (Recover/Mixed) are through their cycle; 1 = ready.</summary>
		public readonly float Readiness;

		/// <summary>1 right after the mode changed, fading to 0.</summary>
		public readonly float Flash;

		public PxDeckStatus(int mode, string modeText, string title, Color accent, int slots, int parked, int airborne,
			int holding, int queued, float readiness, float flash)
		{
			Mode = mode;
			ModeText = modeText;
			Title = title;
			Accent = accent;
			Slots = slots;
			Parked = parked;
			Airborne = airborne;
			Holding = holding;
			Queued = queued;
			Readiness = readiness;
			Flash = flash;
		}
	}

	/// <summary>
	/// The "air boss" tag above a selected carrier: a chamfered glass panel with a glowing edge in the mode's colour,
	/// an animated mode glyph (chevrons climbing off the catapult, dropping onto the wires, or both), the mode name in
	/// the HUD font, one segment per deck slot (solid = parked, outlined = in the air, pulsing = holding), counters for
	/// jets holding and waiting to launch, and a strip that fills as the catapult / wires cycle. Drawn in screen pixels,
	/// so it keeps its size at every zoom.
	/// </summary>
	public class PxDeckStatusRenderable : IRenderable, IFinalizedRenderable
	{
		const int Width = 228;
		const int Height = 46;
		const int Chamfer = 9;
		const int Gap = 12; // above the selection box, clear of the health bar

		static readonly Color Glass = Color.FromArgb(205, 7, 13, 22);
		static readonly Color GlassTop = Color.FromArgb(205, 18, 30, 46);
		static readonly Color Dim = Color.FromArgb(150, 150, 175, 200);
		static readonly Color EmptySlot = Color.FromArgb(55, 160, 190, 220);

		readonly Rectangle bounds;
		readonly PxDeckStatus status;
		readonly SpriteFont modeFont;
		readonly SpriteFont smallFont;

		public PxDeckStatusRenderable(WPos pos, Rectangle decorationBounds, in PxDeckStatus status, SpriteFont modeFont, SpriteFont smallFont)
		{
			Pos = pos;
			bounds = decorationBounds;
			this.status = status;
			this.modeFont = modeFont;
			this.smallFont = smallFont;
		}

		public WPos Pos { get; }
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxDeckStatusRenderable(Pos + vec, bounds, status, modeFont, smallFont); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }

		static Color WithAlpha(Color c, int a) { return Color.FromArgb(Math.Clamp(a, 0, 255), c.R, c.G, c.B); }

		static Color Mix(Color a, Color b, float t)
		{
			return Color.FromArgb((int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}

		public void Render(WorldRenderer wr)
		{
			var cr = Game.Renderer.RgbaColorRenderer;
			var time = Game.RunTime / 1000f;
			var accent = status.Accent;

			// Panel: centred above the selection box, bottom-left and top-right corners cut.
			var top = wr.Viewport.WorldToViewPx(new float2(bounds.Left + bounds.Width / 2f, bounds.Top));
			var x0 = (float)Math.Round(top.X - Width / 2f);
			var y1 = top.Y - Gap;
			var y0 = y1 - Height;
			var x1 = x0 + Width;

			var outline = new float2[]
			{
				new(x0, y0), new(x1 - Chamfer, y0), new(x1, y0 + Chamfer),
				new(x1, y1), new(x0 + Chamfer, y1), new(x0, y1 - Chamfer)
			};

			// Soft outer glow, brighter for a moment after a mode change.
			var glow = 0.35f + 0.65f * status.Flash;
			for (var i = 3; i >= 1; i--)
				cr.DrawPolygon(outline, i * 2.5f, WithAlpha(accent, (int)(28 * glow * (4 - i))));

			// Glass body with a lighter top half (fake vertical gradient).
			var mid = y0 + Height * 0.45f;
			cr.FillRect(new float3(x0, y0, 0), new float3(x1 - Chamfer, y0, 0), new float3(x1, y0 + Chamfer, 0), new float3(x0, y0 + Chamfer, 0), GlassTop);
			cr.FillRect(new float3(x0, y0 + Chamfer, 0), new float3(x1, mid, 0), GlassTop);
			cr.FillRect(new float3(x0, mid, 0), new float3(x1, y1 - Chamfer, 0), Glass);
			cr.FillRect(new float3(x0, y1 - Chamfer, 0), new float3(x1, y1 - Chamfer, 0), new float3(x1, y1, 0), new float3(x0 + Chamfer, y1, 0), Glass);
			if (status.Flash > 0)
				cr.FillRect(new float3(x0, y0, 0), new float3(x1, y1, 0), WithAlpha(accent, (int)(70 * status.Flash)));

			// Crisp edge: accent on the cut corners, dim elsewhere.
			cr.DrawPolygon(outline, 1, WithAlpha(accent, 150));
			cr.DrawLine(new float3(x1 - Chamfer - 26, y0, 0), new float3(x1 - Chamfer, y0, 0), 2, accent);
			cr.DrawLine(new float3(x1 - Chamfer, y0, 0), new float3(x1, y0 + Chamfer, 0), 2, accent);
			cr.DrawLine(new float3(x0, y1 - Chamfer, 0), new float3(x0 + Chamfer, y1, 0), 2, accent);
			cr.DrawLine(new float3(x0 + Chamfer, y1, 0), new float3(x0 + Chamfer + 26, y1, 0), 2, accent);

			// Accent spine on the left.
			cr.FillRect(new float3(x0 + 3, y0 + 4, 0), new float3(x0 + 6, y1 - Chamfer - 2, 0), accent);

			// Mode glyph.
			DrawGlyph(cr, new float2(x0 + 24, y0 + Height / 2f - 1), accent, time);

			// Title (small, letter-spaced) and mode name.
			var textX = x0 + 44;
			DrawSpaced(smallFont, status.Title, new float2(textX, y0 + 4), Dim, 1.5f);
			var modeY = y0 + 12;
			DrawSpaced(modeFont, status.ModeText, new float2(textX + 1, modeY + 1), Color.FromArgb(170, 0, 0, 0), 2.5f);
			DrawSpaced(modeFont, status.ModeText, new float2(textX, modeY), Mix(accent, Color.White, 0.25f + 0.5f * status.Flash), 2.5f);

			// Wing count, right-aligned on the title row.
			var wing = $"{status.Parked + status.Airborne}/{status.Slots}";
			var wingSize = smallFont.Measure(wing);
			smallFont.DrawText(wing, new float2(x1 - Chamfer - 6 - wingSize.X, y0 + 4), Color.White);

			// Counters on the mode row: holding (orbit glyph) and waiting to launch (arrow glyph).
			var cx = x1 - 12f;
			var cy = modeY + 9f;
			if (status.Queued > 0)
				cx = DrawCounter(cr, cx, cy, status.Queued, accent, false, time);

			if (status.Holding > 0)
				DrawCounter(cr, cx, cy, status.Holding, Color.FromArgb(255, 255, 196, 64), true, time);

			// Slot strip: one segment per slot.
			var stripY0 = y1 - 11f;
			var stripY1 = y1 - 6f;
			var stripX0 = textX;
			var stripX1 = x1 - 10f;
			var n = Math.Max(1, status.Slots);
			var seg = (stripX1 - stripX0 + 2) / n;
			var holdPulse = 0.5f + 0.5f * MathF.Sin(time * 6f);
			for (var i = 0; i < n; i++)
			{
				var a = new float3(stripX0 + i * seg, stripY0, 0);
				var b = new float3(stripX0 + (i + 1) * seg - 2, stripY1, 0);
				if (i < status.Parked)
				{
					cr.FillRect(a, b, accent);
					cr.DrawLine(a, new float3(b.X, a.Y, 0), 1, Mix(accent, Color.White, 0.5f));
				}
				else if (i < status.Parked + status.Airborne)
				{
					var holding = i >= status.Parked + status.Airborne - status.Holding;
					var c = holding ? Mix(Color.FromArgb(255, 255, 196, 64), Color.White, holdPulse * 0.4f) : Color.White;
					cr.DrawRect(a, b, 1, WithAlpha(c, holding ? 230 : 200));
				}
				else
					cr.FillRect(a, b, EmptySlot);
			}

			// Cycle strip under the panel: fills as the catapult / wires get ready; a light sweeps along when ready.
			var barY = y1 + 3f;
			var barX0 = x0 + Chamfer;
			var barX1 = x1;
			cr.FillRect(new float3(barX0, barY, 0), new float3(barX1, barY + 2, 0), Color.FromArgb(120, 10, 16, 24));
			var fill = barX0 + (barX1 - barX0) * Math.Clamp(status.Readiness, 0f, 1f);
			cr.FillRect(new float3(barX0, barY, 0), new float3(fill, barY + 2, 0), WithAlpha(accent, 200));
			if (status.Readiness >= 1f)
			{
				var sweep = barX0 + (barX1 - barX0) * (time * 0.8f % 1f);
				cr.DrawLine(new float3(Math.Max(barX0, sweep - 18), barY + 1, 0), new float3(sweep, barY + 1, 0), 2,
					WithAlpha(Color.White, 0), WithAlpha(Color.White, 220));
			}
		}

		void DrawGlyph(RgbaColorRenderer cr, float2 c, Color accent, float time)
		{
			// A soft disc behind the glyph.
			cr.FillEllipse(new float3(c.X - 15, c.Y - 15, 0), new float3(c.X + 15, c.Y + 15, 0), WithAlpha(accent, 34));
			cr.DrawPolygon(Circle(c, 15, 24), 1, WithAlpha(accent, 120));

			// Three chevrons; the lit one travels in the direction the jets move.
			var phase = (int)(time * 6) % 3;
			switch (status.Mode)
			{
				case 0:
					for (var i = 0; i < 3; i++)
						Chevron(cr, new float2(c.X, c.Y + 6 - i * 6), 7, true, ChevronColor(accent, i == phase));
					break;
				case 1:
					for (var i = 0; i < 3; i++)
						Chevron(cr, new float2(c.X, c.Y - 7 + i * 6), 7, false, ChevronColor(accent, i == phase));

					// The arresting wire the chevrons drop onto.
					cr.DrawLine(new float3(c.X - 8, c.Y + 9, 0), new float3(c.X + 8, c.Y + 9, 0), 1.5f, accent);
					break;
				default:
					var up = (int)(time * 3) % 2 == 0;
					Chevron(cr, new float2(c.X - 5, c.Y + 2), 5, true, ChevronColor(accent, up));
					Chevron(cr, new float2(c.X - 5, c.Y - 4), 5, true, ChevronColor(accent, up));
					Chevron(cr, new float2(c.X + 5, c.Y - 2), 5, false, ChevronColor(accent, !up));
					Chevron(cr, new float2(c.X + 5, c.Y + 4), 5, false, ChevronColor(accent, !up));
					break;
			}
		}

		static Color ChevronColor(Color accent, bool lit)
		{
			return lit ? Mix(accent, Color.White, 0.6f) : WithAlpha(accent, 110);
		}

		static void Chevron(RgbaColorRenderer cr, float2 tip, float half, bool up, Color color)
		{
			var dy = up ? half * 0.7f : -half * 0.7f;
			cr.DrawLine(new float3(tip.X - half, tip.Y + dy, 0), new float3(tip.X, tip.Y, 0), 2, color);
			cr.DrawLine(new float3(tip.X, tip.Y, 0), new float3(tip.X + half, tip.Y + dy, 0), 2, color);
		}

		static float2[] Circle(float2 c, float r, int points)
		{
			var result = new float2[points];
			for (var i = 0; i < points; i++)
			{
				var a = i * MathF.PI * 2 / points;
				result[i] = new float2(c.X + r * MathF.Cos(a), c.Y + r * MathF.Sin(a));
			}

			return result;
		}

		/// <summary>Draws "n" with a small glyph to its left, ending at x; returns the x where the next counter ends.</summary>
		float DrawCounter(RgbaColorRenderer cr, float x, float cy, int count, Color color, bool orbit, float time)
		{
			var text = count.ToString(System.Globalization.CultureInfo.InvariantCulture);
			var size = smallFont.Measure(text);
			smallFont.DrawText(text, new float2(x - size.X, cy - size.Y / 2f - 1), color);
			var gx = x - size.X - 8;
			if (orbit)
			{
				// A ring with a dot circling it.
				cr.DrawPolygon(Circle(new float2(gx, cy), 4.5f, 12), 1, WithAlpha(color, 170));
				var a = time * 4f;
				cr.FillEllipse(new float3(gx + 4.5f * MathF.Cos(a) - 1.5f, cy + 4.5f * MathF.Sin(a) - 1.5f, 0),
					new float3(gx + 4.5f * MathF.Cos(a) + 1.5f, cy + 4.5f * MathF.Sin(a) + 1.5f, 0), color);
			}
			else
			{
				Chevron(cr, new float2(gx, cy - 3), 4, true, color);
				Chevron(cr, new float2(gx, cy + 1), 4, true, WithAlpha(color, 140));
			}

			return gx - 9;
		}

		static void DrawSpaced(SpriteFont font, string text, float2 pos, Color color, float spacing)
		{
			var x = pos.X;
			foreach (var ch in text)
			{
				var s = ch.ToString();
				font.DrawText(s, new float2(x, pos.Y), color);
				x += font.Measure(s).X + spacing;
			}
		}
	}
}
