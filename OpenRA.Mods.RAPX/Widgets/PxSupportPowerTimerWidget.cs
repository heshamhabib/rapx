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
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Superweapon intel board replacing the stock SupportPowerTimer text lines: one armoured dispatch plate per
	/// power with owner tab, power icon, YOURS/ALLY/HOSTILE tag, LCD countdown and charge bar. Hostile weapons get a
	/// hazard edge and turn red and pulse in their last minute; armed weapons flash READY.
	/// </summary>
	public class PxSupportPowerTimerWidget : Widget
	{
		public readonly string NameFont = "PXHeader";
		public readonly string SmallFont = "PXSidebarSmall";
		public readonly string DigitFont = "PXDigitsMedium";
		public readonly Color SteelColor = Color.FromArgb(96, 100, 86);

		public readonly int RowHeight = 42;
		public readonly int RowSpacing = 6;
		public readonly int Cut = 9;

		[Desc("Seconds left at which a hostile power starts the red alert pulse.")]
		public readonly int ImminentSeconds = 60;

		public readonly SupportPowerTimerWidget.TimerOrder Order = SupportPowerTimerWidget.TimerOrder.Descending;

		[FluentReference]
		const string TagOwn = "label-support-timer-own";

		[FluentReference]
		const string TagAlly = "label-support-timer-ally";

		[FluentReference]
		const string TagHostile = "label-support-timer-hostile";

		[FluentReference]
		const string Ready = "label-support-timer-ready";

		[FluentReference]
		const string Hold = "label-support-timer-hold";

		readonly World world;
		readonly WorldRenderer worldRenderer;
		readonly IEnumerable<SupportPowerInstance> powers;
		readonly Dictionary<string, Sprite> icons = new();

		[ObjectCreator.UseCtor]
		public PxSupportPowerTimerWidget(World world, WorldRenderer worldRenderer)
		{
			this.world = world;
			this.worldRenderer = worldRenderer;
			IgnoreMouseOver = true;
			powers = world.ActorsWithTrait<SupportPowerManager>()
				.Where(p => !p.Actor.IsDead && !p.Actor.Owner.NonCombatant)
				.SelectMany(s => s.Trait.Powers.Values)
				.Where(p => p.Instances.Count > 0 && p.Info.DisplayTimerRelationships != PlayerRelationship.None && !p.Disabled);
		}

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		public override void Draw()
		{
			if (!IsVisible())
				return;

			var viewer = world.RenderPlayer ?? world.LocalPlayer;
			var rb = RenderBounds;
			var y = 0;
			foreach (var p in powers)
			{
				var owner = p.Instances[0].Self.Owner;
				if (viewer != null && !p.Info.DisplayTimerRelationships.HasRelationship(owner.RelationshipWith(viewer)))
					continue;

				var top = Order == SupportPowerTimerWidget.TimerOrder.Descending ? rb.Y + y : rb.Bottom - RowHeight - y;
				DrawRow(new Rectangle(rb.X, top, rb.Width, RowHeight), p, owner, viewer);
				y += RowHeight + RowSpacing;
			}
		}

		void DrawRow(Rectangle r, SupportPowerInstance p, Player owner, Player viewer)
		{
			var nameFont = Game.Renderer.Fonts[NameFont];
			var smallFont = Game.Renderer.Fonts[SmallFont];
			var digitFont = Game.Renderer.Fonts[DigitFont];

			var own = viewer != null && owner == viewer;
			var hostile = viewer != null && !own && owner.RelationshipWith(viewer) != PlayerRelationship.Ally;
			var seconds = p.RemainingTicks * world.Timestep / 1000;
			var imminent = hostile && !p.Ready && seconds <= ImminentSeconds;
			var blink = Game.LocalTick % 50 < 25;
			var pulse = PxWarChrome.Pulse(imminent ? 500 : 900);

			var accent = hostile ? (p.Ready || imminent ? PxWarChrome.Hostile : PxWarChrome.Amber) : PxWarChrome.Friendly;
			var rim = hostile ? PxWarChrome.Darken(PxWarChrome.Hostile, p.Ready || imminent ? 0.1f + 0.3f * pulse : 0.45f)
				: own ? SteelColor : PxWarChrome.Darken(PxWarChrome.Friendly, 0.4f);
			var glow = p.Ready ? (blink ? 1f : 0.4f) : imminent ? pulse : 0f;

			PxWarChrome.DrawSteelPlate(r, Cut, rim, glow, accent);
			if (hostile)
				PxWarChrome.DrawHazard(new Rectangle(r.X + Cut + 2, r.Y + 2, r.Width / 3, 3), 0, 200,
					p.Ready || imminent ? PxWarChrome.Hostile : PxWarChrome.Hazard);

			// Owner tab
			var ownerColor = owner.Color;
			var tab = new Rectangle(r.X + 3, r.Y + Cut, 5, r.Height - Cut - 3);
			WidgetUtils.FillRectWithColor(tab, ownerColor, ownerColor, PxWarChrome.Darken(ownerColor, 0.5f), PxWarChrome.Darken(ownerColor, 0.5f));

			// Power icon
			var well = new Rectangle(r.X + 12, r.Y + 5, 42, r.Height - 10);
			PxWarChrome.DrawWell(well);
			var sprite = Icon(p);
			Game.Renderer.EnableScissor(well);
			var scale = Math.Min((well.Width - 2) / sprite.Size.X, (well.Height - 2) / sprite.Size.Y);
			Game.Renderer.EnableAntialiasingFilter();
			WidgetUtils.DrawSpriteCentered(sprite, worldRenderer.Palette(p.Info.IconPalette), new float2(well.X + well.Width / 2f, well.Y + well.Height / 2f), scale);
			Game.Renderer.DisableAntialiasingFilter();
			if (!p.Ready)
			{
				var h = p.TotalTicks == 0 ? 0 : (int)(well.Height * p.RemainingTicks / (float)p.TotalTicks);
				WidgetUtils.FillRectWithColor(new Rectangle(well.X, well.Y, well.Width, h), Color.FromArgb(140, 6, 8, 6));
			}

			Game.Renderer.DisableScissor();

			// LCD countdown
			var lcd = new Rectangle(r.Right - 82, r.Y + 6, 74, 22);
			PxWarChrome.DrawWell(lcd);
			WidgetUtils.FillRectWithColor(lcd.InflateBy(-1, -1, -1, -1), Color.FromArgb(14, accent));

			// Low power holds are only shown for our own side; enemies just see the frozen clock
			var onHold = !p.Active && !hostile;
			if (p.Ready || onHold)
			{
				if (onHold)
					PxWarChrome.DrawHazard(lcd.InflateBy(-1, -1, -1, -1), 0, 110);

				var text = FluentProvider.GetMessage(onHold ? Hold : Ready);
				var w = PxWarChrome.SpacedWidth(smallFont, text, 2);
				var h = smallFont.Measure(text).Y;
				if (onHold)
					WidgetUtils.FillRectWithColor(new Rectangle(lcd.X + (lcd.Width - w) / 2 - 4, lcd.Y + 4, w + 8, lcd.Height - 8), Color.FromArgb(230, 12, 12, 10));

				var color = onHold ? (blink ? PxWarChrome.Hazard : PxWarChrome.Darken(PxWarChrome.Hazard, 0.4f))
					: blink ? accent : Color.FromArgb(230, 255, 255, 255);
				PxWarChrome.DrawSpaced(smallFont, text, lcd.X + (lcd.Width - w) / 2, lcd.Y + (lcd.Height - h) / 2, 2, color);
			}
			else
			{
				var time = WidgetUtils.FormatTime(p.RemainingTicks, false, world.Timestep);
				var size = digitFont.Measure(time);
				var lit = PxWarChrome.Lerp(accent, Color.White, 0.12f);
				digitFont.DrawTextWithContrast(time, new float2(lcd.X + (lcd.Width - size.X) / 2, lcd.Y + (lcd.Height - size.Y) / 2),
					lit, Color.FromArgb(imminent ? (int)(60 + 80 * pulse) : 60, accent), 1);
			}

			for (var y = lcd.Y + 1; y < lcd.Bottom; y += 3)
				WidgetUtils.FillRectWithColor(new Rectangle(lcd.X, y, lcd.Width, 1), Color.FromArgb(18, 0, 0, 0));

			// Power name and owner line
			var textX = well.Right + 7;
			var textW = lcd.X - textX - 6;
			var name = WidgetUtils.TruncateText(p.Name.ToUpperInvariant(), textW, nameFont);
			PxWarChrome.DrawSpaced(nameFont, name, textX, r.Y + 4, 1, PxWarChrome.Stencil);

			var line2 = r.Y + 20;
			if (viewer != null)
			{
				var tagText = FluentProvider.GetMessage(own ? TagOwn : hostile ? TagHostile : TagAlly);
				var size = smallFont.Measure(tagText);
				var chip = new Rectangle(textX, line2, size.X + 8, size.Y + 1);
				WidgetUtils.FillRectWithColor(chip, PxWarChrome.Darken(hostile ? PxWarChrome.Hostile : PxWarChrome.Friendly, 0.55f));
				smallFont.DrawText(tagText, new float2(chip.X + 4, chip.Y), hostile ? Color.FromArgb(255, 210, 200) : Color.FromArgb(220, 255, 210));
				textX = chip.Right + 5;
			}

			var playerName = WidgetUtils.TruncateText(owner.ResolvedPlayerName, Math.Max(0, lcd.X - textX - 4), smallFont);
			smallFont.DrawTextWithShadow(playerName, new float2(textX, line2), ownerColor, Color.FromArgb(200, 0, 0, 0), 1);

			// Charge bar along the bottom
			var fraction = p.TotalTicks == 0 ? 1 : 1 - p.RemainingTicks / (float)p.TotalTicks;
			PxWarChrome.DrawSegments(new Rectangle(well.Right + 7, r.Bottom - 8, r.Right - Cut - well.Right - 12, 3), fraction, accent, 4);
		}

		Sprite Icon(SupportPowerInstance p)
		{
			var key = p.Info.IconImage + "/" + p.Info.Icon;
			if (icons.TryGetValue(key, out var sprite))
				return sprite;

			var anim = new Animation(world, p.Info.IconImage);
			anim.Play(p.Info.Icon);
			sprite = anim.Image;

			return icons[key] = sprite;
		}
	}
}
