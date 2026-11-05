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
using System.Globalization;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Network;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Production palette drawn as large cameo tiles: HD art (the `px-` prefixed icon sequence when the
	/// image defines one), a name plate, cost tag, clock-wipe progress, READY glow and a padlock for
	/// items that cannot be built. Input, hotkeys and tooltips are inherited unchanged.
	/// </summary>
	public class PxProductionPaletteWidget : ProductionPaletteWidget
	{
		[Desc("Prefix added to the Buildable icon sequence to find the large cameo.")]
		public readonly string LargeIconPrefix = "px-";

		public readonly string NameFont = "PXSidebarSmall";
		public readonly string ProgressFont = "PXDigitsTile";
		public readonly string SmallFont = "PXDigitsSmall";
		public readonly string BitsCollection = "px-sidebar-bits";
		public readonly string LockImage = "padlock";

		public readonly Color AccentColor = Color.FromArgb(226, 38, 38);
		public readonly Color ReadyColor = Color.FromArgb(255, 209, 102);
		public readonly Color TileColor = Color.FromArgb(21, 22, 26);
		public readonly Color EmptyTileColor = Color.FromArgb(14, 15, 18);
		public readonly Color BorderColor = Color.FromArgb(44, 45, 52);

		[Desc("Draw empty placeholder tiles to fill the visible rows.")]
		public readonly bool DrawEmptySlots = true;

		readonly WorldRenderer worldRenderer;
		readonly OrderManager orderManager;
		readonly Dictionary<(string Actor, string Faction), (Sprite Sprite, PaletteReference Palette, bool Large)> sprites = new();
		readonly Dictionary<string, string> names = new();
		SpriteFont nameFont, progressFont, smallFont;
		Sprite lockSprite;

		[ObjectCreator.UseCtor]
		public PxProductionPaletteWidget(ModData modData, OrderManager orderManager, World world, WorldRenderer worldRenderer)
			: base(modData, orderManager, world, worldRenderer)
		{
			this.worldRenderer = worldRenderer;
			this.orderManager = orderManager;
		}

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			nameFont = Game.Renderer.Fonts[NameFont];
			progressFont = Game.Renderer.Fonts[ProgressFont];
			smallFont = Game.Renderer.Fonts[SmallFont];
			lockSprite = ChromeProvider.GetImage(BitsCollection, LockImage);
		}

		(Sprite Sprite, PaletteReference Palette, bool Large) GetSprite(ActorInfo item, string faction, Player owner)
		{
			if (sprites.TryGetValue((item.Name, faction), out var cached))
				return cached;

			var image = item.TraitInfo<RenderSpritesInfo>().GetImage(item, faction);
			var bi = item.TraitInfo<BuildableInfo>();
			var large = World.Map.Sequences.HasSequence(image, LargeIconPrefix + bi.Icon);
			var icon = new Animation(World, image);
			icon.Play(large ? LargeIconPrefix + bi.Icon : bi.Icon);

			var palette = bi.IconPaletteIsPlayerPalette ? bi.IconPalette + owner.InternalName : bi.IconPalette;
			return sprites[(item.Name, faction)] = (icon.Image, worldRenderer.Palette(palette), large);
		}

		string GetName(ActorInfo item)
		{
			if (names.TryGetValue(item.Name, out var cached))
				return cached;

			var tooltip = item.TraitInfos<TooltipInfo>().FirstOrDefault(info => info.EnabledByDefault);
			var name = (tooltip != null ? FluentProvider.GetMessage(tooltip.Name) : item.Name).ToUpperInvariant();
			return names[item.Name] = WidgetUtils.TruncateText(name, IconSize.X - 8, nameFont);
		}

		public override void Draw()
		{
			var queue = CurrentQueue;
			var producer = queue?.MostLikelyProducer() ?? default;
			var rb = RenderBounds;
			var visible = new List<(Rectangle Rect, ActorInfo Item)>();

			if (queue != null && producer.Trait != null)
			{
				var index = 0;
				foreach (var item in AllBuildables.Skip(IconRowOffset * Columns).Take(MaxIconRowOffset * Columns))
					visible.Add((TileRect(rb, index++), item));
			}

			if (DrawEmptySlots && MaxIconRowOffset < int.MaxValue)
				for (var i = visible.Count; i < MaxIconRowOffset * Columns; i++)
					DrawEmptyTile(TileRect(rb, i));

			if (visible.Count == 0)
				return;

			var buildable = queue.BuildableItems().Select(a => a.Name).ToHashSet();
			var queued = queue.AllQueued().ToList();
			var hovered = TooltipIcon?.Actor;
			var pios = queue.Actor.Owner.PlayerActor.TraitsImplementing<IProductionIconOverlay>().ToArray();
			var faction = producer.Trait.Faction;

			foreach (var (rect, item) in visible)
			{
				var items = queued.Where(q => q.Item == item.Name).ToList();
				DrawTile(rect, item, faction, producer.Actor.Owner, items, buildable.Contains(item.Name), item == hovered, pios);
			}
		}

		Rectangle TileRect(Rectangle rb, int index)
		{
			var x = index % Columns;
			var y = index / Columns;
			return new Rectangle(rb.X + x * (IconSize.X + IconMargin.X), rb.Y + y * (IconSize.Y + IconMargin.Y), IconSize.X, IconSize.Y);
		}

		void DrawEmptyTile(Rectangle r)
		{
			WidgetUtils.FillRectWithColor(r, EmptyTileColor);
			DrawBorder(r, Color.FromArgb(28, 29, 34), 1);
		}

		void DrawTile(Rectangle r, ActorInfo item, string faction, Player owner, List<ProductionItem> items,
			bool canBuild, bool hovered, IProductionIconOverlay[] pios)
		{
			var first = items.FirstOrDefault();
			var locked = first == null && !canBuild;

			// Cameo art, scaled to cover the tile
			WidgetUtils.FillRectWithColor(r, TileColor);
			var (sprite, palette, large) = GetSprite(item, faction, owner);
			var scale = Math.Max(r.Width / sprite.Size.X, r.Height / sprite.Size.Y);
			var center = new float2(r.X + r.Width / 2f, r.Y + r.Height / 2f);
			var topLeft = center - 0.5f * scale * sprite.Size.XY;
			var tint = locked ? new float3(0.38f, 0.38f, 0.4f) : new float3(1, 1, 1);

			if (!large)
				Game.Renderer.EnableScissor(r);

			Game.Renderer.EnableAntialiasingFilter();
			Game.Renderer.SpriteRenderer.DrawSprite(sprite, palette, topLeft, scale, tint, 1f);
			Game.Renderer.DisableAntialiasingFilter();

			foreach (var pio in pios.Where(p => p.IsOverlayActive(item)))
				WidgetUtils.DrawSpriteCentered(pio.Sprite, worldRenderer.Palette(pio.Palette), center + pio.Offset(IconSize));

			if (!large)
				Game.Renderer.DisableScissor();

			// Name plate
			var plate = new Rectangle(r.X, r.Bottom - 26, r.Width, 26);
			WidgetUtils.FillRectWithColor(plate, Color.FromArgb(0, 0, 0, 0), Color.FromArgb(0, 0, 0, 0),
				Color.FromArgb(235, 0, 0, 0), Color.FromArgb(235, 0, 0, 0));
			var name = GetName(item);
			var nameSize = nameFont.Measure(name);
			nameFont.DrawTextWithShadow(name, new float2(r.X + (r.Width - nameSize.X) / 2, r.Bottom - nameSize.Y - 4),
				Color.White, Color.Black, 1);

			if (first == null)
			{
				if (locked)
					WidgetUtils.DrawSprite(lockSprite, center - new float2(0, 8) - 0.5f * lockSprite.Size.XY);
				else
					DrawChip(new float2(r.X + 4, r.Y + 4), "$" + CurrentQueue.GetProductionCost(item).ToString(CultureInfo.InvariantCulture),
						Color.FromArgb(185, 0, 0, 0), ReadyColor, false);
			}
			else
				DrawProgress(r, center, first, items.Count);

			// Border
			if (first != null && first.Done)
			{
				for (var i = 0; i < 5; i++)
					DrawBorder(r.InflateBy(-2 - i * 2, -2 - i * 2, -2 - i * 2, -2 - i * 2), Color.FromArgb(70 - i * 14, ReadyColor), 2);

				DrawBorder(r, ReadyColor, 2);
			}
			else if (hovered)
			{
				DrawBorder(r.InflateBy(1, 1, 1, 1), Color.FromArgb(110, AccentColor), 1);
				DrawBorder(r, AccentColor, 2);
			}
			else
				DrawBorder(r, BorderColor, 1);
		}

		void DrawProgress(Rectangle r, float2 center, ProductionItem first, int total)
		{
			if (first.Done)
			{
				var blink = orderManager.LocalFrameNumber * World.Timestep / 360 % 2 == 0;
				DrawChip(new float2(r.Right - 5, r.Y + 5), ReadyText.ToUpperInvariant(),
					blink ? ReadyColor : Color.FromArgb(255, 236, 170), Color.FromArgb(20, 20, 20), true);
			}
			else
			{
				var progress = first.TotalTime > 0 ? (float)(first.TotalTime - first.RemainingTime) / first.TotalTime : 0;
				var waiting = !CurrentQueue.IsProducing(first);
				FillClockWipe(r, progress, Color.FromArgb(waiting || first.Paused ? 190 : 165, 0, 0, 0));

				if (first.Paused || waiting)
				{
					var text = first.Paused ? HoldText.ToUpperInvariant() : "QUEUED";
					var size = nameFont.Measure(text);
					nameFont.DrawTextWithShadow(text, center - new float2(size.X / 2, size.Y / 2 + 8), Color.White, Color.Black, 1);
				}
				else
				{
					var pct = ((int)(progress * 100)).ToString(CultureInfo.InvariantCulture) + "%";
					var size = progressFont.Measure(pct);
					progressFont.DrawTextWithShadow(pct, center - new float2(size.X / 2, size.Y / 2 + 12), Color.White, Color.Black, 2);

					var time = WidgetUtils.FormatTime(CurrentQueue.RemainingTimeActual(first), World.Timestep);
					var timeSize = smallFont.Measure(time);
					smallFont.DrawTextWithShadow(time, center - new float2(timeSize.X / 2, timeSize.Y / 2 - 8), Color.FromArgb(220, 220, 225), Color.Black, 1);
				}

				// Progress bar along the bottom edge
				var bar = new Rectangle(r.X, r.Bottom - 3, (int)(r.Width * progress), 3);
				WidgetUtils.FillRectWithColor(bar.InflateBy(0, 2, 0, 0), Color.FromArgb(90, AccentColor));
				WidgetUtils.FillRectWithColor(bar, AccentColor);
			}

			if (first.Infinite)
				DrawChip(new float2(r.Right - 5, r.Y + 5), "∞", ReadyColor, Color.FromArgb(20, 20, 20), true);
			else if (total > 1 && !first.Done)
				DrawChip(new float2(r.Right - 5, r.Y + 5), "×" + total.ToString(CultureInfo.InvariantCulture), ReadyColor, Color.FromArgb(20, 20, 20), true);
		}

		void DrawChip(float2 anchor, string text, Color background, Color color, bool alignRight)
		{
			var size = smallFont.Measure(text);
			var w = size.X + 10;
			var x = alignRight ? anchor.X - w : anchor.X;
			WidgetUtils.FillRectWithColor(new Rectangle((int)x, (int)anchor.Y, w, size.Y + 4), background);
			smallFont.DrawText(text, new float2(x + 5, anchor.Y + 2), color);
		}

		static void DrawBorder(Rectangle r, Color color, int width)
		{
			var cr = Game.Renderer.RgbaColorRenderer;
			var w = width / 2f;
			cr.DrawRect(new float3(r.Left + w, r.Top + w, 0), new float3(r.Right - w, r.Bottom - w, 0), width, color);
		}

		/// <summary>Darkens the part of the tile the clock hand has not swept yet (starting at 12 o'clock, clockwise).</summary>
		static void FillClockWipe(Rectangle r, float progress, Color color)
		{
			if (progress >= 1)
				return;

			var c = new float3(r.X + r.Width / 2f, r.Y + r.Height / 2f, 0);
			var radius = (float)Math.Sqrt(r.Width * r.Width + r.Height * r.Height);
			var start = progress * 2 * Math.PI;
			const int Steps = 48;
			var cr = Game.Renderer.RgbaColorRenderer;
			var segments = Math.Max(1, (int)Math.Ceiling(Steps * (1 - progress)));

			Game.Renderer.EnableScissor(r);
			for (var i = 0; i < segments; i++)
			{
				var a0 = start + (2 * Math.PI - start) * i / segments;
				var a1 = start + (2 * Math.PI - start) * (i + 1) / segments;
				var p0 = c + new float3((float)Math.Sin(a0) * radius, -(float)Math.Cos(a0) * radius, 0);
				var p1 = c + new float3((float)Math.Sin(a1) * radius, -(float)Math.Cos(a1) * radius, 0);
				cr.FillRect(c, p0, p1, p1, color);
			}

			Game.Renderer.DisableScissor();
		}
	}
}
