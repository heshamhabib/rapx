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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Shows system, mission and status lines ("Construction complete.", weather forecasts, ...) as a stack of
	/// HUD-styled toasts that slide in, count repeats and drain a timer bar. Player chat stays in the chat overlay;
	/// the stock text displays skip these pools through TextNotificationsDisplay.IgnoredPools.
	/// </summary>
	public class PxToastsWidget : Widget, INotificationHandler<TextNotification>
	{
		public readonly string HeaderFont = "PXSidebarSmall";
		public readonly string BodyFont = "PXBody";
		public readonly string CountFont = "PXDigitsSmall";

		public readonly Color SystemColor = Color.FromArgb(255, 176, 32);
		public readonly Color MissionColor = Color.FromArgb(226, 38, 38);
		public readonly Color StatusColor = Color.FromArgb(84, 200, 232);
		public readonly Color FeedbackColor = Color.FromArgb(150, 170, 220);
		public readonly Color BodyColor = Color.FromArgb(222, 223, 228);

		[Desc("How long status and feedback lines stay on screen.")]
		public readonly int StatusDurationMs = 4500;

		[Desc("How long system and mission lines stay on screen.")]
		public readonly int MessageDurationMs = 8000;

		public readonly int MaxToasts = 5;
		public readonly int Spacing = 8;

		const int EnterMs = 260;
		const int ExitMs = 380;
		const int BumpMs = 320;
		const int IconColumn = 50;
		const int PadRight = 14;
		const int PadTop = 9;
		const int HeaderGap = 4;
		const int PadBottom = 12;

		sealed class Toast
		{
			public TextNotification Notification;
			public string Header;
			public string[] Lines;
			public Color Accent;
			public Color Body;
			public int Duration;
			public int Count = 1;
			public long Born;
			public long Started;
			public long Bumped = -1;
			public long Leaving = -1;
			public int Height;
			public float Y = float.NaN;
		}

		readonly List<Toast> toasts = new();
		SpriteFont headerFont, bodyFont, countFont;
		long lastDraw = -1;

		public PxToastsWidget()
		{
			IgnoreMouseOver = true;
		}

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			headerFont = Game.Renderer.Fonts[HeaderFont];
			bodyFont = Game.Renderer.Fonts[BodyFont];
			countFont = Game.Renderer.Fonts[CountFont];
			Ui.Subscribe(this);
		}

		public override void Removed()
		{
			Ui.Unsubscribe(this);
			base.Removed();
		}

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		public override Rectangle EventBounds => Rectangle.Empty;

		void INotificationHandler<TextNotification>.Handle(TextNotification notification)
		{
			if (notification.Pool is not (TextNotificationPool.System or TextNotificationPool.Mission
				or TextNotificationPool.Transients or TextNotificationPool.Feedback))
				return;

			if (string.IsNullOrEmpty(notification.Text))
				return;

			// Dev screenshot runs (RAPX_SHOTS, see DevScreenshots): keep the "Saved screenshot" debug lines out of the shots
			if (notification.Prefix == "Debug" && !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_SHOTS")))
				return;

			var now = Game.RunTime;

			// Repeats of the newest toast bump its counter instead of stacking a copy
			var newest = toasts.Count > 0 ? toasts[^1] : null;
			if (newest != null && newest.Leaving < 0 && notification.CanIncrementOnDuplicate() && newest.Notification == notification)
			{
				newest.Count++;
				newest.Started = now;
				newest.Bumped = now;
				return;
			}

			var isStatus = notification.Pool is TextNotificationPool.Transients or TextNotificationPool.Feedback;
			var accent = notification.Pool switch
			{
				TextNotificationPool.Mission => notification.PrefixColor ?? MissionColor,
				TextNotificationPool.Transients => StatusColor,
				TextNotificationPool.Feedback => FeedbackColor,
				_ => SystemColor,
			};

			var textWidth = Bounds.Width - IconColumn - PadRight;
			var lines = WidgetUtils.WrapText(notification.Text, textWidth, bodyFont).Split('\n');
			var lineHeight = bodyFont.Measure("Ag").Y;
			var headerHeight = headerFont.Measure("A").Y;

			toasts.Add(new Toast
			{
				Notification = notification,
				Header = (notification.Prefix ?? "").ToUpperInvariant(),
				Lines = lines,
				Accent = accent,
				Body = notification.TextColor ?? BodyColor,
				Duration = isStatus ? StatusDurationMs : MessageDurationMs,
				Born = now,
				Started = now,
				Height = Math.Max(48, PadTop + headerHeight + HeaderGap + lines.Length * lineHeight + PadBottom),
			});

			// Push the oldest ones out when the stack is full
			var alive = 0;
			for (var i = toasts.Count - 1; i >= 0; i--)
				if (toasts[i].Leaving < 0 && ++alive > MaxToasts)
					toasts[i].Leaving = now;
		}

		public override void Tick()
		{
			var now = Game.RunTime;
			foreach (var t in toasts)
				if (t.Leaving < 0 && now - t.Started >= t.Duration)
					t.Leaving = now;

			toasts.RemoveAll(t => t.Leaving >= 0 && now - t.Leaving >= ExitMs);
		}

		public override void Draw()
		{
			var now = Game.RunTime;
			var dt = lastDraw < 0 ? 0 : Math.Min(100, now - lastDraw);
			lastDraw = now;
			if (toasts.Count == 0)
				return;

			var rb = RenderBounds;

			// Newest toast sits at the bottom; older ones glide up to make room
			var target = (float)rb.Bottom;
			for (var i = toasts.Count - 1; i >= 0; i--)
			{
				var t = toasts[i];
				target -= t.Height;
				if (float.IsNaN(t.Y))
					t.Y = target;
				else
					t.Y += (target - t.Y) * Math.Min(1f, dt / 90f);

				if (t.Leaving < 0)
					target -= Spacing;
			}

			foreach (var t in toasts)
				DrawToast(t, rb, now);
		}

		void DrawToast(Toast t, Rectangle rb, long now)
		{
			var enter = EaseOut(Math.Min(1f, (now - t.Born) / (float)EnterMs));
			var exit = t.Leaving < 0 ? 0f : Math.Min(1f, (now - t.Leaving) / (float)ExitMs);
			var alpha = enter * (1 - exit);
			if (alpha <= 0.01f)
				return;

			var slide = (int)((1 - enter) * 48 + EaseIn(exit) * 32);
			var r = new Rectangle(rb.X + slide, (int)t.Y, rb.Width, t.Height);
			if (r.Bottom < rb.Y)
				return;

			var bump = t.Bumped < 0 ? 0f : 1 - Math.Min(1f, (now - t.Bumped) / (float)BumpMs);
			var flash = Math.Max(1 - Math.Min(1f, (now - t.Born) / 420f), bump);
			var cr = Game.Renderer.RgbaColorRenderer;

			// Drop shadow, then the dark panel with a faint accent wash from the left edge
			Fill(new Rectangle(r.X + 3, r.Y + 4, r.Width, r.Height), Color.FromArgb(90, 0, 0, 0), alpha);
			Fill(r, Color.FromArgb(240, 12, 13, 16), alpha);
			var wash = Math.Min(r.Width, 170);
			cr.FillRect(new float3(r.X, r.Y, 0), new float3(r.X + wash, r.Y, 0), new float3(r.X + wash, r.Bottom, 0), new float3(r.X, r.Bottom, 0),
				Fade(t.Accent, (int)(46 + 60 * flash), alpha), Fade(t.Accent, 0, alpha), Fade(t.Accent, 0, alpha), Fade(t.Accent, (int)(46 + 60 * flash), alpha));
			Fill(new Rectangle(r.X, r.Y, r.Width, 1), Color.FromArgb(18, 255, 255, 255), alpha);
			PxWarChrome.DrawBorder(r, Fade(Color.FromArgb(44, 45, 52), 255, alpha), 1);

			// Accent stripe on the left edge, lit white for a moment when the toast arrives or repeats
			var stripe = PxWarChrome.Lerp(t.Accent, Color.White, 0.6f * flash);
			Fill(new Rectangle(r.X, r.Y, 3, r.Height), stripe, alpha);

			DrawIcon(t, new int2(r.X + 26, r.Y + PadTop + 12), alpha, flash);

			// Header: letter-spaced source label with a repeat counter on the right
			var x = r.X + IconColumn;
			var y = r.Y + PadTop;
			PxWarChrome.DrawSpaced(headerFont, t.Header, x, y, 2, Fade(t.Accent, 255, alpha));
			if (t.Count > 1)
			{
				var count = "x" + t.Count;
				var size = countFont.Measure(count);
				var badge = new Rectangle(r.Right - PadRight - size.X - 10, y - 2, size.X + 10, size.Y + 4);
				Fill(badge, PxWarChrome.Lerp(Color.FromArgb(220, 30, 32, 38), t.Accent, 0.35f + 0.5f * bump), alpha);
				countFont.DrawTextWithShadow(count, new float2(badge.X + 5, badge.Y + 2), Fade(Color.White, 255, alpha), Fade(Color.Black, 160, alpha), 1);
			}

			y += headerFont.Measure("A").Y + HeaderGap;
			var lineHeight = bodyFont.Measure("Ag").Y;
			foreach (var line in t.Lines)
			{
				bodyFont.DrawTextWithShadow(line, new float2(x, y), Fade(t.Body, 255, alpha), Fade(Color.Black, 170, alpha), 1);
				y += lineHeight;
			}

			// Timer bar draining along the bottom edge
			var left = t.Leaving >= 0 ? 0f : 1 - Math.Min(1f, (now - t.Started) / (float)t.Duration);
			var bar = new Rectangle(r.X + 3, r.Bottom - 3, r.Width - 4, 2);
			Fill(bar, Fade(t.Accent, 30, alpha), alpha);
			Fill(new Rectangle(bar.X, bar.Y, (int)(bar.Width * left), bar.Height), Fade(t.Accent, 190, alpha), 1);
		}

		/// <summary>Accent diamond with a dark core and a pulsing pip, framed like the HUD wells.</summary>
		static void DrawIcon(Toast t, int2 c, float alpha, float flash)
		{
			var cr = Game.Renderer.RgbaColorRenderer;
			var ring = Fade(t.Accent, (int)(70 + 110 * flash), alpha);
			Diamond(cr, c, 15, ring);
			Diamond(cr, c, 12, Fade(Color.FromArgb(14, 15, 18), 255, alpha));
			Diamond(cr, c, 10, Fade(t.Accent, 255, alpha));
			Diamond(cr, c, 7, Fade(Color.FromArgb(14, 15, 18), 255, alpha));
			var pip = 2 + (int)(2 * PxWarChrome.Pulse(1400));
			Diamond(cr, c, pip, Fade(PxWarChrome.Lerp(t.Accent, Color.White, 0.4f), 255, alpha));
		}

		static void Diamond(RgbaColorRenderer cr, int2 c, int r, Color color)
		{
			cr.FillRect(new float3(c.X, c.Y - r, 0), new float3(c.X + r, c.Y, 0), new float3(c.X, c.Y + r, 0), new float3(c.X - r, c.Y, 0), color);
		}

		static void Fill(Rectangle r, Color c, float alpha)
		{
			WidgetUtils.FillRectWithColor(r, Color.FromArgb((int)(c.A * alpha), c.R, c.G, c.B));
		}

		static Color Fade(Color c, int a, float alpha) => Color.FromArgb((int)(a * alpha), c.R, c.G, c.B);

		static float EaseOut(float t) => 1 - (1 - t) * (1 - t) * (1 - t);

		static float EaseIn(float t) => t * t;
	}
}
