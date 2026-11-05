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

using System.Globalization;
using System.Linq;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Network;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>Fills the RAPX lobby's header chips and match summary, and shares the order manager with row widgets.</summary>
	public class PxLobbyExtrasLogic : ChromeLogic
	{
		readonly ModData modData;
		readonly OrderManager orderManager;
		string cachedMapUid;
		LobbyOption[] options = System.Array.Empty<LobbyOption>();

		[ObjectCreator.UseCtor]
		public PxLobbyExtrasLogic(Widget widget, ModData modData, OrderManager orderManager)
		{
			this.modData = modData;
			this.orderManager = orderManager;
			PxLobbyState.OrderManager = orderManager;

			Bind(widget, "CHIP_PLAYERS_VALUE", () =>
			{
				var lobby = orderManager.LobbyInfo;
				var taken = lobby.Clients.Count(c => c.Slot != null && !c.IsObserver);
				var total = lobby.Slots.Values.Count(s => !s.Closed);
				return taken.ToString(CultureInfo.CurrentCulture) + "/" + total.ToString(CultureInfo.CurrentCulture);
			});

			Bind(widget, "CHIP_SPEED_VALUE", () => OptionValue("gamespeed"));
			Bind(widget, "CHIP_CASH_VALUE", () => OptionValue("startingcash"));
			Bind(widget, "SUM_CASH_VALUE", () => OptionValue("startingcash"));
			Bind(widget, "SUM_UNITS_VALUE", () => OptionValue("startingunits"));
			Bind(widget, "SUM_SPEED_VALUE", () => OptionValue("gamespeed"));
			Bind(widget, "SUM_TIME_VALUE", () => OptionValue("timelimit"));
			Bind(widget, "SUM_TREATY_VALUE", () => OptionValue("peacetreaty"));
		}

		static void Bind(Widget root, string id, System.Func<string> getText)
		{
			var label = root.GetOrNull<LabelWidget>(id);
			if (label != null)
				label.GetText = () => getText().ToUpperInvariant();
		}

		string OptionValue(string id)
		{
			var settings = orderManager.LobbyInfo.GlobalSettings;
			if (settings.Map != cachedMapUid)
			{
				cachedMapUid = settings.Map;
				var preview = settings.Map != null ? modData.MapCache[settings.Map] : null;
				options = preview?.WorldActorInfo == null ? System.Array.Empty<LobbyOption>() :
					preview.PlayerActorInfo.TraitInfos<ILobbyOptions>()
						.Concat(preview.WorldActorInfo.TraitInfos<ILobbyOptions>())
						.SelectMany(t => t.LobbyOptions(preview))
						.ToArray();
			}

			var option = options.FirstOrDefault(o => o.Id == id);
			if (option == null || !settings.LobbyOptions.TryGetValue(id, out var state))
				return "—";

			return state.Value != null && option.Values.TryGetValue(state.Value, out var label) ? label : "—";
		}

		protected override void Dispose(bool disposing)
		{
			if (PxLobbyState.OrderManager == orderManager)
				PxLobbyState.OrderManager = null;

			base.Dispose(disposing);
		}
	}
}
