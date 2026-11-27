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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>Shared drawing helpers for the armoured "war room" HUD pieces (support powers, timers).</summary>
	public static class PxWarChrome
	{
		public static readonly Color Stencil = Color.FromArgb(214, 200, 160);
		public static readonly Color Hazard = Color.FromArgb(232, 178, 36);
		public static readonly Color Friendly = Color.FromArgb(132, 214, 104);
		public static readonly Color Amber = Color.FromArgb(255, 176, 32);
		public static readonly Color Hostile = Color.FromArgb(255, 70, 60);

		/// <summary>Military plate: rectangle with the top-left and bottom-right corners cut off.</summary>
		public static void FillPlate(Rectangle r, int cut, Color top, Color bottom)
		{
			var cr = Game.Renderer.RgbaColorRenderer;
			var mid1 = Lerp(top, bottom, cut / (float)Math.Max(1, r.Height));
			var mid2 = Lerp(top, bottom, 1 - cut / (float)Math.Max(1, r.Height));
			cr.FillRect(new float3(r.X + cut, r.Y, 0), new float3(r.Right, r.Y, 0), new float3(r.Right, r.Y + cut, 0), new float3(r.X, r.Y + cut, 0),
				top, top, mid1, mid1);
			cr.FillRect(new float3(r.X, r.Y + cut, 0), new float3(r.Right, r.Y + cut, 0), new float3(r.Right, r.Bottom - cut, 0), new float3(r.X, r.Bottom - cut, 0),
				mid1, mid1, mid2, mid2);
			cr.FillRect(new float3(r.X, r.Bottom - cut, 0), new float3(r.Right, r.Bottom - cut, 0), new float3(r.Right - cut, r.Bottom, 0), new float3(r.X, r.Bottom, 0),
				mid2, mid2, bottom, bottom);
		}

		/// <summary>Steel plate with a coloured rim, brushed streaks and a top bevel.</summary>
		public static void DrawSteelPlate(Rectangle r, int cut, Color rim, float glow = 0, Color? glowColor = null)
		{
			FillPlate(new Rectangle(r.X + 2, r.Y + 3, r.Width, r.Height), cut, Color.FromArgb(70, 0, 0, 0), Color.FromArgb(120, 0, 0, 0));
			if (glow > 0)
			{
				var g = Color.FromArgb((int)(110 * glow), glowColor ?? rim);
				FillPlate(r.InflateBy(3, 3, 3, 3), cut + 2, g, g);
			}

			FillPlate(r, cut, rim, Darken(rim, 0.45f));
			var face = r.InflateBy(-2, -2, -2, -2);
			FillPlate(face, cut - 1, Color.FromArgb(245, 42, 44, 39), Color.FromArgb(245, 16, 17, 15));

			Game.Renderer.EnableScissor(face);
			var cr = Game.Renderer.RgbaColorRenderer;
			for (var x = face.X + 5; x < face.Right; x += 13)
				cr.FillRect(new float3(x, face.Y, 0), new float3(x + 1, face.Bottom, 0), Color.FromArgb(9, 255, 255, 255));
			Game.Renderer.DisableScissor();

			cr.DrawLine(new float3(face.X + cut, face.Y, 0), new float3(face.Right, face.Y, 0), 1, Color.FromArgb(45, 255, 255, 255));
			cr.DrawLine(new float3(face.X, face.Y + cut, 0), new float3(face.X + cut - 1, face.Y + 1, 0), 1, Color.FromArgb(45, 255, 255, 255));
		}

		/// <summary>Sunken black display window.</summary>
		public static void DrawWell(Rectangle r)
		{
			WidgetUtils.FillRectWithColor(r, Color.FromArgb(255, 6, 7, 6));
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, r.Width, 1), Color.FromArgb(190, 0, 0, 0));
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Bottom - 1, r.Width, 1), Color.FromArgb(45, 255, 255, 255));
		}

		public static void DrawHazard(Rectangle r, int scroll, int alpha = 220, Color? stripe = null)
		{
			WidgetUtils.FillRectWithColor(r, Color.FromArgb(alpha, 18, 16, 10));
			Game.Renderer.EnableScissor(r);
			var cr = Game.Renderer.RgbaColorRenderer;
			var color = Color.FromArgb(alpha, stripe ?? Hazard);
			for (var x = r.X - r.Height - 16 + scroll % 16; x < r.Right + 16; x += 16)
				cr.FillRect(new float3(x, r.Bottom, 0), new float3(x + 8, r.Bottom, 0), new float3(x + 8 + r.Height, r.Y, 0), new float3(x + r.Height, r.Y, 0), color);
			Game.Renderer.DisableScissor();
		}

		public static void DrawRivet(int2 p)
		{
			WidgetUtils.FillEllipseWithColor(new Rectangle(p.X - 2, p.Y - 2, 5, 5), Color.FromArgb(255, 10, 10, 9));
			WidgetUtils.FillEllipseWithColor(new Rectangle(p.X - 1, p.Y - 1, 3, 3), Color.FromArgb(255, 96, 98, 90));
		}

		/// <summary>Segmented charge bar.</summary>
		public static void DrawSegments(Rectangle bar, float fraction, Color color, int segment = 5)
		{
			WidgetUtils.FillRectWithColor(bar.InflateBy(1, 1, 1, 1), Color.FromArgb(255, 5, 6, 5));
			var lit = (int)(bar.Width * Math.Clamp(fraction, 0, 1));
			for (var x = 0; x < bar.Width; x += segment)
			{
				var w = Math.Min(segment - 1, bar.Width - x);
				WidgetUtils.FillRectWithColor(new Rectangle(bar.X + x, bar.Y, w, bar.Height), x < lit ? color : Color.FromArgb(38, color));
			}
		}

		public static void DrawBorder(Rectangle r, Color color, int width)
		{
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, r.Width, width), color);
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Bottom - width, r.Width, width), color);
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y + width, width, r.Height - 2 * width), color);
			WidgetUtils.FillRectWithColor(new Rectangle(r.Right - width, r.Y + width, width, r.Height - 2 * width), color);
		}

		// Letter spacing splits words into single glyphs, which breaks joined (Arabic) and wide (CJK) scripts
		static bool Spaceable(string text) => text.All(c => c < 0x250);

		public static int SpacedWidth(SpriteFont font, string text, int spacing)
		{
			if (!Spaceable(text))
				return font.Measure(text).X;

			var w = 0;
			foreach (var c in text)
				w += font.Measure(c.ToString()).X + spacing;
			return Math.Max(0, w - spacing);
		}

		public static void DrawSpaced(SpriteFont font, string text, float x, float y, int spacing, Color color)
		{
			var shadow = Color.FromArgb(color.A * 3 / 4, 0, 0, 0);
			if (!Spaceable(text))
			{
				font.DrawTextWithShadow(text, new float2(x, y), color, shadow, 1);
				return;
			}

			foreach (var c in text)
			{
				var s = c.ToString();
				font.DrawTextWithShadow(s, new float2(x, y), color, shadow, 1);
				x += font.Measure(s).X + spacing;
			}
		}

		public static Color Darken(Color c, float k) => Color.FromArgb(c.A, (int)(c.R * (1 - k)), (int)(c.G * (1 - k)), (int)(c.B * (1 - k)));

		public static Color Lerp(Color a, Color b, float t) => Color.FromArgb(
			(int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));

		/// <summary>0..1 pulse; period in milliseconds.</summary>
		public static float Pulse(int period) => 0.5f + 0.5f * (float)Math.Sin(Game.RunTime * 2 * Math.PI / period);
	}
}
