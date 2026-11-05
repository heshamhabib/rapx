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
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Replaces the mixer/palette colour chooser (COLOR_CHOOSER) with a fixed grid of team colours. Colours too
	/// close to another player's are shown as taken. Picking one applies it and closes the dropdown.
	/// </summary>
	public class PxColorPickerLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxColorPickerLogic(Widget widget, ModData modData, Color initialColor, Action<Color> onChange,
			Action<Widget> extraLogic, Dictionary<string, MiniYaml> logicArgs)
		{
			var grid = widget.Get("SWATCHES");
			var template = grid.Get<PxColorSwatchWidget>("SWATCH_TEMPLATE");
			grid.RemoveChildren();

			var columns = logicArgs.TryGetValue("Columns", out var c) ? FieldLoader.GetValue<int>("Columns", c.Value) : 5;
			var colors = logicArgs.TryGetValue("Colors", out var list) ? FieldLoader.GetValue<Color[]>("Colors", list.Value) : Array.Empty<Color>();
			var manager = modData.DefaultRules.Actors[SystemActors.World].TraitInfoOrDefault<ColorPickerManagerInfo>();

			// Other players' colours (the colour being edited is the one we were opened with)
			IEnumerable<Color> OtherColors()
			{
				var lobby = PxLobbyState.OrderManager?.LobbyInfo;
				return lobby == null ? Enumerable.Empty<Color>() :
					lobby.Clients.Where(cl => cl.Slot != null && cl.Color != initialColor).Select(cl => cl.Color);
			}

			var current = initialColor;
			const int Gap = 6;
			for (var i = 0; i < colors.Length; i++)
			{
				var color = colors[i];
				var swatch = (PxColorSwatchWidget)template.Clone();
				swatch.Bounds.X = i % columns * (template.Bounds.Width + Gap);
				swatch.Bounds.Y = i / columns * (template.Bounds.Height + Gap);
				swatch.SwatchColor = color;
				swatch.IsSelected = () => current == color;
				swatch.IsTaken = () => manager != null && current != color && manager.IsInvalidColor(color, OtherColors());
				swatch.OnPick = () =>
				{
					current = color;
					onChange(color);
					ClosePanel(widget);
				};

				grid.AddChild(swatch);
			}

			extraLogic(widget);

			// Tint the preview building with the current colour
			onChange(initialColor);
		}

		static void ClosePanel(Widget panel)
		{
			// The dropdown closes (and commits the colour) when its click-catching mask is clicked
			var mask = panel.Parent?.Children.OfType<MaskWidget>().LastOrDefault();
			if (mask != null)
				Game.RunAfterTick(() => mask.HandleMouseInput(new MouseInput(MouseInputEvent.Down, MouseButton.Left, int2.Zero, int2.Zero, Modifiers.None, 1)));
		}
	}

	/// <summary>One colour swatch: a chamfered tile with a glow on hover, a ring and tick when selected, and a strike when taken.</summary>
	public class PxColorSwatchWidget : Widget
	{
		public Color SwatchColor = Color.White;
		public Func<bool> IsSelected = () => false;
		public Func<bool> IsTaken = () => false;
		public Action OnPick = () => { };

		public PxColorSwatchWidget() { }

		protected PxColorSwatchWidget(PxColorSwatchWidget other)
			: base(other)
		{
			SwatchColor = other.SwatchColor;
			IsSelected = other.IsSelected;
			IsTaken = other.IsTaken;
			OnPick = other.OnPick;
		}

		public override Widget Clone() { return new PxColorSwatchWidget(this); }

		public override bool HandleMouseInput(MouseInput mi)
		{
			if (mi.Event != MouseInputEvent.Down || mi.Button != MouseButton.Left)
				return mi.Event == MouseInputEvent.Up;

			if (IsTaken())
			{
				Game.Sound.PlayNotification(Game.ModData.DefaultRules, null, "Sounds", ChromeMetrics.Get<string>("ClickDisabledSound"), null);
				return true;
			}

			Game.Sound.PlayNotification(Game.ModData.DefaultRules, null, "Sounds", ChromeMetrics.Get<string>("ClickSound"), null);
			OnPick();
			return true;
		}

		public override void Draw()
		{
			var rb = RenderBounds;
			var selected = IsSelected();
			var taken = IsTaken();
			var hover = Ui.MouseOverWidget == this && !taken;

			if (selected || hover)
				WidgetUtils.FillRectWithColor(rb.InflateBy(3, 3, 3, 3), Color.FromArgb(selected ? 120 : 70, SwatchColor));

			WidgetUtils.FillRectWithColor(rb, selected ? Color.White : hover ? Color.FromArgb(255, 106, 85) : Color.FromArgb(52, 53, 60));
			var inner = rb.InflateBy(-2, -2, -2, -2);
			var shade = taken ? Color.FromArgb(255, SwatchColor.R / 3, SwatchColor.G / 3, SwatchColor.B / 3) : SwatchColor;
			var dark = Color.FromArgb(255, shade.R * 3 / 4, shade.G * 3 / 4, shade.B * 3 / 4);
			WidgetUtils.FillRectWithColor(inner, shade, shade, dark, dark);

			// Bevel highlight
			WidgetUtils.FillRectWithColor(new Rectangle(inner.X, inner.Y, inner.Width, 2), Color.FromArgb(70, 255, 255, 255));

			var icon = ChromeProvider.TryGetImage("px-lobby-icons", taken ? "taken" : "tick");
			if (icon == null || (!taken && !selected))
				return;

			var c = new float2(inner.X + inner.Width / 2f, inner.Y + inner.Height / 2f);
			if (selected)
				WidgetUtils.FillEllipseWithColor(new Rectangle((int)c.X - 11, (int)c.Y - 11, 22, 22), Color.FromArgb(150, 0, 0, 0));

			WidgetUtils.DrawSprite(icon, c - 0.5f * icon.Size.XY);
		}
	}
}
