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
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// The look of a titan choice (lobby TITAN column, art from artsrc/px-ui/make_titan_art.py): reads the titan id from
	/// a sibling ImageWidget (set by LobbyUtils) and draws its portrait or banner, its accent colour and its lines from
	/// PxTitanSpawner. Button: the row's dropdown. Card: picker entry (banner art for a titan, a portrait for None and
	/// Random), with the selected tick.
	/// </summary>
	public class PxTitanDecorWidget : Widget
	{
		public enum DecorMode { Button, Card }

		public readonly DecorMode Mode = DecorMode.Button;

		[Desc("Id of the sibling ImageWidget whose image name is the titan id (empty = none).")]
		public readonly string PortraitWidget = "PORTRAIT";

		public readonly int2 PortraitSize = new(48, 32);
		public readonly string SubtitleFont = "PXSidebarSmall";
		public readonly string SpecialFont = "PXSmall";
		public readonly string NameFont = "PXDisplay";
		public readonly string SlimNameFont = "PXButton";

		static readonly Color Gold = Color.FromArgb(255, 209, 102);
		static readonly Color NoneColor = Color.FromArgb(110, 111, 120);
		static readonly Color RandomColor = Color.FromArgb(255, 140, 170);

		readonly ModData modData;
		PxTitanSpawnerInfo info;

		[ObjectCreator.UseCtor]
		public PxTitanDecorWidget(ModData modData)
		{
			this.modData = modData;
			IgnoreMouseOver = true;
		}

		protected PxTitanDecorWidget(PxTitanDecorWidget other)
			: base(other)
		{
			modData = other.modData;
			Mode = other.Mode;
			PortraitWidget = other.PortraitWidget;
			PortraitSize = other.PortraitSize;
			SubtitleFont = other.SubtitleFont;
			SpecialFont = other.SpecialFont;
			NameFont = other.NameFont;
			SlimNameFont = other.SlimNameFont;
			IgnoreMouseOver = true;
		}

		public override Widget Clone() { return new PxTitanDecorWidget(this); }

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		PxTitanSpawnerInfo Info => info ??= modData.DefaultRules.Actors[SystemActors.World].TraitInfoOrDefault<PxTitanSpawnerInfo>();

		public static bool IsTitan(string id) => !string.IsNullOrEmpty(id) && id != "none" && id != "random";

		string Line(Dictionary<string, string> lines, string id, string fallback) =>
			Info != null && lines.TryGetValue(id, out var s) ? s : fallback;

		Color Accent(string id) =>
			Info != null && Info.Colors.TryGetValue(id, out var c) ? c : id == "random" ? RandomColor : id == "none" ? NoneColor : Gold;

		public override void Draw()
		{
			var rb = Parent.RenderBounds;
			var image = Parent.GetOrNull<ImageWidget>(PortraitWidget);
			var id = image?.GetImageName();
			if (string.IsNullOrEmpty(id))
				id = "none";

			var accent = Accent(id);
			var subtitle = Info == null ? "" : Line(Info.Subtitles, id, id == "none" ? "NO TITAN" : id == "random" ? "SURPRISE" : "TITAN");

			if (Mode == DecorMode.Button)
			{
				// Like the nation box: accent bar, portrait, the engine's name label, the subtitle in the accent colour
				WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Y + 2, 3, rb.Height - 4), accent);
				var portrait = ChromeProvider.TryGetImage("px-titans", "portrait-" + id);
				var py = rb.Y + (rb.Height - PortraitSize.Y) / 2;
				if (portrait != null)
				{
					WidgetUtils.FillRectWithColor(new Rectangle(rb.X + 9, py + 2, PortraitSize.X, PortraitSize.Y), Color.FromArgb(140, 0, 0, 0));
					WidgetUtils.DrawSprite(portrait, new float2(rb.X + 8, py), PortraitSize);
				}

				var font = Game.Renderer.Fonts[SubtitleFont];
				var x = rb.X + PortraitSize.X + 16;
				var text = WidgetUtils.TruncateText(subtitle.ToUpperInvariant(), rb.Right - x - 26, font);
				font.DrawText(text, new float2(x, rb.Bottom - font.Measure(text).Y - 6), Lighter(accent));
				return;
			}

			// Card. A titan: its banner art fills the card, the text sits on the art's dark lower left
			var selected = Parent is ScrollItemWidget item && item.IsSelected();
			var name = Parent.GetOrNull<LabelWidget>("LABEL")?.GetText() ?? "";
			var hover = Ui.MouseOverWidget == Parent || (Ui.MouseOverWidget != null && Ui.MouseOverWidget.Parent == Parent);
			if (IsTitan(id))
			{
				var banner = ChromeProvider.TryGetImage("px-titans", "banner-" + id);
				if (banner != null)
					WidgetUtils.DrawSprite(banner, new float2(rb.X, rb.Y), new float2(rb.Width, rb.Height));

				Game.Renderer.Fonts[NameFont].DrawTextWithShadow(name.ToUpperInvariant(), new float2(rb.X + 14, rb.Y + 12), Color.White, Color.Black, 2);
				var sub = Game.Renderer.Fonts[SubtitleFont];
				sub.DrawTextWithShadow(subtitle.ToUpperInvariant(), new float2(rb.X + 15, rb.Y + 44), Lighter(accent), Color.Black, 1);
				var special = Line(Info?.Specials ?? new Dictionary<string, string>(), id, "");
				if (!string.IsNullOrEmpty(special))
				{
					var sf = Game.Renderer.Fonts[SpecialFont];
					var y = rb.Bottom - 44;
					// Two lines, written with a literal \\n in the yaml
					foreach (var l in special.Replace("\\n", "\n").Split('\n').Take(2))
					{
						sf.DrawTextWithShadow(WidgetUtils.TruncateText(l.Trim(), rb.Width * 2 / 3, sf), new float2(rb.X + 14, y), Color.FromArgb(214, 215, 222), Color.Black, 1);
						y += 18;
					}
				}
			}
			else
			{
				var portrait = ChromeProvider.TryGetImage("px-titans", "portrait-" + id);
				var py = rb.Y + (rb.Height - PortraitSize.Y) / 2;
				if (portrait != null)
					WidgetUtils.DrawSprite(portrait, new float2(rb.X + 8, py), PortraitSize);

				var x = rb.X + PortraitSize.X + 20;
				Game.Renderer.Fonts[SlimNameFont].DrawText(name, new float2(x, rb.Y + 8), Color.White);
				var line = (Info == null ? "" : Line(Info.Specials, id, subtitle)).Replace("\\n", " ");
				var sf = Game.Renderer.Fonts[SpecialFont];
				sf.DrawText(WidgetUtils.TruncateText(line, rb.Right - x - 36, sf), new float2(x, rb.Y + 31), Lighter(accent));
			}

			// Frame: the accent colour when chosen, a soft light edge on hover
			var edge = selected ? accent : hover ? Color.FromArgb(200, 255, 255, 255) : Color.FromArgb(70, 255, 255, 255);
			var t = selected ? 2 : 1;
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Y, rb.Width, t), edge);
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Bottom - t, rb.Width, t), edge);
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Y, t, rb.Height), edge);
			WidgetUtils.FillRectWithColor(new Rectangle(rb.Right - t, rb.Y, t, rb.Height), edge);
			if (selected)
			{
				var c = new float2(rb.Right - 20, rb.Y + 20);
				WidgetUtils.FillEllipseWithColor(new Rectangle((int)c.X - 11, (int)c.Y - 11, 22, 22), accent);
				var tick = ChromeProvider.TryGetImage("px-lobby-icons", "tick");
				if (tick != null)
					WidgetUtils.DrawSprite(tick, c - 0.5f * tick.Size.XY);
			}
		}

		static Color Lighter(Color c) => Color.FromArgb(Math.Min(255, c.R + 60), Math.Min(255, c.G + 60), Math.Min(255, c.B + 60));
	}

	/// <summary>
	/// "Choose your titan": the lobby's titan dropdown as a panel of cards. Titans get big banner cards, two per row;
	/// None and Random share a slim row underneath. The cards are the TEMPLATE item LobbyUtils clones per option; the
	/// titan id comes from each card's PORTRAIT image.
	/// </summary>
	public class PxTitanPickerPanelWidget : ScrollPanelWidget
	{
		public readonly string Title = "CHOOSE YOUR TITAN";
		public readonly string TitleFont = "PXDisplay";
		public readonly string HintFont = "PXSmall";
		public readonly string Hint = "One per player. It walks out at the start and cannot be rebuilt.";
		public readonly int Padding = 16;
		public readonly int TitleHeight = 64;
		public readonly int Gap = 10;
		public readonly int BannerHeight = 120;
		public readonly int SlimHeight = 56;

		[ObjectCreator.UseCtor]
		public PxTitanPickerPanelWidget(ModData modData)
			: base(modData) { }

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			Layout = new CardLayout(this);
		}

		public override void Tick()
		{
			base.Tick();

			// Show every card (ShowDropDown caps the height for a list) and stay on screen
			if (Bounds.Height != ContentHeight)
			{
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
			var rb = RenderBounds;
			Game.Renderer.Fonts[TitleFont].DrawTextWithShadow(Title, new float2(rb.X + Padding + 4, rb.Y + 12), Color.White, Color.Black, 1);
			Game.Renderer.Fonts[HintFont].DrawText(Hint, new float2(rb.X + Padding + 4, rb.Y + 38), Color.FromArgb(150, 151, 160));
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X + Padding, rb.Y + TitleHeight - 6, rb.Width - 2 * Padding, 1),
				Color.FromArgb(60, 255, 255, 255));
		}

		sealed class CardLayout : ILayout
		{
			readonly PxTitanPickerPanelWidget panel;

			public CardLayout(PxTitanPickerPanelWidget panel)
			{
				this.panel = panel;
			}

			// ScrollPanelWidget.AddChild asks for the new child's place before adding it to Children
			public void AdjustChild(Widget w) { Relayout(w); }

			public void AdjustChildren() { Relayout(null); }

			void Relayout(Widget added)
			{
				var p = panel;
				var children = p.Children.Where(c => c is ScrollItemWidget).ToList();
				if (added is ScrollItemWidget && !children.Contains(added))
					children.Add(added);
				var width = p.Bounds.Width - 2 * p.Padding;
				var half = (width - p.Gap) / 2;
				var big = children.Where(c => PxTitanDecorWidget.IsTitan(c.GetOrNull<ImageWidget>("PORTRAIT")?.GetImageName())).ToList();
				var slim = children.Except(big).ToList();

				var y = p.TitleHeight;
				for (var i = 0; i < big.Count; i++)
				{
					var w = big[i];
					var last = i == big.Count - 1 && big.Count % 2 == 1;
					Place(w, p.Padding + (i % 2) * (half + p.Gap), y, last ? width : half, p.BannerHeight);
					if (i % 2 == 1 || last)
						y += p.BannerHeight + p.Gap;
				}

				var slimWidth = slim.Count > 0 ? (width - (slim.Count - 1) * p.Gap) / slim.Count : 0;
				for (var i = 0; i < slim.Count; i++)
					Place(slim[i], p.Padding + i * (slimWidth + p.Gap), y, slimWidth, p.SlimHeight);

				if (slim.Count > 0)
					y += p.SlimHeight + p.Gap;

				p.ContentHeight = y + p.Padding - p.Gap;
			}

			static void Place(Widget w, int x, int y, int width, int height)
			{
				w.Bounds.X = x;
				w.Bounds.Y = y;
				w.Bounds.Width = width;
				w.Bounds.Height = height;
			}
		}
	}
}
