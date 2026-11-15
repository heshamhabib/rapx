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
using OpenRA.Mods.Common.Traits.Radar;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Drives the RAPX full-height sidebar: faction header, radar status, power readout, production
	/// queue title and how many tile rows fit on screen. Must be attached to the sidebar root so it runs
	/// after ClassicProductionLogic.
	/// </summary>
	public class PxSidebarLogic : ChromeLogic
	{
		static readonly Dictionary<string, string> QueueTitles = new()
		{
			{ "Building", "STRUCTURES" },
			{ "Defense", "DEFENSES" },
			{ "Infantry", "INFANTRY" },
			{ "Vehicle", "VEHICLES" },
			{ "Aircraft", "AIRCRAFT" },
			{ "Ship", "NAVAL" },
		};

		static readonly Color Online = Color.FromArgb(93, 255, 122);
		static readonly Color Offline = Color.FromArgb(255, 92, 70);

		bool radarEnabled;
		bool hasHome;

		[ObjectCreator.UseCtor]
		public PxSidebarLogic(Widget widget, World world, WorldRenderer worldRenderer)
		{
			var player = world.LocalPlayer;
			var faction = player.Faction;

			var emblem = widget.GetOrNull<ImageWidget>("FACTION_EMBLEM");
			if (emblem != null)
				emblem.GetImageName = () => faction.Side == "Vanguard" ? "soviet" : "allies";

			var factionName = widget.GetOrNull<LabelWidget>("FACTION_NAME");
			if (factionName != null)
			{
				var text = FluentProvider.GetMessage(faction.Name).ToUpperInvariant();
				factionName.GetText = () => text;
			}

			var playerName = widget.GetOrNull<LabelWidget>("PLAYER_NAME");
			if (playerName != null)
			{
				var font = Game.Renderer.Fonts[playerName.Font];
				var text = WidgetUtils.TruncateText("COMMANDER · " + player.ResolvedPlayerName.ToUpperInvariant(), playerName.Bounds.Width, font);
				playerName.GetText = () => text;
			}

			// Radar status
			var devMode = player.PlayerActor.Trait<DeveloperMode>();
			var ticker = widget.Get<LogicTickerWidget>("PX_SIDEBAR_TICKER");
			ticker.OnTick = () =>
			{
				radarEnabled = devMode.DisableShroud ||
					world.ActorsHavingTrait<ProvidesRadar>(r => !r.IsTraitDisabled).Any(a => a.Owner == player);
				hasHome = world.ActorsHavingTrait<Building>().Any(a => a.Owner == player && a.IsInWorld && !a.IsDead && a.Info.HasTraitInfo<SelectableInfo>());
			};

			var status = widget.GetOrNull<LabelWidget>("RADAR_STATUS");
			if (status != null)
			{
				status.GetText = () => radarEnabled ? "ONLINE" : "OFFLINE";
				status.GetColor = () => radarEnabled ? Online : Offline;
			}

			var dot = widget.GetOrNull<ColorBlockWidget>("RADAR_DOT");
			if (dot != null)
				dot.GetColor = () => radarEnabled ? Online : Offline;

			var overlay = widget.GetOrNull<PxRadarOverlayWidget>("RADAR_OVERLAY");
			if (overlay != null)
				overlay.IsActive = () => radarEnabled;

			var offline = widget.GetOrNull("RADAR_OFFLINE");
			if (offline != null)
				offline.IsVisible = () => !radarEnabled;

			// Power readout
			var powerManager = player.PlayerActor.Trait<PowerManager>();
			var powerText = widget.GetOrNull<LabelWidget>("POWER_TEXT");
			if (powerText != null)
			{
				var cached = new CachedTransform<(int, int), string>(p =>
					p.Item1.ToString(CultureInfo.CurrentCulture) + "/" + p.Item2.ToString(CultureInfo.CurrentCulture));
				powerText.GetText = () => cached.Update((powerManager.PowerDrained, powerManager.PowerProvided));
				powerText.GetColor = () => powerManager.ExcessPower < 0 ? Offline : Online;
			}

			var powerIcon = widget.GetOrNull<ImageWidget>("POWER_ICON");
			if (powerIcon != null)
				powerIcon.GetImageName = () => powerManager.ExcessPower < 0 ? "power-critical" : "power-normal";

			// Home button: centre the camera on a construction yard (primary first, then oldest); clicking again
			// while the camera is still there moves on to the next yard. Without yards it falls back to any building.
			var home = widget.GetOrNull<ButtonWidget>("HOME_BUTTON");
			if (home != null)
			{
				var viewport = worldRenderer.Viewport;
				var homeIndex = -1;
				int2? homeLocation = null;

				List<Actor> HomeTargets()
				{
					var yards = world.ActorsHavingTrait<BaseBuilding>()
						.Where(a => a.Owner == player && a.IsInWorld && !a.IsDead)
						.OrderByDescending(a => a.TraitOrDefault<PrimaryBuilding>()?.IsPrimary ?? false)
						.ThenBy(a => a.ActorID)
						.ToList();

					if (yards.Count > 0)
						return yards;

					return world.ActorsHavingTrait<Building>()
						.Where(a => a.Owner == player && a.IsInWorld && !a.IsDead && a.Info.HasTraitInfo<SelectableInfo>())
						.OrderBy(a => a.ActorID)
						.Take(1)
						.ToList();
				}

				home.IsDisabled = () => !hasHome;
				home.OnClick = () =>
				{
					var targets = HomeTargets();
					if (targets.Count == 0)
						return;

					homeIndex = homeLocation == viewport.CenterLocation ? (homeIndex + 1) % targets.Count : 0;
					viewport.Center(targets[homeIndex].CenterPosition);
					homeLocation = viewport.CenterLocation;
				};

				var homeIcon = home.GetOrNull<ImageWidget>("ICON");
				if (homeIcon != null)
					homeIcon.GetImageName = () => home.IsDisabled() ? "home-disabled" : Ui.MouseOverWidget == home ? "home-active" : "home";
			}

			// Weather badge (IDEA-20): sits under the header and only takes space when the match has weather;
			// the action buttons and everything below them move down under it
			var weatherWell = widget.GetOrNull("WEATHER_WELL");
			var badge = weatherWell?.GetOrNull<PxWeatherBadgeWidget>("WEATHER_BADGE");
			if (weatherWell != null)
			{
				if (badge == null || !badge.HasWeather)
					weatherWell.Visible = false;
				else
				{
					var top = weatherWell.Bounds.Y;
					var shift = weatherWell.Bounds.Height + 8;
					foreach (var w in widget.Children)
					{
						if (w == weatherWell)
							continue;

						// Container with the options button (stays) and the action buttons (move)
						if (w.Id == "TOP_BUTTONS")
						{
							foreach (var b in w.Children)
								if (w.Bounds.Y + b.Bounds.Y >= top)
									b.Bounds.Y += shift;

							w.Bounds.Height += shift;
						}
						else if (w.Bounds.Y >= top)
						{
							w.Bounds.Y += shift;
							if (w.Id == "SIDEBAR_PRODUCTION")
								w.Bounds.Height -= shift;
						}
					}
				}
			}

			// Production queue header and visible rows
			var palette = widget.Get<ProductionPaletteWidget>("PRODUCTION_PALETTE");
			var categoryBar = widget.GetOrNull<PxCategoryBarWidget>("CATEGORY_BAR");
			var title = widget.GetOrNull<LabelWidget>("QUEUE_TITLE");
			if (title != null)
				title.GetText = () =>
				{
					var q = palette.CurrentQueue;
					if (q == null)
						return "";

					var category = categoryBar?.HoveredName ?? categoryBar?.SelectedName;
					if (category != null)
						return category.ToUpperInvariant();

					var group = q.Info.Group ?? q.Info.Type;
					return QueueTitles.TryGetValue(group, out var t) ? t : group.ToUpperInvariant();
				};

			var count = widget.GetOrNull<LabelWidget>("QUEUE_COUNT");
			if (count != null)
			{
				var cached = new CachedTransform<int, string>(c => c.ToString(CultureInfo.CurrentCulture) + " AVAILABLE");
				count.GetText = () => palette.CurrentQueue == null ? "" : cached.Update(palette.TotalIconCount);
			}

			const int BottomMargin = 12;
			var rowHeight = palette.IconSize.Y + palette.IconMargin.Y;

			// The sidebar stack is authored for a tall window: the header, radar, cash/time, power and the
			// production header eat a fixed 554px before the first cameo row. On a short window - a 720p
			// screen, or a UI scale that divides the window down - that leaves room for a single row of
			// buildings. Give the radar back to the palette until MinimumIconRows fit, then pull the wells
			// below the radar up by the same amount.
			const int MinimumIconRows = 3;
			const int MinimumRadarHeight = 120;
			var radarWell = widget.GetOrNull("RADAR_WELL");
			if (radarWell != null)
			{
				var wanted = palette.RenderOrigin.Y + MinimumIconRows * rowHeight - palette.IconMargin.Y + BottomMargin;
				var shrink = Math.Min(wanted - Game.Renderer.Resolution.Height, radarWell.Bounds.Height - MinimumRadarHeight);
				if (shrink > 0)
				{
					ShrinkRadar(radarWell, shrink);

					var top = radarWell.Bounds.Y;
					foreach (var w in widget.Children)
					{
						if (w == radarWell || w.Bounds.Y <= top)
							continue;

						w.Bounds.Y -= shrink;
						if (w.Id == "SIDEBAR_PRODUCTION")
							w.Bounds.Height += shrink;
					}
				}
			}

			var available = Game.Renderer.Resolution.Height - palette.RenderOrigin.Y - BottomMargin + palette.IconMargin.Y;
			palette.MaxIconRowOffset = Math.Max(1, available / rowHeight);

			// Keep the camera inside the map: the view stops where the map edge meets the sidebar / bottom panel
			// (engine patch patches/engine-viewport-clamp.patch)
			var bottomPanel = widget.Parent?.GetOrNull("PX_SELECTION_PANEL");
			Viewport.ViewInsets = () => (0, 0,
				widget.IsVisible() ? widget.Bounds.Width : 0,
				bottomPanel != null && bottomPanel.IsVisible() ? bottomPanel.Bounds.Height : 0);

			// The start position is set before the clamp exists: pull the camera inside the map once
			worldRenderer.Viewport.Center(worldRenderer.Viewport.CenterPosition);
		}

		/// <summary>
		/// Trims `shrink` pixels off the radar well: the map view and every layer stacked on it lose the
		/// height, and the centred "no signal" text moves up with the middle of the smaller view.
		/// </summary>
		static void ShrinkRadar(Widget radarWell, int shrink)
		{
			radarWell.Bounds.Height -= shrink;

			var radar = radarWell.GetOrNull("RADAR");
			if (radar == null)
				return;

			radar.Bounds.Height -= shrink;
			foreach (var layer in radar.Children)
			{
				layer.Bounds.Height -= shrink;

				// The minimap caches its preview scale and map rectangle from the bounds it was initialized
				// with (patches/engine-radar-resize.patch)
				if (layer is RadarWidget minimap)
					minimap.MapBoundsChanged();

				if (layer.Id != "RADAR_OFFLINE")
					continue;

				foreach (var label in layer.Children)
					label.Bounds.Y -= shrink / 2;
			}
		}

		protected override void Dispose(bool disposing)
		{
			Viewport.ViewInsets = null;
			base.Dispose(disposing);
		}
	}
}
