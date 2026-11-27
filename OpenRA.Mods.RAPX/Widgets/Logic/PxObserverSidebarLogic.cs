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
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// The RAPX observer sidebar (shown to spectators, in replays and after the local player is defeated or wins):
	/// header with the player's fate, weather, radar, mission time, players still fighting, camera view and player cards.
	/// Keeps the camera inside the map like the player HUD (engine patch patches/engine-viewport-clamp.patch, which
	/// also turns off the stock spectator zoom-out that would show past the map edge).
	/// </summary>
	public class PxObserverSidebarLogic : ChromeLogic
	{
		readonly Func<(int Left, int Top, int Right, int Bottom)> insets;

		[ObjectCreator.UseCtor]
		public PxObserverSidebarLogic(Widget widget, World world, WorldRenderer worldRenderer)
		{
			var player = world.LocalPlayer;

			var emblem = widget.GetOrNull<ImageWidget>("FACTION_EMBLEM");
			if (emblem != null)
				emblem.GetImageName = () => player?.Faction.Side == "Vanguard" ? "soviet" : "allies";

			var subtitle = widget.GetOrNull<LabelWidget>("OBSERVER_SUBTITLE");
			if (subtitle != null)
			{
				var font = Game.Renderer.Fonts[subtitle.Font];
				var name = player?.ResolvedPlayerName.ToUpperInvariant();
				var text = world.IsReplay ? PxText.T("REPLAY") :
					player == null ? PxText.T("SPECTATING") :
					player.WinState == WinState.Won ? PxText.F("VICTORY · {0}", name) :
					player.WinState == WinState.Lost ? PxText.F("DEFEATED · {0}", name) : PxText.F("SPECTATING · {0}", name);
				text = WidgetUtils.TruncateText(text, subtitle.Bounds.Width, font);
				subtitle.GetText = () => text;
				subtitle.GetColor = () => player?.WinState == WinState.Won ? Color.FromArgb(255, 209, 102) : subtitle.TextColor;
			}

			var alive = widget.GetOrNull<LabelWidget>("PLAYERS_ALIVE");
			if (alive != null)
			{
				var fighters = world.Players.Where(p => p.Playable && !p.NonCombatant).ToArray();
				var cached = new CachedTransform<int, string>(n => $"{n}/{fighters.Length}");
				alive.GetText = () => cached.Update(fighters.Count(p => p.WinState != WinState.Lost));
			}

			// No weather this match: close the gap the badge would take
			var weatherWell = widget.GetOrNull("WEATHER_WELL");
			var badge = weatherWell?.GetOrNull<PxWeatherBadgeWidget>("WEATHER_BADGE");
			if (weatherWell != null && (badge == null || !badge.HasWeather))
			{
				weatherWell.Visible = false;
				var shift = weatherWell.Bounds.Height + 8;
				foreach (var w in widget.Children)
				{
					if (w != weatherWell && w.Id != "REPLAY_PLAYER" && w.Bounds.Y > weatherWell.Bounds.Y)
					{
						w.Bounds.Y -= shift;
						if (w.Id == "PLAYER_CARDS")
							w.Bounds.Height += shift;
					}
				}
			}

			// Replays need room for the speed controls under the cards
			var replay = widget.GetOrNull("REPLAY_PLAYER");
			var cards = widget.GetOrNull("PLAYER_CARDS");
			if (replay != null && cards != null && world.IsReplay)
				cards.Bounds.Height -= replay.Bounds.Height + 8;

			insets = () => (0, 0, widget.IsVisible() ? widget.Bounds.Width : 0, 0);
			Viewport.ViewInsets = insets;

			// The sidebar is opaque: full-screen passes skip the world under it
			WorldRenderer.VisibleViewArea = PxHudOcclusion.VisibleViewArea;

			// The camera may sit past the edge from before the clamp applied (start position, other HUD): pull it in
			worldRenderer.Viewport.Center(worldRenderer.Viewport.CenterPosition);
		}

		protected override void Dispose(bool disposing)
		{
			if (Viewport.ViewInsets == insets)
			{
				Viewport.ViewInsets = null;
				WorldRenderer.VisibleViewArea = null;
			}

			base.Dispose(disposing);
		}
	}
}
