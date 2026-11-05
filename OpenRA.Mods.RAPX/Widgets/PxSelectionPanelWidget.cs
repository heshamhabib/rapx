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
using OpenRA.Primitives;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>The current selection, grouped by actor type. Shared by every part of the selection panel.</summary>
	public static class PxSelection
	{
		public sealed class Group
		{
			public ActorInfo Info;
			public List<Actor> Actors;
		}

		static readonly List<Group> Empty = new();
		static int cachedTick = -1;
		static int cachedHash;
		static World cachedWorld;
		static List<Group> cachedGroups = Empty;

		/// <summary>Actor type the player last picked from the selected-units strip.</summary>
		public static string PreferredType;

		public static List<Group> Groups(World world)
		{
			var hash = world.Selection.Hash;
			if (world == cachedWorld && world.WorldTick == cachedTick && hash == cachedHash)
				return cachedGroups;

			cachedWorld = world;
			cachedTick = world.WorldTick;
			cachedHash = hash;
			cachedGroups = world.Selection.Actors
				.Where(a => a.IsInWorld && !a.IsDead)
				.GroupBy(a => a.Info)
				.Select(g => new Group { Info = g.Key, Actors = g.OrderBy(a => a.ActorID).ToList() })
				.OrderByDescending(g => g.Actors.Count)
				.ThenBy(g => g.Info.Name, StringComparer.Ordinal)
				.ToList();

			return cachedGroups;
		}

		public static int Count(World world) => Groups(world).Sum(g => g.Actors.Count);

		public static Actor Primary(World world)
		{
			var groups = Groups(world);
			if (groups.Count == 0)
				return null;

			var preferred = groups.FirstOrDefault(g => g.Info.Name == PreferredType) ?? groups[0];
			return preferred.Actors[0];
		}
	}

	/// <summary>
	/// One part of the bottom selection panel: the portrait, the name/description block, the health and
	/// stats block, or the selected-units strip (which selects a single actor type when clicked).
	/// </summary>
	public class PxSelectionPanelWidget : Widget
	{
		public enum PanelPart { Portrait, Info, Stats, Groups }

		public readonly PanelPart Part = PanelPart.Portrait;

		public readonly string LargeIconPrefix = "px-";
		public readonly string TitleFont = "PXSidebarTitle";
		public readonly string LabelFont = "PXSidebarSmall";
		public readonly string ValueFont = "PXSidebarLabel";
		public readonly string BodyFont = "PXSmall";
		public readonly string DigitsFont = "PXDigitsMedium";
		public readonly string BadgeFont = "PXDigitsSmall";

		public readonly Color AccentColor = Color.FromArgb(226, 38, 38);
		public readonly Color LabelColor = Color.FromArgb(157, 158, 166);
		public readonly Color BodyColor = Color.FromArgb(207, 208, 214);

		[Desc("Size of one thumbnail in the selected-units strip.")]
		public readonly int2 SlotSize = new(72, 54);
		public readonly int SlotSpacing = 6;

		static readonly Dictionary<string, string> Categories = new()
		{
			{ "Building", "Structure" },
			{ "Defense", "Defensive Structure" },
			{ "Infantry", "Infantry" },
			{ "Vehicle", "Vehicle" },
			{ "Aircraft", "Aircraft" },
			{ "Ship", "Naval Unit" },
		};

		readonly World world;
		readonly WorldRenderer worldRenderer;
		readonly Dictionary<(string Image, bool Large), (Sprite Sprite, PaletteReference Palette)> sprites = new();
		readonly Dictionary<ActorInfo, string[]> descriptions = new();
		SpriteFont titleFont, labelFont, valueFont, bodyFont, digitsFont, badgeFont;
		int hoveredSlot = -1;

		[ObjectCreator.UseCtor]
		public PxSelectionPanelWidget(World world, WorldRenderer worldRenderer)
		{
			this.world = world;
			this.worldRenderer = worldRenderer;
		}

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			titleFont = Game.Renderer.Fonts[TitleFont];
			labelFont = Game.Renderer.Fonts[LabelFont];
			valueFont = Game.Renderer.Fonts[ValueFont];
			bodyFont = Game.Renderer.Fonts[BodyFont];
			digitsFont = Game.Renderer.Fonts[DigitsFont];
			badgeFont = Game.Renderer.Fonts[BadgeFont];
		}

		public override void Draw()
		{
			var rb = RenderBounds;
			var primary = PxSelection.Primary(world);
			switch (Part)
			{
				case PanelPart.Portrait: DrawPortrait(rb, primary); break;
				case PanelPart.Info: DrawInfo(rb, primary); break;
				case PanelPart.Stats: DrawStats(rb, primary); break;
				case PanelPart.Groups: DrawGroups(rb); break;
			}
		}

		(Sprite Sprite, PaletteReference Palette)? GetPortrait(Actor actor, bool preferLarge)
		{
			var bi = actor.Info.TraitInfoOrDefault<BuildableInfo>();
			var rs = actor.TraitOrDefault<RenderSprites>();
			if (bi == null || rs == null)
				return null;

			var image = rs.GetImage(actor);
			if (sprites.TryGetValue((image, preferLarge), out var cached))
				return cached.Sprite != null ? cached : null;

			(Sprite, PaletteReference) result = (null, null);
			try
			{
				var sequences = world.Map.Sequences;
				var sequence = preferLarge && sequences.HasSequence(image, LargeIconPrefix + bi.Icon) ? LargeIconPrefix + bi.Icon :
					sequences.HasSequence(image, bi.Icon) ? bi.Icon : null;

				if (sequence != null)
				{
					var anim = new Animation(world, image);
					anim.Play(sequence);
					var palette = bi.IconPaletteIsPlayerPalette ? bi.IconPalette + actor.Owner.InternalName : bi.IconPalette;
					result = (anim.Image, worldRenderer.Palette(palette));
				}
			}
			catch (InvalidOperationException)
			{
				// Image without sequences: fall back to the faction emblem
			}

			sprites[(image, preferLarge)] = result;
			return result.Item1 != null ? result : null;
		}

		void DrawCover(Rectangle r, Actor actor, float alpha = 1f)
		{
			var portrait = GetPortrait(actor, true);
			if (portrait == null)
			{
				var emblem = ChromeProvider.GetImage("px-emblems", EmblemName(actor.Owner));
				var size = Math.Min(r.Width, r.Height) * 0.5f;
				WidgetUtils.DrawSprite(emblem, new float2(r.X + (r.Width - size) / 2, r.Y + (r.Height - size) / 2), new float2(size, size));
				return;
			}

			var (sprite, palette) = portrait.Value;
			var scale = Math.Max(r.Width / sprite.Size.X, r.Height / sprite.Size.Y);
			var topLeft = new float2(r.X + r.Width / 2f, r.Y + r.Height / 2f) - 0.5f * scale * sprite.Size.XY;
			Game.Renderer.EnableScissor(r);
			Game.Renderer.EnableAntialiasingFilter();
			Game.Renderer.SpriteRenderer.DrawSprite(sprite, palette, topLeft, scale, new float3(alpha, alpha, alpha), 1f);
			Game.Renderer.DisableAntialiasingFilter();
			Game.Renderer.DisableScissor();
		}

		void DrawPortrait(Rectangle rb, Actor primary)
		{
			var r = rb.InflateBy(-4, -4, -4, -6);
			WidgetUtils.FillRectWithColor(r, Color.FromArgb(14, 15, 18));
			if (primary == null)
			{
				var emblem = ChromeProvider.GetImage("px-emblems", EmblemName(world.LocalPlayer));
				WidgetUtils.DrawSprite(emblem, new float2(r.X + (r.Width - 44) / 2, r.Y + (r.Height - 44) / 2), new float2(44, 44));
				return;
			}

			DrawCover(r, primary);

			if (primary.Owner != world.LocalPlayer)
			{
				var tag = OwnerTag(primary.Owner);
				var size = labelFont.Measure(tag);
				WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, size.X + 12, size.Y + 6), Color.FromArgb(200, 0, 0, 0));
				WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, 3, size.Y + 6), primary.Owner.Color);
				labelFont.DrawText(tag, new float2(r.X + 8, r.Y + 3), Color.White);
			}

			DrawBorder(r, Color.FromArgb(44, 45, 52), 1);
		}

		void DrawInfo(Rectangle rb, Actor primary)
		{
			var x = rb.X + 12;
			var y = rb.Y + 10;
			if (primary == null)
			{
				titleFont.DrawText("NO SELECTION", new float2(x, y + 2), Color.FromArgb(110, 111, 120));
				bodyFont.DrawText("Select a unit or structure", new float2(x, y + 32), LabelColor);
				bodyFont.DrawText("to see its details.", new float2(x, y + 50), LabelColor);
				return;
			}

			var emblem = ChromeProvider.GetImage("px-emblems", EmblemName(primary.Owner));
			WidgetUtils.DrawSprite(emblem, new float2(x, y), new float2(36, 36));

			var textX = x + 46;
			var width = rb.Right - textX - 10;
			var name = WidgetUtils.TruncateText(ActorName(primary.Info).ToUpperInvariant(), width, titleFont);
			titleFont.DrawText(name, new float2(textX, y), Color.White);

			var count = PxSelection.Groups(world).FirstOrDefault(g => g.Info == primary.Info)?.Actors.Count ?? 1;
			var subtitle = Category(primary.Info) + (count > 1 ? $"  ·  ×{count}" : "");
			labelFont.DrawText(subtitle.ToUpperInvariant(), new float2(textX, y + 23), primary.Owner == world.LocalPlayer ? AccentColor : primary.Owner.Color);

			WidgetUtils.FillRectWithColor(new Rectangle(x, y + 44, rb.Right - x - 10, 1), Color.FromArgb(44, 45, 52));

			var lines = Description(primary.Info, rb.Right - x - 12);
			for (var i = 0; i < lines.Length; i++)
				bodyFont.DrawText(lines[i], new float2(x, y + 52 + i * 18), BodyColor);
		}

		string[] Description(ActorInfo info, int width)
		{
			if (descriptions.TryGetValue(info, out var cached))
				return cached;

			var bi = info.TraitInfoOrDefault<BuildableInfo>();
			var text = bi?.Description != null ? FluentProvider.GetMessage(bi.Description) : "";
			text = string.Join(" ", text.Split('\n', StringSplitOptions.RemoveEmptyEntries).Select(l => l.Trim()));
			var lines = WidgetUtils.WrapText(text, width, bodyFont).Split('\n');
			if (lines.Length > 3)
			{
				lines = lines.Take(3).ToArray();
				lines[2] = WidgetUtils.TruncateText(lines[2] + " …", width, bodyFont);
			}

			return descriptions[info] = lines;
		}

		void DrawStats(Rectangle rb, Actor primary)
		{
			var x = rb.X + 12;
			var y = rb.Y + 8;
			var right = rb.Right - 12;
			labelFont.DrawText("HEALTH", new float2(x, y), LabelColor);

			var health = primary?.TraitOrDefault<IHealth>();
			var fraction = health != null && health.MaxHP > 0 ? (float)health.HP / health.MaxHP : 0f;
			var hpText = health != null ? $"{(health.HP + 99) / 100} / {(health.MaxHP + 99) / 100}" : "—";
			var hpSize = digitsFont.Measure(hpText);
			var hpColor = fraction > 0.5f ? Color.FromArgb(126, 224, 138) : fraction > 0.25f ? Color.FromArgb(255, 176, 32) : Color.FromArgb(255, 92, 70);
			digitsFont.DrawText(hpText, new float2(right - hpSize.X, y + 14), health != null ? hpColor : LabelColor);

			DrawSegments(new Rectangle(x, y + 19, right - x - hpSize.X - 14, 10), fraction, hpColor);

			// 2x2 stat grid
			var top = y + 42;
			var cellW = (right - x) / 2;
			WidgetUtils.FillRectWithColor(new Rectangle(x, top - 4, right - x, 1), Color.FromArgb(44, 45, 52));
			WidgetUtils.FillRectWithColor(new Rectangle(x + cellW - 4, top, 1, 70), Color.FromArgb(44, 45, 52));

			var stats = Stats(primary);
			for (var i = 0; i < stats.Length; i++)
			{
				var cx = x + i % 2 * cellW;
				var cy = top + 4 + i / 2 * 36;
				var (icon, label, value, color) = stats[i];
				WidgetUtils.DrawSprite(ChromeProvider.GetImage("px-stat-icons", icon), new float2(cx, cy + 6));
				labelFont.DrawText(label, new float2(cx + 26, cy), LabelColor);
				valueFont.DrawText(WidgetUtils.TruncateText(value, cellW - 34, valueFont), new float2(cx + 26, cy + 14), color);
			}
		}

		(string Icon, string Label, string Value, Color Color)[] Stats(Actor actor)
		{
			const string None = "—";
			if (actor == null)
			{
				return new[]
				{
					("armor", "ARMOR", None, LabelColor),
					("build-time", "BUILD TIME", None, LabelColor),
					("speed", "SPEED", None, LabelColor),
					("cost", "COST", None, LabelColor)
				};
			}

			var info = actor.Info;
			var armor = info.TraitInfos<ArmorInfo>().FirstOrDefault()?.Type;
			var bi = info.TraitInfoOrDefault<BuildableInfo>();
			var buildTime = None;
			if (bi != null)
			{
				var queue = actor.Owner.PlayerActor.TraitsImplementing<ProductionQueue>()
					.FirstOrDefault(q => bi.Queue.Contains(q.Info.Type));
				if (queue != null)
					buildTime = WidgetUtils.FormatTime(queue.GetBuildTime(info, bi), world.Timestep);
			}

			var cost = info.TraitInfoOrDefault<ValuedInfo>()?.Cost;
			var result = new (string, string, string, Color)[4];
			result[0] = ("armor", "ARMOR", armor != null ? Capitalize(armor) : None, Color.White);
			result[1] = ("build-time", "BUILD TIME", buildTime, Color.White);

			var powers = info.TraitInfos<PowerInfo>().ToList();
			if (powers.Count > 0)
			{
				var amount = powers.Sum(p => p.Amount);
				result[2] = ("power", amount >= 0 ? "POWER OUTPUT" : "POWER USAGE",
					(amount > 0 ? "+" : "") + amount.ToString(CultureInfo.InvariantCulture),
					amount >= 0 ? Color.FromArgb(126, 224, 138) : Color.FromArgb(255, 140, 120));
			}
			else
			{
				var speed = info.TraitInfoOrDefault<MobileInfo>()?.Speed ?? info.TraitInfoOrDefault<AircraftInfo>()?.Speed;
				result[2] = ("speed", "SPEED", speed?.ToString(CultureInfo.InvariantCulture) ?? None, Color.White);
			}

			result[3] = ("cost", "COST", cost != null ? "$" + cost.Value.ToString(CultureInfo.InvariantCulture) : None, Color.FromArgb(255, 209, 102));
			return result;
		}

		int VisibleSlots(Rectangle rb) => Math.Max(1, (rb.Width - 24 + SlotSpacing) / (SlotSize.X + SlotSpacing));

		Rectangle SlotRect(Rectangle rb, int i) =>
			new(rb.X + 12 + i * (SlotSize.X + SlotSpacing), rb.Y + 32, SlotSize.X, SlotSize.Y);

		void DrawGroups(Rectangle rb)
		{
			var groups = PxSelection.Groups(world);
			var total = groups.Sum(g => g.Actors.Count);
			labelFont.DrawText($"SELECTED UNITS ({total})", new float2(rb.X + 12, rb.Y + 8), LabelColor);

			var primary = PxSelection.Primary(world);
			var slots = VisibleSlots(rb);
			var overflow = groups.Count > slots ? groups.Count - slots + 1 : 0;
			for (var i = 0; i < slots; i++)
			{
				var r = SlotRect(rb, i);
				if (i >= groups.Count)
				{
					WidgetUtils.FillRectWithColor(r, Color.FromArgb(14, 15, 18));
					DrawBorder(r, Color.FromArgb(32, 33, 38), 1);
					continue;
				}

				if (overflow > 0 && i == slots - 1)
				{
					WidgetUtils.FillRectWithColor(r, Color.FromArgb(24, 25, 30));
					var more = "+" + overflow.ToString(CultureInfo.InvariantCulture);
					var size = valueFont.Measure(more);
					valueFont.DrawText(more, new float2(r.X + (r.Width - size.X) / 2, r.Y + (r.Height - size.Y) / 2), BodyColor);
					DrawBorder(r, Color.FromArgb(44, 45, 52), 1);
					continue;
				}

				var group = groups[i];
				DrawCover(r, group.Actors[0]);

				// Average health of the group along the bottom edge
				var healths = group.Actors.Select(a => a.TraitOrDefault<IHealth>()).Where(h => h != null && h.MaxHP > 0).ToList();
				if (healths.Count > 0)
				{
					var f = healths.Average(h => (float)h.HP / h.MaxHP);
					var c = f > 0.5f ? Color.FromArgb(79, 197, 102) : f > 0.25f ? Color.FromArgb(255, 176, 32) : Color.FromArgb(255, 70, 60);
					WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Bottom - 4, r.Width, 4), Color.FromArgb(200, 0, 0, 0));
					WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Bottom - 4, (int)(r.Width * f), 4), c);
				}

				var isPrimary = primary != null && group.Info == primary.Info;
				DrawBorder(r, isPrimary ? AccentColor : i == hoveredSlot ? Color.FromArgb(170, AccentColor) : Color.FromArgb(44, 45, 52), isPrimary ? 2 : 1);

				var count = group.Actors.Count.ToString(CultureInfo.InvariantCulture);
				var countSize = badgeFont.Measure(count);
				var badge = new Rectangle(r.X + (r.Width - countSize.X - 10) / 2, r.Bottom + 3, countSize.X + 10, countSize.Y + 3);
				WidgetUtils.FillRectWithColor(badge, isPrimary ? AccentColor : Color.FromArgb(52, 53, 60));
				badgeFont.DrawText(count, new float2(badge.X + 5, badge.Y + 1), Color.White);
			}
		}

		public override bool HandleMouseInput(MouseInput mi)
		{
			if (Part != PanelPart.Groups)
				return false;

			var rb = RenderBounds;
			var groups = PxSelection.Groups(world);
			var slots = VisibleSlots(rb);
			var hit = -1;
			for (var i = 0; i < Math.Min(slots, groups.Count); i++)
				if (SlotRect(rb, i).Contains(mi.Location) && !(groups.Count > slots && i == slots - 1))
					hit = i;

			hoveredSlot = hit;
			if (hit < 0 || mi.Event != MouseInputEvent.Down || mi.Button != MouseButton.Left)
				return hit >= 0;

			// Narrow the selection to the clicked type
			var group = groups[hit];
			PxSelection.PreferredType = group.Info.Name;
			world.Selection.Combine(world, group.Actors, false, false);

			Game.Sound.PlayNotification(world.Map.Rules, null, "Sounds", ChromeMetrics.Get<string>("ClickSound"), null);
			return true;
		}

		public override void MouseExited() { hoveredSlot = -1; }

		static void DrawSegments(Rectangle r, float fraction, Color color)
		{
			const int Segments = 16;
			const int Gap = 2;
			var w = (r.Width - (Segments - 1) * Gap) / (float)Segments;
			var lit = (int)Math.Ceiling(fraction * Segments);
			for (var i = 0; i < Segments; i++)
			{
				var x = (int)(r.X + i * (w + Gap));
				var seg = new Rectangle(x, r.Y, (int)(r.X + (i + 1) * (w + Gap) - Gap) - x, r.Height);
				WidgetUtils.FillRectWithColor(seg, i < lit ? color : Color.FromArgb(36, 40, 40));
			}
		}

		static void DrawBorder(Rectangle r, Color color, int width)
		{
			var w = width / 2f;
			Game.Renderer.RgbaColorRenderer.DrawRect(new float3(r.Left + w, r.Top + w, 0), new float3(r.Right - w, r.Bottom - w, 0), width, color);
		}

		static string EmblemName(Player player) => player?.Faction.Side == "Vanguard" ? "soviet" : "allies";

		string OwnerTag(Player owner)
		{
			var relationship = world.LocalPlayer?.RelationshipWith(owner) ?? PlayerRelationship.Neutral;
			var kind = relationship == PlayerRelationship.Ally ? "ALLY" : relationship == PlayerRelationship.Enemy ? "ENEMY" : "NEUTRAL";
			return kind + " · " + owner.ResolvedPlayerName.ToUpperInvariant();
		}

		static string ActorName(ActorInfo info)
		{
			var tooltip = info.TraitInfos<TooltipInfo>().FirstOrDefault(t => t.EnabledByDefault);
			return tooltip != null ? FluentProvider.GetMessage(tooltip.Name) : info.Name;
		}

		static string Category(ActorInfo info)
		{
			var queue = info.TraitInfoOrDefault<BuildableInfo>()?.Queue.FirstOrDefault();
			if (queue != null && Categories.TryGetValue(queue, out var category))
				return category;

			return info.HasTraitInfo<BuildingInfo>() ? "Structure" : "Unit";
		}

		static string Capitalize(string s) => s.Length == 0 ? s : char.ToUpperInvariant(s[0]) + s[1..];
	}
}
