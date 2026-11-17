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
	/// Shows system, mission and status lines ("Construction complete.", weather forecasts, ...) as a compact,
	/// right-aligned ticker of one-line chips. Kept quiet on purpose:
	/// - status lines (Transients/Feedback) share a single lane, so a new one cross-fades over the previous one;
	/// - a repeat of any visible line bumps its counter and moves it to the bottom instead of stacking a copy;
	/// - only a few messages are visible, older ones dim and shrink away, overflow retires the oldest fast.
	/// Player chat stays in the chat overlay; the stock text displays skip these pools through TextNotificationsDisplay.IgnoredPools.
	/// </summary>
	public class PxToastsWidget : Widget, INotificationHandler<TextNotification>
	{
		public readonly string HeaderFont = "PXSidebarSmall";
		public readonly string BodyFont = "PXSmall";
		public readonly string CountFont = "PXDigitsSmall";

		public readonly Color SystemColor = Color.FromArgb(255, 176, 32);
		public readonly Color MissionColor = Color.FromArgb(226, 38, 38);
		public readonly Color StatusColor = Color.FromArgb(84, 200, 232);
		public readonly Color FeedbackColor = Color.FromArgb(150, 170, 220);
		public readonly Color BodyColor = Color.FromArgb(222, 223, 228);

		[Desc("How long status and feedback lines stay on screen.")]
		public readonly int StatusDurationMs = 3200;

		[Desc("How long system and mission lines stay on screen.")]
		public readonly int MessageDurationMs = 6500;

		[Desc("Most system/mission chips visible at once (the status lane is extra).")]
		public readonly int MaxMessages = 2;

		[Desc("Body lines per chip; longer text is cut with an ellipsis.")]
		public readonly int MaxLines = 2;

		public readonly int Spacing = 3;

		const int EnterMs = 200;
		const int ExitMs = 260;
		const int BumpMs = 320;
		const int PadLeft = 9;
		const int PadRight = 9;
		const int PadY = 4;
		const int HeaderGap = 7;

		sealed class Toast
		{
			public TextNotification Notification;
			public bool IsStatus;
			public string Header;
			public int HeaderWidth;
			public string[] Lines;
			public Color Accent;
			public Color Body;
			public int Duration;
			public int Count = 1;
			public long Born;
			public long Started;
			public long Bumped = -1;
			public long Leaving = -1;
			public int Width;
			public int Height;
			public int Depth;
			public float Y = float.NaN;
		}

		readonly List<Toast> toasts = new();
		SpriteFont headerFont, bodyFont, countFont;
		int lineHeight, headerHeight;
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
			lineHeight = bodyFont.Measure("Ag").Y;
			headerHeight = headerFont.Measure("A").Y;
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

			// A repeat of any visible line bumps its counter and drops it to the newest slot instead of stacking a copy
			if (notification.CanIncrementOnDuplicate())
			{
				var same = toasts.FindLastIndex(t => t.Leaving < 0 && t.Notification == notification);
				if (same >= 0)
				{
					var t = toasts[same];
					toasts.RemoveAt(same);
					toasts.Add(t);
					t.Count++;
					t.Started = now;
					t.Bumped = now;
					t.Width = ChipWidth(t);
					return;
				}
			}

			var isStatus = notification.Pool is TextNotificationPool.Transients or TextNotificationPool.Feedback;
			var accent = notification.Pool switch
			{
				TextNotificationPool.Mission => notification.PrefixColor ?? MissionColor,
				TextNotificationPool.Transients => StatusColor,
				TextNotificationPool.Feedback => FeedbackColor,
				_ => SystemColor,
			};

			// Status lines carry no source label (they are all EVA chatter); messages show theirs inline in the accent colour
			var header = isStatus ? "" : (notification.Prefix ?? "").ToUpperInvariant();
			var headerWidth = header.Length > 0 ? PxWarChrome.SpacedWidth(headerFont, header, 1) + HeaderGap : 0;
			var textWidth = Bounds.Width - PadLeft - PadRight - headerWidth - 34;
			var lines = WrapLimited(notification.Text, textWidth);

			var toast = new Toast
			{
				Notification = notification,
				IsStatus = isStatus,
				Header = header,
				HeaderWidth = headerWidth,
				Lines = lines,
				Accent = accent,
				Body = notification.TextColor ?? BodyColor,
				Duration = isStatus ? StatusDurationMs : MessageDurationMs,
				Born = now,
				Started = now,
				Height = PadY * 2 + lines.Length * lineHeight,
			};
			toast.Width = ChipWidth(toast);

			// One status lane: the new status line replaces the previous one in place
			if (isStatus)
				foreach (var t in toasts)
					if (t.IsStatus && t.Leaving < 0)
						t.Leaving = now;

			toasts.Add(toast);

			// Retire the oldest messages when there are too many
			var alive = 0;
			for (var i = toasts.Count - 1; i >= 0; i--)
				if (!toasts[i].IsStatus && toasts[i].Leaving < 0 && ++alive > MaxMessages)
					toasts[i].Leaving = now;
		}

		string[] WrapLimited(string text, int width)
		{
			var lines = WidgetUtils.WrapText(text, width, bodyFont).Split('\n');
			if (lines.Length <= MaxLines)
				return lines;

			var cut = lines[..MaxLines];
			cut[^1] = WidgetUtils.TruncateText(cut[^1] + " " + lines[MaxLines], width, bodyFont);
			if (!cut[^1].EndsWith("...", StringComparison.Ordinal))
				cut[^1] = WidgetUtils.TruncateText(cut[^1] + "...", width, bodyFont);
			return cut;
		}

		int ChipWidth(Toast t)
		{
			var text = 0;
			foreach (var line in t.Lines)
				text = Math.Max(text, bodyFont.Measure(line).X);

			var count = t.Count > 1 ? countFont.Measure("x" + t.Count).X + 14 : 0;
			return Math.Min(Bounds.Width, PadLeft + t.HeaderWidth + text + count + PadRight);
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

			// Newest chip sits at the bottom; older ones glide up. Leaving chips keep their spot and fade out,
			// so a replaced status line cross-fades under its successor instead of pushing the stack around.
			var target = (float)rb.Bottom;
			var depth = 0;
			for (var i = toasts.Count - 1; i >= 0; i--)
			{
				var t = toasts[i];
				if (t.Leaving >= 0)
				{
					if (float.IsNaN(t.Y))
						t.Y = target - t.Height;
					continue;
				}

				target -= t.Height;
				if (float.IsNaN(t.Y))
					t.Y = target;
				else
					t.Y += (target - t.Y) * Math.Min(1f, dt / 90f);

				target -= Spacing;
				t.Depth = depth++;
			}

			foreach (var t in toasts)
				DrawToast(t, rb, now);

		}

		void DrawToast(Toast t, Rectangle rb, long now)
		{
			var enter = EaseOut(Math.Min(1f, (now - t.Born) / (float)EnterMs));
			var exit = t.Leaving < 0 ? 0f : Math.Min(1f, (now - t.Leaving) / (float)ExitMs);

			// Older chips step back: dimmer the further they are from the newest
			var dim = t.Depth == 0 ? 1f : t.Depth == 1 ? 0.72f : 0.5f;
			var alpha = enter * (1 - exit) * dim;
			if (alpha <= 0.01f)
				return;

			var slide = (int)((1 - enter) * 28 + EaseIn(exit) * 18);
			var r = new Rectangle(rb.Right - t.Width + slide, (int)t.Y, t.Width, t.Height);
			if (r.Bottom < rb.Y)
				return;

			var bump = t.Bumped < 0 ? 0f : 1 - Math.Min(1f, (now - t.Bumped) / (float)BumpMs);
			var flash = Math.Max(1 - Math.Min(1f, (now - t.Born) / 360f), bump);
			var cr = Game.Renderer.RgbaColorRenderer;

			// Translucent dark chip with a short accent wash from the left edge
			Fill(r, Color.FromArgb(200, 10, 11, 14), alpha);
			var wash = Math.Min(r.Width, 90);
			var washA = (int)(34 + 50 * flash);
			cr.FillRect(new float3(r.X, r.Y, 0), new float3(r.X + wash, r.Y, 0), new float3(r.X + wash, r.Bottom, 0), new float3(r.X, r.Bottom, 0),
				Fade(t.Accent, washA, alpha), Fade(t.Accent, 0, alpha), Fade(t.Accent, 0, alpha), Fade(t.Accent, washA, alpha));

			// Accent stripe on the left edge, lit white for a moment when the chip arrives or repeats
			Fill(new Rectangle(r.X, r.Y, 2, r.Height), PxWarChrome.Lerp(t.Accent, Color.White, 0.6f * flash), alpha);

			var x = r.X + PadLeft;
			var y = r.Y + PadY;
			if (t.Header.Length > 0)
				PxWarChrome.DrawSpaced(headerFont, t.Header, x, y + (lineHeight - headerHeight) / 2 + 1, 1, Fade(t.Accent, 255, alpha));

			x += t.HeaderWidth;
			foreach (var line in t.Lines)
			{
				bodyFont.DrawTextWithShadow(line, new float2(x, y), Fade(t.Body, 255, alpha), Fade(Color.Black, 170, alpha), 1);
				y += lineHeight;
			}

			if (t.Count > 1)
			{
				var count = "x" + t.Count;
				var size = countFont.Measure(count);
				var badge = new Rectangle(r.Right - PadRight - size.X - 8, r.Y + (r.Height - size.Y - 4) / 2, size.X + 8, size.Y + 4);
				Fill(badge, PxWarChrome.Lerp(Color.FromArgb(220, 30, 32, 38), t.Accent, 0.35f + 0.5f * bump), alpha);
				countFont.DrawTextWithShadow(count, new float2(badge.X + 4, badge.Y + 2), Fade(Color.White, 255, alpha), Fade(Color.Black, 160, alpha), 1);
			}

			// Hairline timer draining along the bottom edge
			var left = t.Leaving >= 0 ? 0f : 1 - Math.Min(1f, (now - t.Started) / (float)t.Duration);
			Fill(new Rectangle(r.X + 2, r.Bottom - 1, (int)((r.Width - 2) * left), 1), Fade(t.Accent, 150, alpha), 1);
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
