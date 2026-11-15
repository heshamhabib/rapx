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
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Sidebar weather badge (IDEA-20): an animated icon plate tinted by the weather, the current weather,
	/// and a forecast of the next weather with a countdown that turns amber during the warning.
	/// A timeline along the bottom shows the time left until the change.
	/// </summary>
	public class PxWeatherBadgeWidget : Widget
	{
		public readonly string LabelFont = "PXSidebarSmall";
		public readonly string NameFont = "PXSidebarLabel";
		public readonly string DigitFont = "PXDigitsMedium";
		public readonly string IconCollection = "px-weather-icons";
		public readonly Color LabelColor = Color.FromArgb(157, 158, 166);
		public readonly Color TextColor = Color.FromArgb(237, 238, 242);
		public readonly Color WarningColor = Color.FromArgb(255, 176, 32);

		[Desc("Width of the forecast block on the right.")]
		public readonly int ForecastWidth = 150;

		public readonly string TooltipTemplate = "SIMPLE_TOOLTIP";
		public readonly string TooltipContainer;

		[FluentReference]
		const string Title = "label-px-weather-title";

		[FluentReference]
		const string Changing = "label-px-weather-changing";

		[FluentReference]
		const string NextShort = "label-px-weather-next-short";

		[FluentReference]
		const string IncomingShort = "label-px-weather-incoming-short";

		[FluentReference]
		const string ForecastLabel = "label-px-weather-forecast";

		[FluentReference]
		const string Stable = "label-px-weather-stable";

		[FluentReference("weather")]
		const string TooltipNow = "label-px-weather-tooltip-now";

		[FluentReference("weather", "time")]
		const string TooltipNext = "label-px-weather-tooltip-next";

		[FluentReference]
		const string TooltipFixed = "label-px-weather-tooltip-fixed";

		[FluentReference]
		const string TooltipMode = "label-px-weather-tooltip-mode";

		static readonly Dictionary<PxWeatherType, Color> Accents = new()
		{
			{ PxWeatherType.Clear, Color.FromArgb(255, 209, 102) },
			{ PxWeatherType.Rain, Color.FromArgb(104, 178, 255) },
			{ PxWeatherType.Thunderstorm, Color.FromArgb(176, 150, 255) },
			{ PxWeatherType.Snow, Color.FromArgb(196, 232, 255) },
			{ PxWeatherType.Blizzard, Color.FromArgb(150, 214, 255) },
			{ PxWeatherType.Fog, Color.FromArgb(184, 194, 204) },
			{ PxWeatherType.Sandstorm, Color.FromArgb(232, 165, 90) },
			{ PxWeatherType.StrongWind, Color.FromArgb(132, 226, 196) },
			{ PxWeatherType.HeatHaze, Color.FromArgb(255, 138, 76) },
		};

		readonly PxWeatherManager weather;
		readonly Lazy<TooltipContainerWidget> tooltipContainer;
		SpriteFont labelFont, nameFont, digitFont;
		int labelHeight, nameHeight;

		[ObjectCreator.UseCtor]
		public PxWeatherBadgeWidget(World world)
		{
			weather = world.WorldActor.TraitOrDefault<PxWeatherManager>();
			if (weather != null && !weather.Enabled)
				weather = null;

			tooltipContainer = Exts.Lazy(() => Ui.Root.Get<TooltipContainerWidget>(TooltipContainer));
		}

		public bool HasWeather => weather != null;

		static Color Accent(PxWeatherType type)
		{
			return Accents.TryGetValue(type, out var c) ? c : Color.White;
		}

		static Color Mix(Color a, Color b, float t)
		{
			t = Math.Clamp(t, 0, 1);
			return Color.FromArgb(
				(int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t),
				(int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}

		static Color Alpha(Color c, float a)
		{
			return Color.FromArgb((int)(Math.Clamp(a, 0, 1) * 255), c.R, c.G, c.B);
		}

		static string FormatTime(int seconds)
		{
			return $"{seconds / 60}:{seconds % 60:D2}";
		}

		int SecondsLeft => (weather.TicksUntilChange + weather.TicksPerSecond - 1) / weather.TicksPerSecond;

		bool Warning => weather.HasForecast && weather.Next != weather.Current && weather.TicksUntilChange <= weather.WarningTicks;

		public override void Draw()
		{
			if (weather == null)
				return;

			labelFont ??= Game.Renderer.Fonts[LabelFont];
			nameFont ??= Game.Renderer.Fonts[NameFont];
			digitFont ??= Game.Renderer.Fonts[DigitFont];
			if (labelHeight == 0)
			{
				labelHeight = labelFont.Measure("W").Y;
				nameHeight = nameFont.Measure("W").Y;
			}

			var rb = RenderBounds;
			var t = Game.RunTime / 1000f;
			var frame = weather.Frame();
			var current = weather.Current;

			// During a change the colours blend from the old weather to the new one
			var fade = weather.Transition;
			var accent = fade < 1 ? Mix(Accent(weather.Previous), Accent(current), fade) : Accent(current);
			var flash = Math.Clamp(frame.Flash, 0, 1);
			var warning = Warning;
			var pulse = 0.5f + 0.5f * MathF.Sin(t * 6f);

			// Warning: the whole badge picks up a pulsing amber edge
			if (warning)
				DrawOutline(rb, Alpha(WarningColor, 0.25f + 0.45f * pulse));

			var plate = new Rectangle(rb.X + 5, rb.Y + 4, 38, rb.Height - 8);
			DrawPlate(plate, accent, flash, current, t);

			// The badge is laid out from its own height: a label row, a name row and the timeline along the
			// bottom edge. Hardcoded offsets would run the timeline through the name row on a short badge.
			var timelineY = rb.Bottom - 4;
			var labelRow = rb.Y + Math.Max(2, (timelineY - 2 - rb.Y - labelHeight - 1 - nameHeight) / 2);
			var nameRow = labelRow + labelHeight + 1;

			// Current weather
			var x0 = plate.Right + 10;
			var divider = rb.Right - ForecastWidth;
			var title = FluentProvider.GetMessage(Title);
			labelFont.DrawText(title, new float2(x0, labelRow), LabelColor);
			if (fade < 1)
			{
				var tag = "· " + FluentProvider.GetMessage(Changing);
				labelFont.DrawText(tag, new float2(x0 + labelFont.Measure(title).X + 5, labelRow), Alpha(accent, 0.6f + 0.4f * pulse));
			}

			var name = WidgetUtils.TruncateText(PxWeatherManager.WeatherName(current).ToUpperInvariant(), divider - x0 - 8, nameFont);
			nameFont.DrawTextWithShadow(name, new float2(x0, nameRow), Mix(TextColor, Color.White, flash),
				Color.FromArgb(160, 0, 0, 0), 1);

			// Divider
			WidgetUtils.FillRectWithColor(new Rectangle(divider, rb.Y + 8, 1, rb.Height - 17), Color.FromArgb(46, 255, 255, 255));

			DrawForecast(new Rectangle(divider + 10, rb.Y, rb.Right - divider - 18, rb.Height), labelRow, nameRow, warning, pulse);
			DrawTimeline(new Rectangle(x0, timelineY, rb.Right - 8 - x0, 2), accent, warning, pulse);
		}

		void DrawPlate(Rectangle r, Color accent, float flash, PxWeatherType type, float t)
		{
			// Chamfered plate with a vertical gradient of the weather colour and a bright top edge
			const int Cut = 5;
			var top = Mix(Color.FromArgb(255, 18, 20, 26), accent, 0.42f + 0.4f * flash);
			var bottom = Mix(Color.FromArgb(255, 10, 11, 15), accent, 0.12f + 0.3f * flash);
			for (var y = 0; y < r.Height; y++)
			{
				var inset = y < Cut ? Cut - y : y >= r.Height - Cut ? y - (r.Height - Cut - 1) : 0;
				WidgetUtils.FillRectWithColor(new Rectangle(r.X + inset, r.Y + y, r.Width - 2 * inset, 1),
					Mix(top, bottom, y / (float)(r.Height - 1)));
			}

			WidgetUtils.FillRectWithColor(new Rectangle(r.X + Cut, r.Y, r.Width - 2 * Cut, 1), Alpha(Mix(accent, Color.White, 0.5f), 0.8f));
			WidgetUtils.FillRectWithColor(new Rectangle(r.X + Cut, r.Bottom - 1, r.Width - 2 * Cut, 1), Color.FromArgb(120, 0, 0, 0));

			DrawPrecipitation(r, type, accent, t);

			var center = new float2(r.X + r.Width / 2f, r.Y + r.Height / 2f);
			var id = type.ToString().ToLowerInvariant();

			// Soft halo, breathing slowly; lightning makes it bloom
			var glow = ChromeProvider.GetImage(IconCollection, id + "-glow");
			if (glow != null)
				DrawTinted(glow, center, 36, accent, 0.3f + 0.12f * MathF.Sin(t * 1.7f) + 0.6f * flash, 0);

			// The glyph moves a little with its weather
			var offset = float2.Zero;
			var rotation = 0f;
			var alpha = 1f;
			switch (type)
			{
				case PxWeatherType.Clear:
					rotation = t * 0.3f;
					break;
				case PxWeatherType.HeatHaze:
					offset = new float2(MathF.Sin(t * 3.1f) * 0.8f, MathF.Sin(t * 1.9f) * 0.8f);
					break;
				case PxWeatherType.StrongWind:
				case PxWeatherType.Sandstorm:
				case PxWeatherType.Blizzard:
					offset = new float2(MathF.Sin(t * 2.4f) * 1.5f, 0);
					break;
				case PxWeatherType.Fog:
					alpha = 0.75f + 0.25f * MathF.Sin(t * 1.3f);
					break;
				default:
					offset = new float2(0, MathF.Sin(t * 1.6f) * 0.9f - 2);
					break;
			}

			var icon = ChromeProvider.GetImage(IconCollection, id);
			if (icon != null)
				DrawTinted(icon, center + offset, 26, Mix(accent, Color.White, 0.55f + 0.45f * flash), alpha, rotation);
		}

		// Falling drops / flakes / grains inside the plate, under the cloud
		static void DrawPrecipitation(Rectangle r, PxWeatherType type, Color accent, float t)
		{
			int count;
			float speed;
			int2 size;
			switch (type)
			{
				case PxWeatherType.Rain:
					(count, speed, size) = (7, 26f, new int2(1, 4));
					break;
				case PxWeatherType.Thunderstorm:
					(count, speed, size) = (9, 34f, new int2(1, 5));
					break;
				case PxWeatherType.Snow:
					(count, speed, size) = (7, 9f, new int2(2, 2));
					break;
				case PxWeatherType.Blizzard:
					(count, speed, size) = (10, 20f, new int2(3, 1));
					break;
				case PxWeatherType.Sandstorm:
				case PxWeatherType.StrongWind:
					(count, speed, size) = (6, 30f, new int2(4, 1));
					break;
				default:
					return;
			}

			var horizontal = size.X > size.Y;
			var color = Alpha(Mix(accent, Color.White, 0.3f), 0.55f);
			for (var i = 0; i < count; i++)
			{
				// Fixed lanes with their own phase; travel loops through the plate
				var lane = (i * 37 % 29 + 4) / 36f;
				var phase = (i * 0.61f + t * speed / (horizontal ? r.Width : r.Height)) % 1f;
				int x, y;
				if (horizontal)
				{
					x = r.X + 3 + (int)(phase * (r.Width - 6 - size.X));
					y = r.Y + 4 + (int)(lane * (r.Height - 8));
				}
				else
				{
					x = r.X + 4 + (int)(lane * (r.Width - 8)) + (type == PxWeatherType.Snow ? (int)(MathF.Sin(t * 2 + i) * 1.5f) : 0);
					y = r.Y + r.Height / 2 + (int)(phase * (r.Height / 2 - 3 - size.Y));
				}

				var fadeEdge = MathF.Min(1, MathF.Min(phase, 1 - phase) * 6);
				WidgetUtils.FillRectWithColor(new Rectangle(x, y, size.X, size.Y), Alpha(color, color.A / 255f * fadeEdge));
			}
		}

		void DrawForecast(Rectangle r, int labelRow, int nameRow, bool warning, float pulse)
		{
			if (!weather.HasForecast)
			{
				labelFont.DrawText(FluentProvider.GetMessage(ForecastLabel), new float2(r.X, labelRow), LabelColor);
				nameFont.DrawText(FluentProvider.GetMessage(Stable), new float2(r.X, nameRow), LabelColor);
				return;
			}

			// Top line: NEXT / INCOMING and the countdown; bottom line: the next weather's icon and name
			var next = weather.Next;
			var labelColor = warning ? Mix(WarningColor, Color.White, 0.25f * pulse) : LabelColor;
			var label = FluentProvider.GetMessage(warning ? IncomingShort : NextShort);
			labelFont.DrawText(label, new float2(r.X, labelRow), labelColor);

			// The countdown shares the label row, so it keeps clear of the label it sits beside
			var time = FormatTime(SecondsLeft);
			var size = digitFont.Measure(time);
			var digits = warning ? Mix(WarningColor, Color.White, 0.3f * pulse) : TextColor;
			var timeX = Math.Max(r.X + labelFont.Measure(label).X + 6, r.Right - size.X);
			digitFont.DrawTextWithShadow(time, new float2(timeX, labelRow - (size.Y - labelHeight) / 2), digits,
				Color.FromArgb(160, 0, 0, 0), 1);

			var small = ChromeProvider.GetImage(IconCollection, next.ToString().ToLowerInvariant() + "-small");
			if (small != null)
				DrawTinted(small, new float2(r.X + 8, nameRow + nameHeight / 2f), 17, Mix(Accent(next), Color.White, 0.35f), 1, 0);

			var nameX = r.X + 21;
			var nextName = WidgetUtils.TruncateText(PxWeatherManager.WeatherName(next).ToUpperInvariant(), r.Right - nameX, labelFont);
			labelFont.DrawText(nextName, new float2(nameX, nameRow + (nameHeight - labelHeight) / 2), Mix(Accent(next), Color.White, 0.5f));
		}

		void DrawTimeline(Rectangle r, Color accent, bool warning, float pulse)
		{
			WidgetUtils.FillRectWithColor(r, Color.FromArgb(70, 0, 0, 0));
			if (!weather.HasForecast)
				return;

			var left = Math.Clamp(weather.TicksUntilChange / (float)weather.ForecastTotalTicks, 0, 1);
			var w = (int)(r.Width * left);
			if (w <= 0)
				return;

			var color = warning ? Mix(WarningColor, Color.White, 0.3f * pulse) : accent;
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, w, r.Height), Alpha(color, 0.85f));

			// Bright head with a soft glow where the time runs out
			WidgetUtils.FillRectWithColor(new Rectangle(r.X + w - 2, r.Y - 1, 2, r.Height + 2), Mix(color, Color.White, 0.6f));
			WidgetUtils.FillRectWithColor(new Rectangle(r.X + w - 6, r.Y - 1, 4, r.Height + 2), Alpha(color, 0.35f));
		}

		static void DrawOutline(Rectangle r, Color c)
		{
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, r.Width, 1), c);
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Bottom - 1, r.Width, 1), c);
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, 1, r.Height), c);
			WidgetUtils.FillRectWithColor(new Rectangle(r.Right - 1, r.Y, 1, r.Height), c);
		}

		static void DrawTinted(Sprite sprite, float2 center, float size, Color tint, float alpha, float rotation)
		{
			var scale = size / Math.Max(sprite.Size.X, sprite.Size.Y);
			var pos = center - 0.5f * scale * sprite.Size.XY;
			Game.Renderer.RgbaSpriteRenderer.DrawSprite(sprite, new float3(pos, 0), scale,
				new float3(tint.R / 255f, tint.G / 255f, tint.B / 255f), Math.Clamp(alpha, 0, 1), rotation);
		}

		string TooltipText()
		{
			var lines = new List<string>
			{
				FluentProvider.GetMessage(TooltipNow, "weather", PxWeatherManager.WeatherName(weather.Current)),
				weather.HasForecast
					? FluentProvider.GetMessage(TooltipNext, "weather", PxWeatherManager.WeatherName(weather.Next), "time", FormatTime(SecondsLeft))
					: FluentProvider.GetMessage(TooltipFixed),
				FluentProvider.GetMessage(TooltipMode)
			};

			return string.Join("\n", lines);
		}

		public override void MouseEntered()
		{
			if (TooltipContainer == null || weather == null)
				return;

			tooltipContainer.Value.SetTooltip(TooltipTemplate, new WidgetArgs() { { "getText", (Func<string>)TooltipText } });
		}

		public override void MouseExited()
		{
			if (TooltipContainer != null && tooltipContainer.IsValueCreated)
				tooltipContainer.Value.RemoveTooltip();
		}
	}
}
