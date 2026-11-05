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
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Mods.RAPX.Orders;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Bottom selection panel: shows the unit command and stance keys while units (or nothing) are selected,
	/// and Repair / Sell / Power / Rally keys acting directly on the selected structures otherwise.
	/// </summary>
	public class PxSelectionPanelLogic : ChromeLogic
	{
		readonly World world;

		[ObjectCreator.UseCtor]
		public PxSelectionPanelLogic(Widget widget, World world)
		{
			this.world = world;

			var buildingActions = widget.Get("BUILDING_ACTIONS");
			buildingActions.IsVisible = ShowBuildingActions;
			foreach (var id in new[] { "COMMAND_BAR", "STANCE_BAR", "COMMANDS_LABEL" })
			{
				var w = widget.GetOrNull(id);
				if (w != null)
					w.IsVisible = () => !ShowBuildingActions();
			}

			Bind(widget.Get<ButtonWidget>("REPAIR_SELECTED"),
				() => Owned<RepairableBuilding>().Any(a => a.TraitOrDefault<IHealth>()?.DamageState > DamageState.Undamaged || IsRepairing(a)),
				() => Owned<RepairableBuilding>().Any(IsRepairing),
				Repair);

			Bind(widget.Get<ButtonWidget>("SELL_SELECTED"),
				() => Owned<Sellable>().Any(),
				() => false,
				() => Issue(Owned<Sellable>(), "Sell"));

			Bind(widget.Get<ButtonWidget>("POWER_SELECTED"),
				() => PowerDownable().Any(),
				() => false,
				() => Issue(PowerDownable(), "PowerDown"));

			Bind(widget.Get<ButtonWidget>("RALLY_SELECTED"),
				() => OwnedWithInfo<RallyPointInfo>().Any(),
				() => world.OrderGenerator is PxRallyPointOrderGenerator,
				() =>
				{
					if (world.OrderGenerator is PxRallyPointOrderGenerator)
						world.CancelInputMode();
					else
						world.OrderGenerator = new PxRallyPointOrderGenerator(OwnedWithInfo<RallyPointInfo>());
				});
		}

		IEnumerable<Actor> OwnedSelection() =>
			PxSelection.Groups(world).SelectMany(g => g.Actors).Where(a => a.Owner == world.LocalPlayer);

		bool ShowBuildingActions()
		{
			var owned = OwnedSelection().ToList();
			return owned.Count > 0 && owned.All(a => a.Info.HasTraitInfo<BuildingInfo>());
		}

		IEnumerable<Actor> Owned<T>() where T : class =>
			OwnedSelection().Where(a => a.Info.HasTraitInfo<BuildingInfo>() && a.TraitsImplementing<T>().Any(t => t is not IDisabledTrait d || !d.IsTraitDisabled));

		IEnumerable<Actor> OwnedWithInfo<T>() where T : class, ITraitInfoInterface =>
			OwnedSelection().Where(a => a.Info.HasTraitInfo<T>());

		IEnumerable<Actor> PowerDownable() =>
			Owned<ToggleConditionOnOrder>().Where(a => a.TraitsImplementing<ToggleConditionOnOrder>().Any(t => t.Info.OrderName == "PowerDown"));

		static bool IsRepairing(Actor a) => a.TraitsImplementing<RepairableBuilding>().Any(r => r.RepairActive);

		void Repair()
		{
			var buildings = Owned<RepairableBuilding>().ToList();
			var start = buildings.Where(a => !IsRepairing(a) && a.TraitOrDefault<IHealth>()?.DamageState > DamageState.Undamaged).ToList();

			// Start repairing anything damaged; if everything already repairs, toggle repairs off instead
			var targets = start.Count > 0 ? start : buildings.Where(IsRepairing).ToList();
			foreach (var a in targets)
				world.IssueOrder(new Order("RepairBuilding", world.LocalPlayer.PlayerActor, Target.FromActor(a), false));
		}

		void Issue(IEnumerable<Actor> actors, string order)
		{
			foreach (var a in actors.ToList())
				world.IssueOrder(new Order(order, a, false));
		}

		static void Bind(ButtonWidget button, Func<bool> enabled, Func<bool> highlighted, Action onClick)
		{
			button.IsDisabled = () => !enabled();
			button.IsHighlighted = highlighted;
			button.OnClick = onClick;
			WidgetUtils.BindButtonIcon(button);
		}
	}
}
