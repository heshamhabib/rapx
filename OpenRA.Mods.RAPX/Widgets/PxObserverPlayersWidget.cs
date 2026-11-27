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
using System.Globalization;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Observer sidebar: one card per player in the match with flag, name, nation, status (in battle / defeated / victory)
	/// and live numbers (credits, army value, kills and losses, power). Defeated players are dimmed.
	/// </summary>
	public class PxObserverPlayersWidget : Widget
	{
		public readonly string NameFont = "PXSidebarLabel";
		public readonly string SmallFont = "PXSidebarSmall";
		public readonly string DigitsFont = "PXDigitsSmall";

		public readonly int CardHeight = 66;
		public readonly int CardSpacing = 6;

		public readonly Color LabelColor = Color.FromArgb(157, 158, 166);
		public readonly Color ValueColor = Color.FromArgb(222, 223, 228);
		public readonly Color ActiveColor = Color.FromArgb(93, 255, 122);
		public readonly Color DefeatColor = Color.FromArgb(255, 92, 70);
		public readonly Color VictoryColor = Color.FromArgb(255, 209, 102);

		readonly World world;
		SpriteFont nameFont, smallFont, digitsFont;
		Player[] players = Array.Empty<Player>();

		[ObjectCreator.UseCtor]
		public PxObserverPlayersWidget(World world)
		{
			this.world = world;
			IgnoreMouseOver = true;
		}

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			nameFont = Game.Renderer.Fonts[NameFont];
			smallFont = Game.Renderer.Fonts[SmallFont];
			digitsFont = Game.Renderer.Fonts[DigitsFont];

			players = world.Players
				.Where(p => p.Playable && !p.NonCombatant)
				.OrderBy(p => p.ClientIndex)
				.ToArray();
		}

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		public override void Draw()
		{
			var rb = RenderBounds;
			Game.Renderer.EnableScissor(rb);
			var y = rb.Y;
			foreach (var p in players)
			{
				if (y >= rb.Bottom)
					break;

				DrawCard(p, new Rectangle(rb.X, y, rb.Width, CardHeight));
				y += CardHeight + CardSpacing;
			}

			Game.Renderer.DisableScissor();
		}

		void DrawCard(Player p, Rectangle r)
		{
			var defeated = p.WinState == WinState.Lost;
			var won = p.WinState == WinState.Won;
			var dim = defeated ? 0.45f : 1f;

			WidgetUtils.FillRectWithColor(r, Color.FromArgb(240, 12, 13, 16));
			PxWarChrome.DrawBorder(r, Color.FromArgb(44, 45, 52), 1);
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, 4, r.Height), Fade(p.Color, dim));

			// Flag, name and nation
			var flag = ChromeProvider.TryGetImage("flags", p.Faction.InternalName);
			var flagRect = new Rectangle(r.X + 14, r.Y + 10, 32, 20);
			if (flag != null)
				WidgetUtils.DrawSprite(flag, new float2(flagRect.X, flagRect.Y), new float2(flagRect.Width, flagRect.Height));

			if (defeated)
				WidgetUtils.FillRectWithColor(flagRect, Color.FromArgb(150, 12, 13, 16));

			var nameX = r.X + 56;
			var status = won ? PxText.T("VICTORY") : defeated ? PxText.T("DEFEATED") : PxText.T("IN BATTLE");
			var statusColor = won ? VictoryColor : defeated ? DefeatColor : ActiveColor;
			var statusWidth = PxWarChrome.SpacedWidth(smallFont, status, 1);
			var nameWidth = r.Right - 12 - statusWidth - 16 - nameX;
			var name = WidgetUtils.TruncateText(p.ResolvedPlayerName, nameWidth, nameFont);
			nameFont.DrawTextWithShadow(name, new float2(nameX, r.Y + 7), Fade(Color.White, dim), Color.FromArgb(160, 0, 0, 0), 1);
			var nation = FluentProvider.GetMessage(p.Faction.Name).ToUpperInvariant();
			PxWarChrome.DrawSpaced(smallFont, nation, nameX, r.Y + 26, 1, Fade(LabelColor, dim));

			// Status tag with a dot
			var tagX = r.Right - 12 - statusWidth;
			WidgetUtils.FillRectWithColor(new Rectangle(tagX - 11, r.Y + 13, 6, 6), Fade(statusColor, defeated || won ? 1f : 0.5f + 0.5f * PxWarChrome.Pulse(1600)));
			PxWarChrome.DrawSpaced(smallFont, status, tagX, r.Y + 9, 1, statusColor);

			// Numbers row
			var stats = p.PlayerActor.TraitOrDefault<PlayerStatistics>();
			var resources = p.PlayerActor.TraitOrDefault<PlayerResources>();
			var power = p.PlayerActor.TraitOrDefault<PowerManager>();
			var cells = new (string Label, string Value, Color Color)[]
			{
				(PxText.T("CREDITS"), resources != null ? Money(resources.Cash + resources.Resources) : "-", Color.FromArgb(255, 209, 102)),
				(PxText.T("ARMY"), stats != null ? Money(stats.ArmyValue) : "-", ValueColor),
				(PxText.T("K / L"), stats != null ? $"{stats.UnitsKilled + stats.BuildingsKilled}/{stats.UnitsDead + stats.BuildingsDead}" : "-", ValueColor),
				(PxText.T("POWER"), power != null ? power.ExcessPower.ToString(CultureInfo.InvariantCulture) : "-",
					power != null && power.ExcessPower < 0 ? DefeatColor : ActiveColor),
			};

			var row = new Rectangle(r.X + 14, r.Y + 42, r.Width - 26, 18);
			var cellWidth = row.Width / cells.Length;
			for (var i = 0; i < cells.Length; i++)
			{
				var x = row.X + i * cellWidth;
				smallFont.DrawText(cells[i].Label, new float2(x, row.Y + 3), Fade(LabelColor, dim * 0.85f));
				var labelWidth = smallFont.Measure(cells[i].Label).X;
				var value = WidgetUtils.TruncateText(cells[i].Value, cellWidth - labelWidth - 10, digitsFont);
				digitsFont.DrawText(value, new float2(x + labelWidth + 5, row.Y + 1), Fade(cells[i].Color, dim));
			}
		}

		static string Money(long v)
		{
			var a = Math.Abs(v);
			var s = a >= 1_000_000_000_000 ? (a / 1e12).ToString("0.#", CultureInfo.InvariantCulture) + "T" :
				a >= 1_000_000_000 ? (a / 1e9).ToString("0.#", CultureInfo.InvariantCulture) + "B" :
				a >= 1_000_000 ? (a / 1e6).ToString("0.#", CultureInfo.InvariantCulture) + "M" :
				a >= 10_000 ? (a / 1e3).ToString("0.#", CultureInfo.InvariantCulture) + "K" :
				a.ToString(CultureInfo.InvariantCulture);
			return (v < 0 ? "-$" : "$") + s;
		}

		static Color Fade(Color c, float k) => Color.FromArgb((int)(c.A * k), c.R, c.G, c.B);
	}
}
