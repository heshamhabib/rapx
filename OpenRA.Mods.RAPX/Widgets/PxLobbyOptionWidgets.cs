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
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	static class PxDraw
	{
		public static readonly Color Accent = Color.FromArgb(226, 38, 38);
		public static readonly Color AccentBright = Color.FromArgb(255, 106, 85);
		public static readonly Color Muted = Color.FromArgb(157, 158, 166);
		public static readonly Color Dim = Color.FromArgb(138, 139, 147);

		public static Sprite[] Panel(string name) => ChromeProvider.TryGetPanelImages(name) ?? ChromeProvider.GetPanelImages("px-row");
	}

	/// <summary>A lobby checkbox drawn as a row: icon tile, label, one-line hint and a skinned checkbox.</summary>
	public class PxOptionSwitchWidget : CheckboxWidget
	{
		public string Icon = "default";
		public Func<string> GetHint = () => "";
		public readonly string IconCollection = "px-option-icons";
		public readonly string HintFont = "PXSmall";
		public readonly string CheckboxCollection = "px-checkbox";

		[ObjectCreator.UseCtor]
		public PxOptionSwitchWidget(ModData modData)
			: base(modData) { }

		protected PxOptionSwitchWidget(PxOptionSwitchWidget other)
			: base(other)
		{
			Icon = other.Icon;
			GetHint = other.GetHint;
			IconCollection = other.IconCollection;
			HintFont = other.HintFont;
			CheckboxCollection = other.CheckboxCollection;
		}

		public override Widget Clone() { return new PxOptionSwitchWidget(this); }

		public override void Draw()
		{
			var rb = RenderBounds;
			var on = IsChecked();
			var disabled = IsDisabled();
			var hover = Ui.MouseOverWidget == this && !disabled;
			WidgetUtils.DrawPanel(rb, PxDraw.Panel(hover ? "px-row-hover" : "px-row"));

			// Icon tile
			var tile = new Rectangle(rb.X + 10, rb.Y + (rb.Height - 32) / 2, 32, 32);
			WidgetUtils.FillRectWithColor(tile, on ? Color.FromArgb(46, 226, 38, 38) : Color.FromArgb(27, 28, 33));
			var icon = ChromeProvider.TryGetImage(IconCollection, on ? Icon : Icon + "-off");
			if (icon != null)
				WidgetUtils.DrawSprite(icon, new float2(tile.X + (32 - icon.Size.X) / 2, tile.Y + (32 - icon.Size.Y) / 2));

			var font = Game.Renderer.Fonts[Font];
			var label = GetText();
			var textColor = disabled ? GetColorDisabled() : on ? Color.White : Color.FromArgb(185, 186, 194);
			// Label and hint form a 38px block, centred so shorter rows still read cleanly
			var textTop = rb.Y + (rb.Height - 38) / 2;
			font.DrawText(label, new float2(tile.Right + 12, textTop), textColor);

			var hintFont = Game.Renderer.Fonts[HintFont];
			var hint = WidgetUtils.TruncateText(GetHint() ?? "", rb.Right - 50 - tile.Right - 12, hintFont);
			hintFont.DrawText(hint, new float2(tile.Right + 12, textTop + 20), PxDraw.Dim);

			// Checkbox
			var box = ChromeProvider.TryGetImage(CheckboxCollection, (on ? "on" : "off") + (disabled ? "-disabled" : hover ? "-hover" : ""));
			if (box != null)
				WidgetUtils.DrawSprite(box, new float2(rb.Right - 10 - box.Size.X, rb.Y + (rb.Height - box.Size.Y) / 2));
		}
	}

	/// <summary>A lobby dropdown drawn as a card: icon, small caps title and the current value in large type.</summary>
	public class PxOptionCardWidget : DropDownButtonWidget
	{
		public string Icon = "default";
		public Func<string> GetTitle = () => "";
		public readonly string IconCollection = "px-option-icons";
		public readonly string TitleFont = "PXSidebarSmall";
		public readonly string ValueFont = "PXDigitsMedium";
		public Color ValueColor = Color.FromArgb(232, 230, 227);

		[ObjectCreator.UseCtor]
		public PxOptionCardWidget(ModData modData)
			: base(modData) { }

		protected PxOptionCardWidget(PxOptionCardWidget other)
			: base(other)
		{
			Icon = other.Icon;
			GetTitle = other.GetTitle;
			IconCollection = other.IconCollection;
			TitleFont = other.TitleFont;
			ValueFont = other.ValueFont;
			ValueColor = other.ValueColor;
		}

		public override Widget Clone() { return new PxOptionCardWidget(this); }

		public override void Draw()
		{
			var rb = RenderBounds;
			var disabled = IsDisabled();
			var hover = (Ui.MouseOverWidget == this || Depressed) && !disabled;
			WidgetUtils.DrawPanel(rb, PxDraw.Panel(hover ? "px-row-hover" : "px-row"));

			var icon = ChromeProvider.TryGetImage(IconCollection, disabled ? Icon + "-off" : Icon);
			if (icon != null)
				WidgetUtils.DrawSprite(icon, new float2(rb.X + 12, rb.Y + 12));

			var titleFont = Game.Renderer.Fonts[TitleFont];
			var title = WidgetUtils.TruncateText((GetTitle() ?? "").ToUpperInvariant(), rb.Width - 64, titleFont);
			titleFont.DrawText(title, new float2(rb.X + 38, rb.Y + 15), PxDraw.Muted);

			// Dropdown arrow from the skin
			var arrow = ChromeProvider.TryGetImage(Decorations, DecorationMarker);
			if (arrow != null)
				WidgetUtils.DrawSprite(arrow, new float2(rb.Right - 12 - arrow.Size.X, rb.Y + 22 - arrow.Size.Y / 2));

			var valueFont = Game.Renderer.Fonts[ValueFont];
			var value = WidgetUtils.TruncateText((GetText() ?? "").ToUpperInvariant(), rb.Width - 24, valueFont);
			// Value sits 40px down on a full card, moving up (clear of the title) when cards are shortened to fit
			valueFont.DrawText(value, new float2(rb.X + 12, rb.Y + Math.Min(40, rb.Height - 32)), disabled ? PxDraw.Dim : ValueColor);
		}
	}
}
