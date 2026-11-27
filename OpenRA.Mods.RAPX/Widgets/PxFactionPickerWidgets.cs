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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Faction dropdown panel shown as a card grid: the first group (Union) fills the left column, the second
	/// (Vanguard) the right column and any further group (Random) a row along the bottom. Used as the lobby's
	/// FACTION_DROPDOWN_TEMPLATE, so the engine still creates the items and handles the selection.
	/// </summary>
	public class PxFactionPickerPanelWidget : ScrollPanelWidget
	{
		public readonly string Title = PxText.N("CHOOSE YOUR NATION");
		public readonly string TitleFont = "PXDisplay";
		public readonly int Padding = 16;
		public readonly int TitleHeight = 46;
		public readonly int ColumnGap = 14;
		public readonly int CardGap = 6;
		public readonly int RowGap = 12;

		[ObjectCreator.UseCtor]
		public PxFactionPickerPanelWidget(ModData modData)
			: base(modData) { }

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			Layout = new GridLayout(this);
		}

		public override void Tick()
		{
			base.Tick();

			// ShowDropDown caps the height for a plain list; show every card instead and stay on screen
			if (Bounds.Height != ContentHeight)
			{
				// The dropdown scrolled to the selected item while it was still short; every card now fits
				Bounds.Height = ContentHeight;
				ScrollToTop();
				if (Parent != null)
				{
					var screen = Game.Renderer.Resolution;
					var maxY = screen.Height - Parent.RenderOrigin.Y - Bounds.Height - 8;
					var maxX = screen.Width - Parent.RenderOrigin.X - Bounds.Width - 8;
					Bounds.Y = Math.Max(8 - Parent.RenderOrigin.Y, Math.Min(Bounds.Y, maxY));
					Bounds.X = Math.Max(8 - Parent.RenderOrigin.X, Math.Min(Bounds.X, maxX));
				}
			}
		}

		public override void DrawOuter()
		{
			base.DrawOuter();
			var font = Game.Renderer.Fonts[TitleFont];
			var rb = RenderBounds;
			font.DrawTextWithShadow(PxText.T(Title), new float2(rb.X + Padding + 4, rb.Y + 14), Color.White, Color.Black, 1);
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X + Padding, rb.Y + TitleHeight - 6, rb.Width - 2 * Padding, 1),
				Color.FromArgb(60, 255, 106, 85));
		}

		sealed class GridLayout : ILayout
		{
			readonly PxFactionPickerPanelWidget panel;

			public GridLayout(PxFactionPickerPanelWidget panel) { this.panel = panel; }

			// ScrollPanelWidget calls this before the new child joins Children, so lay it out with the others
			public void AdjustChild(Widget w) { Layout(panel.Children.Contains(w) ? panel.Children : panel.Children.Append(w)); }

			public void AdjustChildren() { Layout(panel.Children); }

			void Layout(IEnumerable<Widget> children)
			{
				var p = panel;
				var width = p.Bounds.Width - 2 * p.Padding;
				var columnWidth = (width - p.ColumnGap) / 2;
				var columnY = new[] { p.TitleHeight, p.TitleHeight };
				var group = -1;
				var bottomY = 0;
				var bottomX = 0;
				var bottomRow = new List<Widget>();

				foreach (var w in children)
				{
					if (w.Id == "HEADER")
					{
						group++;
						if (group < 2)
						{
							w.Bounds.X = p.Padding + group * (columnWidth + p.ColumnGap);
							w.Bounds.Y = columnY[group];
							w.Bounds.Width = columnWidth;
							columnY[group] += w.Bounds.Height + p.CardGap;
						}
						else
						{
							bottomY = Math.Max(columnY[0], columnY[1]) + p.RowGap;
							w.Bounds.X = p.Padding;
							w.Bounds.Y = bottomY;
							w.Bounds.Width = width;
							bottomY += w.Bounds.Height + p.CardGap;
						}

						continue;
					}

					var column = Math.Max(group, 0);
					if (column < 2)
					{
						w.Bounds.X = p.Padding + column * (columnWidth + p.ColumnGap);
						w.Bounds.Y = columnY[column];
						w.Bounds.Width = columnWidth;
						columnY[column] += w.Bounds.Height + p.CardGap;
					}
					else
						bottomRow.Add(w);
				}

				// Random options share the bottom row
				if (bottomRow.Count > 0)
				{
					var itemWidth = (width - (bottomRow.Count - 1) * p.CardGap) / bottomRow.Count;
					foreach (var w in bottomRow)
					{
						w.Bounds.X = p.Padding + bottomX;
						w.Bounds.Y = bottomY;
						w.Bounds.Width = itemWidth;
						w.Bounds.Height = 50;
						bottomX += itemWidth + p.CardGap;
					}

					bottomY += 50;
				}

				p.ContentHeight = Math.Max(Math.Max(columnY[0], columnY[1]), bottomY) + p.Padding;
			}
		}
	}

	/// <summary>
	/// Draws a faction card's large flag, motto, special ability and side accent (Mode Card), a side header
	/// (Mode Header), or the large flag and side on the player row's faction button (Mode Button).
	/// The faction id comes from the sibling flag image that the lobby logic binds.
	/// </summary>
	public class PxFactionDecorWidget : Widget
	{
		public enum DecorMode { Card, Header, Button }

		public readonly DecorMode Mode = DecorMode.Card;

		[Desc("Id of the sibling ImageWidget whose image name is the faction id.")]
		public readonly string FlagWidget = "FLAG";

		public readonly string MottoFont = "PXSmall";
		public readonly string SpecialFont = "PXSidebarSmall";
		public readonly int2 FlagSize = new(60, 40);

		static readonly Color Allied = Color.FromArgb(58, 123, 255);
		static readonly Color AlliedText = Color.FromArgb(143, 182, 255);
		static readonly Color Soviet = Color.FromArgb(226, 38, 38);
		static readonly Color SovietText = Color.FromArgb(255, 138, 122);
		static readonly Color Neutral = Color.FromArgb(110, 111, 120);
		static readonly Color Gold = Color.FromArgb(255, 209, 102);

		readonly ModData modData;
		Dictionary<string, (string Side, string Motto, string Special)> factions;

		[ObjectCreator.UseCtor]
		public PxFactionDecorWidget(ModData modData)
		{
			this.modData = modData;
			IgnoreMouseOver = true;
		}

		protected PxFactionDecorWidget(PxFactionDecorWidget other)
			: base(other)
		{
			modData = other.modData;
			Mode = other.Mode;
			FlagWidget = other.FlagWidget;
			MottoFont = other.MottoFont;
			SpecialFont = other.SpecialFont;
			FlagSize = other.FlagSize;
			factions = other.factions;
			IgnoreMouseOver = true;
		}

		public override Widget Clone() { return new PxFactionDecorWidget(this); }

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		(string Side, string Motto, string Special) Lookup(string id)
		{
			factions ??= modData.DefaultRules.Actors[SystemActors.World].TraitInfos<FactionInfo>()
				.Where(f => f.InternalName != null)
				.GroupBy(f => f.InternalName)
				.ToDictionary(g => g.Key, g =>
				{
					var f = g.First();
					var lines = f.Description != null ? FluentProvider.GetMessage(f.Description).Split('\n') : Array.Empty<string>();
					var first = lines.Length > 0 ? lines[0].Trim() : "";
					var colon = first.IndexOfAny(new[] { ':', '：' });
					var motto = colon >= 0 ? first[(colon + 1)..].Trim() : first;
					var special = lines.Length > 1 ? lines[1].Trim().ToUpperInvariant() : "";
					return (f.Side ?? "", motto, special);
				});

			return factions.TryGetValue(id, out var v) ? v : ("", "", "");
		}

		static Color SideColor(string side) => side == "Union" ? Allied : side == "Vanguard" ? Soviet : Neutral;
		static Color SideText(string side) => side == "Union" ? AlliedText : side == "Vanguard" ? SovietText : Color.FromArgb(185, 186, 194);

		public override void Draw()
		{
			var rb = Parent.RenderBounds;
			if (Mode == DecorMode.Header)
			{
				DrawHeader(rb);
				return;
			}

			var flag = Parent.GetOrNull<ImageWidget>(FlagWidget);
			var id = flag?.GetImageName();
			if (string.IsNullOrEmpty(id))
				return;

			var (side, motto, special) = Lookup(id);
			var sprite = ChromeProvider.TryGetImage("flags-large", id) ?? ChromeProvider.TryGetImage("flags", id);
			var y = rb.Y + (rb.Height - FlagSize.Y) / 2;

			if (Mode == DecorMode.Button)
			{
				if (sprite != null)
					WidgetUtils.DrawSprite(sprite, new float2(rb.X + 8, y), FlagSize);

				var font = Game.Renderer.Fonts[SpecialFont];
				var label = side == "Random" ? PxText.T("RANDOM") : PxText.T(side).ToUpperInvariant();
				font.DrawText(label, new float2(rb.X + FlagSize.X + 16, rb.Bottom - font.Measure(label).Y - 6), SideText(side));
				return;
			}

			// Card: side accent, large flag, motto and special line under the engine's name label
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Y + 2, 3, rb.Height - 4), SideColor(side));
			if (sprite != null)
			{
				WidgetUtils.FillRectWithColor(new Rectangle(rb.X + 11, y + 2, FlagSize.X, FlagSize.Y), Color.FromArgb(140, 0, 0, 0));
				WidgetUtils.DrawSprite(sprite, new float2(rb.X + 10, y), FlagSize);
			}

			var textX = rb.X + FlagSize.X + 22;
			var motto2 = side == "Random" ? "" : motto;
			if (!string.IsNullOrEmpty(motto2))
				Game.Renderer.Fonts[MottoFont].DrawText(motto2, new float2(textX, rb.Y + 26), Color.FromArgb(200, 201, 208));

			if (!string.IsNullOrEmpty(special) && side != "Random")
			{
				// Special lines read "Special Unit: X" in every language; the generic arsenal lines have no colon
				var isSpecial = special.Contains(':') || special.Contains('：');
				var specialFont = Game.Renderer.Fonts[SpecialFont];
				var line = WidgetUtils.TruncateText(special, rb.Right - textX - 8, specialFont);
				specialFont.DrawText(line, new float2(textX, rb.Y + 42), isSpecial ? Gold : Color.FromArgb(138, 139, 147));
			}

			if (Parent is ScrollItemWidget item && item.IsSelected())
			{
				var c = new float2(rb.Right - 20, rb.Y + rb.Height / 2);
				WidgetUtils.FillEllipseWithColor(new Rectangle((int)c.X - 11, (int)c.Y - 11, 22, 22), Soviet);
				var tick = ChromeProvider.TryGetImage("px-lobby-icons", "tick");
				if (tick != null)
					WidgetUtils.DrawSprite(tick, c - 0.5f * tick.Size.XY);
			}
		}

		void DrawHeader(Rectangle rb)
		{
			var label = Parent.GetOrNull<LabelWidget>("LABEL");
			var text = label?.GetText() ?? "";
			var side = text.StartsWith("Union", StringComparison.OrdinalIgnoreCase) ? "Union" :
				text.StartsWith("Vanguard", StringComparison.OrdinalIgnoreCase) ? "Vanguard" : "Random";
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Bottom - 2, rb.Width, 2), SideColor(side));
			var emblem = ChromeProvider.TryGetImage("flags", side == "Union" ? "RandomAllies" : side == "Vanguard" ? "RandomSoviet" : "Random");
			if (emblem != null)
				WidgetUtils.DrawSprite(emblem, new float2(rb.X + 2, rb.Y + (rb.Height - 15) / 2 - 1), new float2(30, 15));
		}
	}
}
