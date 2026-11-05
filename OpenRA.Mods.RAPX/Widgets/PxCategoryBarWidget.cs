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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Row of category chips (IDEA-05) above the production palette: "All" plus every PxBuildCategory of the
	/// current queue that has items. Clicking a chip filters the palette. Chips show how many items can be
	/// built now, a progress bar while one of their items is in production, and pulse when a new item unlocks
	/// in a category that isn't selected. The choice is remembered per queue.
	/// </summary>
	public class PxCategoryBarWidget : Widget
	{
		public readonly string Palette = "PRODUCTION_PALETTE";
		public readonly string IconCollection = "px-category-icons";
		public readonly string Font = "PXSidebarSmall";
		public readonly string BadgeFont = "PXDigitsSmall";
		public readonly int Gap = 4;
		public readonly int MaxChipWidth = 44;

		[Desc("How long a chip pulses after a new item unlocks in it, in milliseconds.")]
		public readonly int PulseTime = 1800;

		public readonly Color ChipColor = Color.FromArgb(21, 22, 26);
		public readonly Color HoverColor = Color.FromArgb(36, 37, 44);
		public readonly Color BorderColor = Color.FromArgb(44, 45, 52);
		public readonly Color AccentColor = Color.FromArgb(226, 38, 38);
		public readonly Color ReadyColor = Color.FromArgb(255, 209, 102);
		public readonly Color TextColor = Color.FromArgb(185, 186, 194);

		[FluentReference]
		const string AllName = "label-px-category-all";

		[FluentReference]
		const string OtherName = "label-px-category-other";

		const string AllId = "";
		const string OtherId = "~other";

		sealed class Chip
		{
			public string Id;
			public string Name;
			public string Icon;
			public Rectangle Rect;
			public int Available;
			public float Progress = -1;
			public bool Done;
		}

		readonly World world;
		readonly ModData modData;
		readonly Dictionary<string, List<PxBuildCategoryInfo>> categories = new();
		readonly Dictionary<string, string> selected = new();
		readonly Dictionary<(string Queue, string Id), int> lastAvailable = new();
		readonly Dictionary<(string Queue, string Id), long> pulseUntil = new();
		List<Chip> chips = new();
		ProductionPaletteWidget palette;
		(string Queue, string Id) appliedFilter = (null, null);
		string queueType;
		int hovered = -1;
		SpriteFont font, badgeFont;

		/// <summary>Name of the chip under the mouse, or null.</summary>
		public string HoveredName => hovered >= 0 && hovered < chips.Count ? chips[hovered].Name : null;

		/// <summary>Name of the selected category in the current queue, or null when "All" is selected.</summary>
		public string SelectedName => chips.FirstOrDefault(c => c.Id != AllId && c.Id == SelectedId)?.Name;

		string SelectedId => SelectedIdFor(queueType);

		string SelectedIdFor(string queue)
		{
			if (queue == null || !selected.TryGetValue(queue, out var id))
				return AllId;

			// A category with no items in this queue any more falls back to "All" (Tick resets it too)
			return id == AllId || id == OtherId || (categories.GetValueOrDefault(queue)?.Any(c => c.Name == id) ?? false) ? id : AllId;
		}

		[ObjectCreator.UseCtor]
		public PxCategoryBarWidget(World world, ModData modData)
		{
			this.world = world;
			this.modData = modData;
		}

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			font = Game.Renderer.Fonts[Font];
			badgeFont = Game.Renderer.Fonts[BadgeFont];

			var player = world.LocalPlayer;
			if (player == null)
				return;

			foreach (var c in player.PlayerActor.Info.TraitInfos<PxBuildCategoryInfo>().OrderBy(c => c.Order))
			{
				if (!categories.TryGetValue(c.Queue, out var list))
					categories[c.Queue] = list = new List<PxBuildCategoryInfo>();

				list.Add(c);
			}
		}

		bool InCategory(string queue, string id, ActorInfo actor)
		{
			if (id == AllId)
				return true;

			var list = categories.GetValueOrDefault(queue);
			if (id == OtherId)
				return list == null || !list.Any(c => c.Actors.Contains(actor.Name));

			var category = list?.FirstOrDefault(c => c.Name == id);
			return category != null && category.Actors.Contains(actor.Name);
		}

		// National units of other nations stay hidden even when AllTech ignores their prerequisites,
		// and so do faction variants (e.g. AFLD vs AFLD.Ukraine, which otherwise both show as "Airfield")
		bool Shown(ActorInfo actor) => PxNationalUnitInfo.ShownTo(actor, world.LocalPlayer) && FactionVariantShown(actor);

		bool FactionVariantShown(ActorInfo actor)
		{
			var techTree = world.LocalPlayer?.PlayerActor.TraitOrDefault<OpenRA.Mods.Common.Traits.TechTree>();
			var buildable = actor.TraitInfoOrDefault<OpenRA.Mods.Common.Traits.BuildableInfo>();
			if (techTree == null || buildable == null)
				return true;

			// Hidden ("~") side/nation prerequisites such as ~structures.ukraine, ~!structures.ukraine or ~vehicles.soviet;
			// tech levels and producer buildings (~techlevel.medium, ~afld) are left to AllTech
			var faction = buildable.Prerequisites.Where(p =>
			{
				if (!p.StartsWith('~'))
					return false;

				var name = p.TrimStart('~', '!');
				return name.Contains('.') && !name.StartsWith("techlevel.", StringComparison.Ordinal);
			}).ToList();

			return faction.Count == 0 || techTree.HasPrerequisites(faction);
		}

		public override void Tick()
		{
			palette ??= Ui.Root.GetOrNull<ProductionPaletteWidget>(Palette);
			var queue = palette?.CurrentQueue;
			if (queue == null)
			{
				chips.Clear();
				queueType = null;
				return;
			}

			queueType = queue.Info.Type;
			var all = queue.AllItems().Where(Shown).ToList();
			var buildable = queue.BuildableItems().Select(a => a.Name).ToHashSet();
			var queued = queue.AllQueued().ToList();
			var list = categories.GetValueOrDefault(queueType) ?? new List<PxBuildCategoryInfo>();

			// No categories for this queue: no chips, no filter
			if (list.Count == 0)
			{
				chips.Clear();
				ApplyFilter(queueType, AllId);
				return;
			}

			var next = new List<Chip> { new() { Id = AllId, Name = FluentProvider.GetMessage(AllName) } };
			foreach (var c in list)
				if (all.Any(a => c.Actors.Contains(a.Name)))
					next.Add(new Chip { Id = c.Name, Name = FluentProvider.GetMessage(c.Name), Icon = c.Icon });

			if (all.Any(a => !list.Any(c => c.Actors.Contains(a.Name))))
				next.Add(new Chip { Id = OtherId, Name = FluentProvider.GetMessage(OtherName), Icon = "other" });

			var now = Game.RunTime;
			foreach (var chip in next)
			{
				var items = all.Where(a => InCategory(queueType, chip.Id, a)).Select(a => a.Name).ToHashSet();
				chip.Available = items.Count(buildable.Contains);

				var first = queued.FirstOrDefault(q => items.Contains(q.Item));
				if (first != null)
				{
					chip.Done = first.Done;
					chip.Progress = first.TotalTime > 0 ? (float)(first.TotalTime - first.RemainingTime) / first.TotalTime : 0;
				}

				// Pulse a chip that isn't selected when something new becomes buildable in it
				var key = (queueType, chip.Id);
				if (chip.Id != AllId && lastAvailable.TryGetValue(key, out var before) && chip.Available > before && chip.Id != SelectedId)
					pulseUntil[key] = now + PulseTime;

				lastAvailable[key] = chip.Available;
			}

			chips = next;
			if (!chips.Any(c => c.Id == SelectedId))
				selected[queueType] = AllId;

			// Layout: chips share the row, up to MaxChipWidth each
			var w = Math.Min(MaxChipWidth, (Bounds.Width - Gap * (chips.Count - 1)) / chips.Count);
			var rb = RenderBounds;
			for (var i = 0; i < chips.Count; i++)
				chips[i].Rect = new Rectangle(rb.X + i * (w + Gap), rb.Y, w, rb.Height);

			ApplyFilter(queueType, SelectedId);
		}

		void ApplyFilter(string queue, string id)
		{
			if (appliedFilter == (queue, id))
				return;

			appliedFilter = (queue, id);

			// Resolve the queue when the palette asks, not when the filter is set: switching tabs refreshes the
			// palette before our next Tick, and a filter still bound to the old queue's category would show no
			// items, which makes ClassicProductionLogic jump back to the first tab
			palette.BuildableFilter = a => Shown(a) && InCategory(palette.CurrentQueue?.Info.Type, SelectedIdFor(palette.CurrentQueue?.Info.Type), a);
			palette.ScrollToTop();
			palette.RefreshIcons();
		}

		/// <summary>Selects the chip at this position (0 = All); used by the developer menu script.</summary>
		public void SelectIndex(int index)
		{
			if (queueType != null && index >= 0 && index < chips.Count)
				selected[queueType] = chips[index].Id;
		}

		public override bool HandleMouseInput(MouseInput mi)
		{
			var index = chips.FindIndex(c => c.Rect.Contains(mi.Location));
			hovered = index;
			if (index < 0 || mi.Event != MouseInputEvent.Down || mi.Button != MouseButton.Left || queueType == null)
				return index >= 0;

			selected[queueType] = chips[index].Id;
			pulseUntil.Remove((queueType, chips[index].Id));
			Game.Sound.PlayNotification(modData.DefaultRules, null, "Sounds", "ClickSound", null);
			return true;
		}

		public override void MouseExited()
		{
			hovered = -1;
		}

		public override void Draw()
		{
			if (chips.Count < 2)
				return;

			var now = Game.RunTime;
			var selectedId = SelectedId;
			for (var i = 0; i < chips.Count; i++)
			{
				var chip = chips[i];
				var r = chip.Rect;
				var isSelected = chip.Id == selectedId;
				var isHovered = i == hovered;

				WidgetUtils.FillRectWithColor(r, isSelected ? AccentColor : isHovered ? HoverColor : ChipColor);

				// Icon (or text for "All")
				var center = new float2(r.X + r.Width / 2f, r.Y + r.Height / 2f - 1);
				var sprite = chip.Icon != null
					? ChromeProvider.GetImage(IconCollection, isSelected || isHovered ? chip.Icon : chip.Icon + "-off")
					: null;

				if (sprite != null)
					WidgetUtils.DrawSprite(sprite, center - 0.5f * sprite.Size.XY);
				else
				{
					var text = chip.Name.ToUpperInvariant();
					var size = font.Measure(text);
					font.DrawTextWithShadow(text, center - new float2(size.X / 2f, size.Y / 2f),
						isSelected || isHovered ? Color.White : TextColor, Color.Black, 1);
				}

				// Count of items that can be built now
				if (chip.Available > 0 && chip.Id != AllId)
				{
					var count = chip.Available.ToString(CultureInfo.InvariantCulture);
					var size = badgeFont.Measure(count);
					var badge = new Rectangle(r.Right - size.X - 5, r.Y + 1, size.X + 4, size.Y + 1);
					WidgetUtils.FillRectWithColor(badge, Color.FromArgb(200, 0, 0, 0));
					badgeFont.DrawText(count, new float2(badge.X + 2, badge.Y), isSelected ? Color.White : ReadyColor);
				}

				// Production progress along the bottom edge
				if (chip.Progress >= 0)
				{
					var blink = chip.Done && now / 360 % 2 == 0;
					var bar = new Rectangle(r.X, r.Bottom - 3, chip.Done ? r.Width : (int)(r.Width * chip.Progress), 3);
					WidgetUtils.FillRectWithColor(bar, chip.Done ? (blink ? ReadyColor : Color.White) : isSelected ? Color.White : AccentColor);
				}

				// Border, glowing while the chip pulses
				var cr = Game.Renderer.RgbaColorRenderer;
				if (pulseUntil.TryGetValue((queueType, chip.Id), out var until) && now < until)
				{
					var a = (int)(140 + 115 * Math.Sin(now / 90.0));
					cr.DrawRect(new float3(r.Left + 1, r.Top + 1, 0), new float3(r.Right - 1, r.Bottom - 1, 0), 2, Color.FromArgb(a, ReadyColor));
				}
				else
					cr.DrawRect(new float3(r.Left + 0.5f, r.Top + 0.5f, 0), new float3(r.Right - 0.5f, r.Bottom - 0.5f, 0), 1,
						isSelected ? Color.FromArgb(255, 120, 110) : BorderColor);
			}
		}
	}
}
