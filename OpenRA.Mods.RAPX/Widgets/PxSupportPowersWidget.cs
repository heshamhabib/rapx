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
using System.Reflection;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Support power bin drawn as armoured launch panels: steel frame, recessed icon screen with a charging shutter,
	/// LCD countdown strip, pulsing green READY and hazard-striped ON HOLD. Behaviour (clicks, hotkeys, tooltips) is stock.
	/// </summary>
	public class PxSupportPowersWidget : SupportPowersWidget
	{
		static readonly FieldInfo IconsField = typeof(SupportPowersWidget).GetField("icons", BindingFlags.NonPublic | BindingFlags.Instance);

		public readonly string LabelFont = "PXSidebarSmall";
		public readonly string DigitFont = "PXDigitsSmall";
		public readonly Color FrameColor = Color.FromArgb(96, 100, 86);
		public readonly int Cut = 8;

		[Desc("Height of the status strip under the icon screen.")]
		public readonly int StripHeight = 16;

		readonly World world;

		[ObjectCreator.UseCtor]
		public PxSupportPowersWidget(ModData modData, World world, WorldRenderer worldRenderer)
			: base(modData, world, worldRenderer)
		{
			this.world = world;
		}

		public override void Draw()
		{
			if (IconsField.GetValue(this) is not Dictionary<Rectangle, SupportPowerIcon> icons)
				return;

			var labelFont = Game.Renderer.Fonts[LabelFont];
			var digitFont = Game.Renderer.Fonts[DigitFont];
			var hovered = TooltipIcon;
			foreach (var (r, icon) in icons)
				DrawPanel(r, icon, icon == hovered, labelFont, digitFont);
		}

		void DrawPanel(Rectangle r, SupportPowerIcon icon, bool hover, SpriteFont labelFont, SpriteFont digitFont)
		{
			var p = icon.Power;
			var hold = !p.Active;
			var ready = p.Ready;
			var custom = p.IconOverlayTextOverride();
			var readyPulse = PxWarChrome.Pulse(900);

			var rim = ready ? PxWarChrome.Lerp(PxWarChrome.Darken(PxWarChrome.Friendly, 0.3f), PxWarChrome.Friendly, readyPulse)
				: hold ? PxWarChrome.Darken(PxWarChrome.Hazard, 0.35f)
				: FrameColor;
			if (hover)
				rim = PxWarChrome.Lerp(rim, Color.White, 0.3f);

			PxWarChrome.DrawSteelPlate(r, Cut, rim, ready ? 0.35f + 0.65f * readyPulse : 0, PxWarChrome.Friendly);
			PxWarChrome.DrawRivet(new int2(r.Right - 5, r.Y + 5));
			PxWarChrome.DrawRivet(new int2(r.X + 5, r.Bottom - 5));

			// Icon screen
			var screen = new Rectangle(r.X + 6, r.Y + 6, r.Width - 12, r.Height - StripHeight - 15);
			PxWarChrome.DrawWell(screen);
			Game.Renderer.EnableScissor(screen);
			var sprite = icon.Sprite;
			var scale = Math.Min((screen.Width - 2) / sprite.Size.X, (screen.Height - 2) / sprite.Size.Y);
			var center = new float2(screen.X + screen.Width / 2f, screen.Y + screen.Height / 2f);
			Game.Renderer.EnableAntialiasingFilter();
			WidgetUtils.DrawSpriteCentered(sprite, icon.Palette, center, scale);
			Game.Renderer.DisableAntialiasingFilter();

			if (hold)
			{
				WidgetUtils.FillRectWithColor(screen, Color.FromArgb(150, 10, 10, 8));
				PxWarChrome.DrawHazard(new Rectangle(screen.X, screen.Y + screen.Height / 2 - 6, screen.Width, 12), (int)(Game.RunTime / 60), 150);
			}
			else if (!ready)
			{
				// Charging shutter: closes from the top, opening as the charge builds up
				var remaining = p.TotalTicks == 0 ? 0 : p.RemainingTicks / (float)p.TotalTicks;
				var h = (int)(screen.Height * remaining);
				if (h > 0)
				{
					WidgetUtils.FillRectWithColor(new Rectangle(screen.X, screen.Y, screen.Width, h), Color.FromArgb(165, 6, 8, 6));
					WidgetUtils.FillRectWithColor(new Rectangle(screen.X, screen.Y + h - 1, screen.Width, 1), Color.FromArgb(200, PxWarChrome.Amber));
					WidgetUtils.FillRectWithColor(new Rectangle(screen.X, screen.Y + h, screen.Width, 3), Color.FromArgb(50, PxWarChrome.Amber));
				}
			}
			else
			{
				// Armed: a highlight sweeps across the screen
				var sweep = Game.RunTime % 1800 / 1800f;
				var x = screen.X - 20 + (int)((screen.Width + 40) * sweep);
				Game.Renderer.RgbaColorRenderer.FillRect(new float3(x, screen.Bottom, 0), new float3(x + 10, screen.Bottom, 0),
					new float3(x + 22, screen.Y, 0), new float3(x + 12, screen.Y, 0), Color.FromArgb(50, 255, 255, 255));
				PxWarChrome.DrawBorder(screen, Color.FromArgb((int)(80 + 150 * readyPulse), PxWarChrome.Friendly), 1);
			}

			// Scanlines over the screen
			for (var y = screen.Y + 1; y < screen.Bottom; y += 3)
				WidgetUtils.FillRectWithColor(new Rectangle(screen.X, y, screen.Width, 1), Color.FromArgb(16, 0, 0, 0));
			Game.Renderer.DisableScissor();

			// Hotkey tag
			var key = icon.Hotkey?.GetValue();
			if (key != null && key.Value.IsValid())
			{
				var text = key.Value.DisplayString();
				var size = labelFont.Measure(text);
				var tag = new Rectangle(screen.X, screen.Y, size.X + 6, size.Y + 1);
				WidgetUtils.FillRectWithColor(tag, Color.FromArgb(200, 12, 13, 11));
				labelFont.DrawText(text, new float2(tag.X + 3, tag.Y), Color.FromArgb(200, PxWarChrome.Stencil));
			}

			// Status strip
			var strip = new Rectangle(r.X + 6, r.Bottom - StripHeight - 6, r.Width - 12, StripHeight);
			PxWarChrome.DrawWell(strip);
			if (custom != null)
				DrawCentered(labelFont, custom.ToUpperInvariant(), strip, PxWarChrome.Stencil, 1);
			else if (ready)
				DrawCentered(labelFont, ReadyText, strip, Game.LocalTick % 50 < 25 ? PxWarChrome.Friendly : Color.FromArgb(220, 255, 255, 255), 2);
			else if (hold)
			{
				PxWarChrome.DrawHazard(strip.InflateBy(-1, -1, -1, -1), 0, 120);
				var chip = strip.InflateBy(-10, -1, -10, -1);
				WidgetUtils.FillRectWithColor(chip, Color.FromArgb(230, 12, 12, 10));
				DrawCentered(labelFont, HoldText, strip, Game.LocalTick % 50 < 32 ? PxWarChrome.Hazard : PxWarChrome.Darken(PxWarChrome.Hazard, 0.4f), 1);
			}
			else
			{
				var time = WidgetUtils.FormatTime(p.RemainingTicks, false, world.Timestep);
				var size = digitFont.Measure(time);
				digitFont.DrawTextWithContrast(time, new float2(strip.X + (strip.Width - size.X) / 2, strip.Y + (strip.Height - size.Y) / 2),
					PxWarChrome.Amber, Color.FromArgb(70, PxWarChrome.Amber), 1);
			}
		}

		static void DrawCentered(SpriteFont font, string text, Rectangle r, Color color, int spacing)
		{
			var w = PxWarChrome.SpacedWidth(font, text, spacing);
			var h = font.Measure(text).Y;
			PxWarChrome.DrawSpaced(font, text, r.X + (r.Width - w) / 2, r.Y + (r.Height - h) / 2, spacing, color);
		}
	}
}
