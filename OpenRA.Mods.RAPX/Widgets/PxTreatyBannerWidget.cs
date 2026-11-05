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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Peace treaty countdown (IDEA-10): an armoured plate hanging from the top of the screen with hazard stripes,
	/// LCD digit cells and a draining fuse bar. Turns amber in the last minute, red and flashing in the final seconds,
	/// then shows a WAR plate for PxTreatyManager.WarBadgeSeconds.
	/// </summary>
	public class PxTreatyBannerWidget : Widget
	{
		public readonly string HeaderFont = "PXHeader";
		public readonly string DigitFont = "PXDigits";
		public readonly string WarFont = "PXDisplayLarge";
		public readonly string HintFont = "PXSidebarSmall";

		public readonly Color PeaceColor = Color.FromArgb(132, 214, 104);
		public readonly Color WarningColor = Color.FromArgb(255, 176, 32);
		public readonly Color FinalColor = Color.FromArgb(255, 70, 60);
		public readonly Color WarColor = Color.FromArgb(226, 38, 38);
		public readonly Color StencilColor = Color.FromArgb(214, 200, 160);
		public readonly Color HazardColor = Color.FromArgb(232, 178, 36);

		[Desc("Seconds left at which the banner turns to the warning colour.")]
		public readonly int WarningSeconds = 60;

		[Desc("Width of the chamfer on the bottom corners of the plate.")]
		public readonly int Chamfer = 22;

		[FluentReference]
		const string Header = "label-peace-treaty-header";

		[FluentReference]
		const string HeaderFinal = "label-peace-treaty-header-final";

		[FluentReference]
		const string War = "label-peace-treaty-war";

		[FluentReference]
		const string WarSub = "label-peace-treaty-war-sub";

		[FluentReference("votes", "needed")]
		const string Votes = "label-peace-treaty-votes";

		[FluentReference]
		const string Hint = "label-peace-treaty-hint";

		readonly World world;
		PxTreatyManager manager;
		bool resolved;
		long shownAt = -1;

		[ObjectCreator.UseCtor]
		public PxTreatyBannerWidget(World world)
		{
			this.world = world;
			IgnoreMouseOver = true;
		}

		protected PxTreatyBannerWidget(PxTreatyBannerWidget other)
			: base(other)
		{
			world = other.world;
			HeaderFont = other.HeaderFont;
			DigitFont = other.DigitFont;
			WarFont = other.WarFont;
			HintFont = other.HintFont;
			PeaceColor = other.PeaceColor;
			WarningColor = other.WarningColor;
			FinalColor = other.FinalColor;
			WarColor = other.WarColor;
			StencilColor = other.StencilColor;
			HazardColor = other.HazardColor;
			WarningSeconds = other.WarningSeconds;
			Chamfer = other.Chamfer;
			IgnoreMouseOver = true;
		}

		public override Widget Clone() { return new PxTreatyBannerWidget(this); }

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		PxTreatyManager Manager
		{
			get
			{
				if (!resolved)
				{
					manager = world.WorldActor.TraitOrDefault<PxTreatyManager>();
					resolved = true;
				}

				return manager;
			}
		}

		public override void Draw()
		{
			var m = Manager;
			if (m == null || m.TotalTicks <= 0)
				return;

			var sinceEnd = m.TicksSinceEnd;
			var warTicks = m.Info.WarBadgeSeconds * m.TicksPerSecond;
			if (!m.IsActive && (sinceEnd < 0 || sinceEnd >= warTicks))
				return;

			var now = Game.RunTime;
			if (shownAt < 0)
				shownAt = now;

			// Drop in from above the screen edge when the game starts
			var slide = Math.Min(1f, (now - shownAt) / 450f);
			var drop = (int)((1 - EaseOut(slide)) * -(Bounds.Height + 10));

			if (m.IsActive)
				DrawCountdown(m, now, drop);
			else
				DrawWar(m, now, drop, sinceEnd, warTicks);
		}

		void DrawCountdown(PxTreatyManager m, long now, int drop)
		{
			var rb = RenderBounds;
			rb = new Rectangle(rb.X, rb.Y + drop, rb.Width, rb.Height);

			var left = m.TicksLeft;
			var secondsLeft = (left + m.TicksPerSecond - 1) / m.TicksPerSecond;
			var final = secondsLeft <= m.Info.CountdownSeconds;
			var warning = secondsLeft <= WarningSeconds;
			var accent = final ? FinalColor : warning ? WarningColor : PeaceColor;

			// Final seconds: the plate throbs once per second, in step with the digits
			var beat = final ? 1 - left % m.TicksPerSecond / (float)m.TicksPerSecond : 0f;
			var pulse = final ? (float)Math.Pow(Math.Max(0, (beat - 0.6f) / 0.4f), 2) : warning ? 0.5f + 0.5f * (float)Math.Sin(now / 220.0) : 0f;

			DrawPlate(rb, accent, pulse, final ? 40 : 0);

			// Stencilled header
			var header = FluentProvider.GetMessage(final ? HeaderFinal : Header);
			var headerFont = Game.Renderer.Fonts[HeaderFont];
			DrawSpaced(headerFont, header, rb.X + rb.Width / 2, rb.Y + 9, 3, warning ? accent : StencilColor);

			// Star emblems either side of the header
			var hw = SpacedWidth(headerFont, header, 3);
			DrawStar(new float2(rb.X + rb.Width / 2 - hw / 2 - 14, rb.Y + 15), 5, accent);
			DrawStar(new float2(rb.X + rb.Width / 2 + hw / 2 + 14, rb.Y + 15), 5, accent);

			// LCD digits
			var time = WidgetUtils.FormatTime(left, world.Timestep);
			var digitsTop = rb.Y + 27;
			DrawDigits(time, rb.X + rb.Width / 2, digitsTop, accent, final ? 1 - beat : 1);

			// Fuse bar: remaining treaty time, burning down from the right
			var fraction = Math.Clamp(left / (float)m.TotalTicks, 0, 1);
			var bar = new Rectangle(rb.X + Chamfer + 8, rb.Bottom - 16, rb.Width - 2 * Chamfer - 16, 6);
			DrawFuse(bar, fraction, accent, now);

			// Votes to end early, or the hint how to start one
			var hintFont = Game.Renderer.Fonts[HintFont];
			var hint = m.VoteCount > 0
				? FluentProvider.GetMessage(Votes, "votes", m.VoteCount, "needed", m.VotersNeeded)
				: FluentProvider.GetMessage(Hint);
			var hintColor = m.VoteCount > 0 ? WarningColor : Color.FromArgb(150, StencilColor);
			var size = hintFont.Measure(hint);
			var tag = new Rectangle(rb.X + (rb.Width - size.X) / 2 - 10, rb.Bottom + 2, size.X + 20, size.Y + 6);
			FillTrapezoid(tag, 6, Color.FromArgb(200, 12, 13, 11), Color.FromArgb(200, 12, 13, 11));
			hintFont.DrawTextWithShadow(hint, new float2(tag.X + 10, tag.Y + 2), hintColor, Color.Black, 1);
		}

		void DrawWar(PxTreatyManager m, long now, int drop, int sinceEnd, int warTicks)
		{
			var rb = RenderBounds;
			var fade = Math.Min(1f, (warTicks - sinceEnd) / (float)m.TicksPerSecond);
			var age = sinceEnd / (float)m.TicksPerSecond;

			// Shake hard for the first second
			var shake = Math.Max(0, 1 - age);
			var dx = (int)(Math.Sin(now / 23.0) * 6 * shake);
			var dy = (int)(Math.Cos(now / 31.0) * 3 * shake);
			rb = new Rectangle(rb.X + dx, rb.Y + drop + dy, rb.Width, rb.Height);

			var flash = Math.Max(0, 1 - age / 0.35f);
			DrawPlate(rb, WarColor, 0.5f + 0.5f * (float)Math.Sin(now / 90.0), 90, fade);

			var font = Game.Renderer.Fonts[WarFont];
			var text = FluentProvider.GetMessage(War);
			var width = SpacedWidth(font, text, 10);
			var y = rb.Y + 22;
			DrawSpaced(font, text, rb.X + rb.Width / 2, y, 10, Color.FromArgb((int)(255 * fade), Lerp(Color.FromArgb(255, 226, 200), Color.White, flash)),
				Color.FromArgb((int)(220 * fade), 60, 0, 0));

			// Crossed blades of hazard stripes either side of the word
			var stripeY = y + 6;
			var lane = (rb.Width - width) / 2 - Chamfer - 20;
			if (lane > 10)
			{
				var scroll = (int)(now / 25 % 16);
				DrawHazard(new Rectangle(rb.X + Chamfer + 6, stripeY, lane, 14), scroll, fade);
				DrawHazard(new Rectangle(rb.Right - Chamfer - 6 - lane, stripeY, lane, 14), -scroll, fade);
			}

			var subFont = Game.Renderer.Fonts[HeaderFont];
			DrawSpaced(subFont, FluentProvider.GetMessage(WarSub), rb.X + rb.Width / 2, rb.Bottom - 22, 3, Color.FromArgb((int)(255 * fade), StencilColor));

			if (flash > 0)
				WidgetUtils.FillRectWithColor(rb, Color.FromArgb((int)(180 * flash), 255, 240, 220));
		}

		/// <summary>The hanging plate: dark steel trapezoid, hazard strip along the screen edge, coloured rim and rivets.</summary>
		void DrawPlate(Rectangle rb, Color accent, float pulse, int redTint, float alpha = 1)
		{
			int A(int a) => (int)(a * alpha);

			// Drop shadow and outer glow
			FillTrapezoid(new Rectangle(rb.X - 4, rb.Y, rb.Width + 8, rb.Height + 5), Chamfer + 4, Color.FromArgb(A(60), 0, 0, 0), Color.FromArgb(A(110), 0, 0, 0));
			if (pulse > 0)
			{
				var glow = Color.FromArgb(A((int)(90 * pulse)), accent);
				FillTrapezoid(new Rectangle(rb.X - 3, rb.Y, rb.Width + 6, rb.Height + 3), Chamfer + 3, glow, glow);
			}

			// Rim in the state colour, then the steel face
			FillTrapezoid(rb, Chamfer, Color.FromArgb(A(255), Darken(accent, 0.55f)), Color.FromArgb(A(255), Darken(accent, 0.8f)));
			var face = new Rectangle(rb.X + 2, rb.Y, rb.Width - 4, rb.Height - 2);
			var top = Color.FromArgb(A(245), 40 + redTint / 3, 42, 38);
			var bottom = Color.FromArgb(A(245), 15 + redTint / 4, 16, 14);
			FillTrapezoid(face, Chamfer - 1, top, bottom);

			// Brushed-metal streaks
			Game.Renderer.EnableScissor(face);
			for (var x = face.X + 7; x < face.Right; x += 19)
				Game.Renderer.RgbaColorRenderer.FillRect(new float3(x, face.Y, 0), new float3(x + 1, face.Bottom, 0), Color.FromArgb(A(10), 255, 255, 255));
			Game.Renderer.DisableScissor();

			// Inner bevel highlight along the chamfered edges
			var cr = Game.Renderer.RgbaColorRenderer;
			var bevel = Color.FromArgb(A(40), 255, 255, 255);
			cr.DrawLine(new float3(face.X + 1, face.Y + 6, 0), new float3(face.X + 1, face.Bottom - Chamfer, 0), 1, bevel);
			cr.DrawLine(new float3(face.X + 1, face.Bottom - Chamfer, 0), new float3(face.X + Chamfer, face.Bottom - 1, 0), 1, bevel);
			cr.DrawLine(new float3(face.X + Chamfer, face.Bottom - 1, 0), new float3(face.Right - Chamfer, face.Bottom - 1, 0), 1, Color.FromArgb(A(90), accent));

			// Hazard strip along the screen edge
			DrawHazard(new Rectangle(rb.X, rb.Y, rb.Width, 5), 0, alpha);

			// Rivets
			var rivets = new[]
			{
				new int2(rb.X + 9, rb.Y + 13), new int2(rb.Right - 10, rb.Y + 13),
				new int2(rb.X + Chamfer + 3, rb.Bottom - 9), new int2(rb.Right - Chamfer - 4, rb.Bottom - 9)
			};

			foreach (var p in rivets)
			{
				WidgetUtils.FillEllipseWithColor(new Rectangle(p.X - 3, p.Y - 3, 6, 6), Color.FromArgb(A(255), 10, 10, 9));
				WidgetUtils.FillEllipseWithColor(new Rectangle(p.X - 2, p.Y - 2, 4, 4), Color.FromArgb(A(255), 92, 94, 88));
				WidgetUtils.FillRectWithColor(new Rectangle(p.X - 1, p.Y - 1, 1, 1), Color.FromArgb(A(200), 210, 210, 200));
			}
		}

		void DrawDigits(string time, int centerX, int top, Color accent, float glow)
		{
			var font = Game.Renderer.Fonts[DigitFont];
			var digit = font.Measure("0");
			var cellW = digit.X + 8;
			var cellH = digit.Y + 8;
			const int Gap = 3;
			var colonW = digit.X / 2 + 4;

			var total = 0;
			foreach (var c in time)
				total += (c == ':' ? colonW : cellW) + Gap;
			total -= Gap;

			// Recessed display window behind the cells
			var window = new Rectangle(centerX - total / 2 - 6, top - 3, total + 12, cellH + 6);
			WidgetUtils.FillRectWithColor(window, Color.FromArgb(255, 6, 7, 6));
			WidgetUtils.FillRectWithColor(new Rectangle(window.X, window.Y, window.Width, 1), Color.FromArgb(160, 0, 0, 0));
			WidgetUtils.FillRectWithColor(new Rectangle(window.X, window.Bottom - 1, window.Width, 1), Color.FromArgb(50, 255, 255, 255));

			var ghost = Color.FromArgb(22, accent);
			var lit = Lerp(accent, Color.White, 0.15f);
			var halo = Color.FromArgb((int)(90 * glow), accent);
			var x = centerX - total / 2;
			foreach (var c in time)
			{
				if (c == ':')
				{
					// Colon dots blink with the seconds
					var on = Game.RunTime / 500 % 2 == 0;
					var dotColor = on ? accent : ghost;
					var cx = x + colonW / 2 - 2;
					WidgetUtils.FillRectWithColor(new Rectangle(cx, top + cellH / 3 - 2, 4, 4), dotColor);
					WidgetUtils.FillRectWithColor(new Rectangle(cx, top + cellH * 2 / 3 - 2, 4, 4), dotColor);
					x += colonW + Gap;
					continue;
				}

				var cell = new Rectangle(x, top, cellW, cellH);
				var cellTop = Color.FromArgb(255, 14, 17, 13);
				var cellBottom = Color.FromArgb(255, 8, 10, 8);
				WidgetUtils.FillRectWithColor(cell, cellTop, cellTop, cellBottom, cellBottom);
				WidgetUtils.FillRectWithColor(cell, Color.FromArgb(16, accent));

				var pos = new float2(x + (cellW - digit.X) / 2, top + 4);
				font.DrawTextWithContrast(c.ToString(), pos, lit, halo, 1);

				// Scanlines and a glass glint
				for (var y = cell.Y + 1; y < cell.Bottom; y += 3)
					WidgetUtils.FillRectWithColor(new Rectangle(cell.X, y, cell.Width, 1), Color.FromArgb(18, 0, 0, 0));
				WidgetUtils.FillRectWithColor(new Rectangle(cell.X, cell.Y, cell.Width, cell.Height / 2), Color.FromArgb(14, 255, 255, 255));

				x += cellW + Gap;
			}
		}

		static void DrawFuse(Rectangle bar, float fraction, Color accent, long now)
		{
			WidgetUtils.FillRectWithColor(bar.InflateBy(1, 1, 1, 1), Color.FromArgb(255, 5, 6, 5));

			const int Segment = 6;
			var lit = (int)(bar.Width * fraction);
			for (var x = 0; x < bar.Width; x += Segment)
			{
				var w = Math.Min(Segment - 1, bar.Width - x);
				var on = x < lit;
				WidgetUtils.FillRectWithColor(new Rectangle(bar.X + x, bar.Y, w, bar.Height), on ? accent : Color.FromArgb(40, accent));
			}

			// Burning tip
			if (lit > 0 && fraction < 1)
			{
				var flicker = 0.6f + 0.4f * (float)Math.Sin(now / 45.0);
				var tip = new float2(bar.X + lit, bar.Y + bar.Height / 2);
				WidgetUtils.FillEllipseWithColor(new Rectangle((int)tip.X - 6, (int)tip.Y - 6, 12, 12), Color.FromArgb((int)(90 * flicker), 255, 190, 80));
				WidgetUtils.FillEllipseWithColor(new Rectangle((int)tip.X - 3, (int)tip.Y - 3, 6, 6), Color.FromArgb((int)(255 * flicker), 255, 240, 200));
			}
		}

		void DrawHazard(Rectangle r, int scroll, float alpha)
		{
			var a = (int)(255 * alpha);
			WidgetUtils.FillRectWithColor(r, Color.FromArgb(a, 18, 16, 10));
			Game.Renderer.EnableScissor(r);
			var cr = Game.Renderer.RgbaColorRenderer;
			var color = Color.FromArgb((int)(220 * alpha), HazardColor);
			for (var x = r.X - r.Height - 16 + scroll; x < r.Right + 16; x += 16)
				cr.FillRect(new float3(x, r.Bottom, 0), new float3(x + 8, r.Bottom, 0), new float3(x + 8 + r.Height, r.Y, 0), new float3(x + r.Height, r.Y, 0), color);
			Game.Renderer.DisableScissor();
		}

		static void DrawStar(float2 c, float radius, Color color)
		{
			var cr = Game.Renderer.RgbaColorRenderer;
			var inner = radius * 0.42f;
			for (var i = 0; i < 5; i++)
			{
				var a0 = -Math.PI / 2 + i * 2 * Math.PI / 5;
				var a1 = a0 + Math.PI / 5;
				var a2 = a0 - Math.PI / 5;
				var tip = new float3(c.X + (float)Math.Cos(a0) * radius, c.Y + (float)Math.Sin(a0) * radius, 0);
				var l = new float3(c.X + (float)Math.Cos(a1) * inner, c.Y + (float)Math.Sin(a1) * inner, 0);
				var r = new float3(c.X + (float)Math.Cos(a2) * inner, c.Y + (float)Math.Sin(a2) * inner, 0);
				var center = new float3(c.X, c.Y, 0);
				cr.FillRect(center, r, tip, l, color);
			}
		}

		/// <summary>Plate shape: full width at the top edge, chamfered bottom corners.</summary>
		static void FillTrapezoid(Rectangle r, int chamfer, Color top, Color bottom)
		{
			var cr = Game.Renderer.RgbaColorRenderer;
			var body = r.Bottom - chamfer;
			var mid = Lerp(top, bottom, 0.7f);
			cr.FillRect(new float3(r.X, r.Y, 0), new float3(r.Right, r.Y, 0), new float3(r.Right, body, 0), new float3(r.X, body, 0), top, top, mid, mid);
			cr.FillRect(new float3(r.X, body, 0), new float3(r.Right, body, 0), new float3(r.Right - chamfer, r.Bottom, 0), new float3(r.X + chamfer, r.Bottom, 0),
				mid, mid, bottom, bottom);
		}

		static int SpacedWidth(SpriteFont font, string text, int spacing)
		{
			var w = 0;
			foreach (var c in text)
				w += font.Measure(c.ToString()).X + spacing;
			return Math.Max(0, w - spacing);
		}

		static void DrawSpaced(SpriteFont font, string text, int centerX, int y, int spacing, Color color, Color? shadow = null)
		{
			var x = (float)(centerX - SpacedWidth(font, text, spacing) / 2);
			var bg = shadow ?? Color.FromArgb(color.A * 3 / 4, 0, 0, 0);
			foreach (var c in text)
			{
				var s = c.ToString();
				font.DrawTextWithShadow(s, new float2(x, y), color, bg, 1);
				x += font.Measure(s).X + spacing;
			}
		}

		static float EaseOut(float t) => 1 - (1 - t) * (1 - t) * (1 - t);

		static Color Darken(Color c, float k) => Color.FromArgb(c.A, (int)(c.R * (1 - k)), (int)(c.G * (1 - k)), (int)(c.B * (1 - k)));

		static Color Lerp(Color a, Color b, float t) => Color.FromArgb(
			(int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
	}
}
