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
using OpenRA.Mods.Common.Widgets.Logic;
using OpenRA.Network;
using OpenRA.Primitives;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Lobby options laid out as sections: on/off switches split into Battlefield and Rules columns, a row of
	/// Match Setup cards for the dropdown options, and Developer options (the debug menu) along the bottom.
	/// </summary>
	public class PxLobbyOptionsLogic : ChromeLogic
	{
		[FluentReference]
		const string NotAvailable = "label-not-available";

		static readonly HashSet<string> Battlefield = new() { "explored", "fog", "separateteamspawns", "buildradius", "shortgame" };
		static readonly HashSet<string> Developer = new() { "cheats" };

		readonly Func<MapPreview> getMap;
		readonly OrderManager orderManager;
		readonly Func<bool> configurationDisabled;
		readonly Widget battlefieldColumn, rulesColumn, setupRow, developerRow;
		readonly Widget switchTemplate, cardTemplate;
		MapPreview mapPreview;

		[ObjectCreator.UseCtor]
		public PxLobbyOptionsLogic(Widget widget, OrderManager orderManager, Func<MapPreview> getMap, Func<bool> configurationDisabled)
		{
			this.getMap = getMap;
			this.orderManager = orderManager;
			this.configurationDisabled = configurationDisabled;

			battlefieldColumn = widget.Get("BATTLEFIELD_OPTIONS");
			rulesColumn = widget.Get("RULES_OPTIONS");
			setupRow = widget.Get("SETUP_OPTIONS");
			developerRow = widget.Get("DEVELOPER_OPTIONS");
			switchTemplate = widget.Get("SWITCH_TEMPLATE");
			cardTemplate = widget.Get("CARD_TEMPLATE");
			switchTemplate.IsVisible = () => false;
			cardTemplate.IsVisible = () => false;

			mapPreview = getMap();
			RebuildOptions();
		}

		public override void Tick()
		{
			var newMapPreview = getMap();
			if (newMapPreview == mapPreview)
				return;

			// We are currently enumerating the widget tree and so can't modify any layout
			Game.RunAfterTick(() =>
			{
				mapPreview = newMapPreview;
				RebuildOptions();
			});
		}

		static string Hint(LobbyOption option)
		{
			if (option.Description == null)
				return "";

			var (text, desc) = LobbyUtils.SplitOnFirstToken(option.Description);
			return (desc ?? text).Replace("\n", " ").Trim();
		}

		void RebuildOptions()
		{
			if (mapPreview == null || mapPreview.WorldActorInfo == null)
				return;

			foreach (var c in new[] { battlefieldColumn, rulesColumn, setupRow, developerRow })
				c.RemoveChildren();

			var allOptions = mapPreview.PlayerActorInfo.TraitInfos<ILobbyOptions>()
				.Concat(mapPreview.WorldActorInfo.TraitInfos<ILobbyOptions>())
				.SelectMany(t => t.LobbyOptions(mapPreview))
				.Where(o => o.IsVisible)
				.OrderBy(o => o.DisplayOrder)
				.ToArray();

			static string IconFor(string id) => ChromeProvider.TryGetImage("px-option-icons", id) != null ? id : "default";

			foreach (var option in allOptions.Where(o => o is LobbyBooleanOption))
			{
				var column = Developer.Contains(option.Id) ? developerRow : Battlefield.Contains(option.Id) ? battlefieldColumn : rulesColumn;
				var sw = (PxOptionSwitchWidget)switchTemplate.Clone();
				sw.IsVisible = () => true;
				sw.Icon = IconFor(option.Id);

				if (column == developerRow)
				{
					sw.Bounds.X = column.Children.Sum(c => c.Bounds.Width + 8);
					sw.Bounds.Width = 300;
					sw.Bounds.Y = 0;
				}
				else
				{
					sw.Bounds.Y = column.Children.Sum(c => c.Bounds.Height + 6);
					sw.Bounds.Width = column.Bounds.Width;
				}

				var optionEnabled = new PredictedCachedTransform<Session.Global, bool>(gs => gs.LobbyOptions[option.Id].IsEnabled);
				var optionLocked = new CachedTransform<Session.Global, bool>(gs => gs.LobbyOptions[option.Id].IsLocked);

				sw.GetText = () => option.Name;
				var hint = Hint(option);
				sw.GetHint = () => hint;
				if (option.Description != null)
				{
					var (text, desc) = LobbyUtils.SplitOnFirstToken(option.Description);
					sw.GetTooltipText = () => text;
					sw.GetTooltipDesc = () => desc;
				}

				sw.IsChecked = () => optionEnabled.Update(orderManager.LobbyInfo.GlobalSettings);
				sw.IsDisabled = () => configurationDisabled() || optionLocked.Update(orderManager.LobbyInfo.GlobalSettings);
				sw.OnClick = () =>
				{
					var state = !optionEnabled.Update(orderManager.LobbyInfo.GlobalSettings);
					orderManager.IssueOrder(Order.Command($"option {option.Id} {state}"));
					optionEnabled.Predict(state);
				};

				column.AddChild(sw);
			}

			var dropdowns = allOptions.Where(o => o is not LobbyBooleanOption).ToList();

			// Balanced grid of at most MaxColumns cards per row, so values like "HEAVY SUPPORT" are not truncated
			const int Gap = 8;
			const int MaxColumns = 4;
			var rows = Math.Max(1, (dropdowns.Count + MaxColumns - 1) / MaxColumns);
			var columns = Math.Max(1, (dropdowns.Count + rows - 1) / rows);
			var cardWidth = (setupRow.Bounds.Width - (columns - 1) * Gap) / columns;
			var cardHeight = Math.Min(cardTemplate.Bounds.Height, (setupRow.Bounds.Height - (rows - 1) * Gap) / rows);
			var index = 0;
			foreach (var option in dropdowns)
			{
				var card = (PxOptionCardWidget)cardTemplate.Clone();
				card.IsVisible = () => true;
				card.Icon = IconFor(option.Id);
				card.Bounds.X = index % columns * (cardWidth + Gap);
				card.Bounds.Y = index++ / columns * (cardHeight + Gap);
				card.Bounds.Width = cardWidth;
				card.Bounds.Height = cardHeight;
				if (option.Id == "startingcash")
					card.ValueColor = Color.FromArgb(255, 209, 102);

				var optionValue = new CachedTransform<Session.Global, Session.LobbyOptionState>(gs => gs.LobbyOptions[option.Id]);
				var getOptionLabel = new CachedTransform<string, string>(id =>
					id == null || !option.Values.TryGetValue(id, out var value) ? FluentProvider.GetMessage(NotAvailable) : value);

				card.GetTitle = () => option.Name;
				card.GetText = () => getOptionLabel.Update(optionValue.Update(orderManager.LobbyInfo.GlobalSettings).Value);
				if (option.Description != null)
				{
					var (text, desc) = LobbyUtils.SplitOnFirstToken(option.Description);
					card.GetTooltipText = () => text;
					card.GetTooltipDesc = () => desc;
				}

				card.IsDisabled = () => configurationDisabled() || optionValue.Update(orderManager.LobbyInfo.GlobalSettings).IsLocked;
				card.OnMouseDown = _ =>
				{
					ScrollItemWidget SetupItem(KeyValuePair<string, string> c, ScrollItemWidget template)
					{
						bool IsSelected() => optionValue.Update(orderManager.LobbyInfo.GlobalSettings).Value == c.Key;
						void OnClick() => orderManager.IssueOrder(Order.Command($"option {option.Id} {c.Key}"));

						var item = ScrollItemWidget.Setup(template, IsSelected, OnClick);
						item.Get<LabelWidget>("LABEL").GetText = () => c.Value;
						return item;
					}

					card.ShowDropDown("LABEL_DROPDOWN_TEMPLATE", option.Values.Count * 30, option.Values, SetupItem);
				};

				setupRow.AddChild(card);
			}
		}
	}
}
