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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>Runs after ProductionTooltipLogic (list it second in the template's Logic): adds the ARMAMENT block
	/// (PxWeaponLoadout@WEAPONS) under the description and grows the tooltip to fit it.</summary>
	public class PxProductionTooltipWeaponsLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxProductionTooltipWeaponsLogic(Widget widget, TooltipContainerWidget tooltipContainer, World world, Func<ProductionIcon> getTooltipIcon)
		{
			var weapons = widget.Get<PxWeaponLoadoutWidget>("WEAPONS");
			var desc = widget.Get<LabelWidget>("DESC");
			var margin = desc.Bounds.X;
			var inner = tooltipContainer.BeforeRender;
			var lastHeight = -1;
			var lastWidth = -1;
			ActorInfo lastActor = null;
			var right = new[] { "COST", "COST_ICON", "TIME", "TIME_ICON", "POWER", "POWER_ICON" };

			tooltipContainer.BeforeRender = () =>
			{
				inner?.Invoke();
				var actor = getTooltipIcon()?.Actor;
				weapons.SetActor(actor, world.Map.Rules);

				// ProductionTooltipLogic resizes the tooltip whenever its text changes: add the block under it then
				if (actor == lastActor && widget.Bounds.Height == lastHeight && widget.Bounds.Width == lastWidth)
					return;

				lastActor = actor;

				weapons.Visible = weapons.ContentHeight > 0;
				if (!weapons.Visible)
				{
					lastHeight = widget.Bounds.Height;
					lastWidth = widget.Bounds.Width;
					return;
				}

				var top = Math.Max(desc.Bounds.Bottom, widget.Bounds.Height - margin) + 2;
				var width = Math.Max(widget.Bounds.Width, weapons.ContentWidth + 2 * margin);

				// Keep price, build time and power on the right edge of the wider tooltip
				foreach (var id in right)
				{
					var w = widget.GetOrNull(id);
					if (w != null)
						w.Bounds.X += width - widget.Bounds.Width;
				}

				widget.Bounds.Width = width;
				weapons.Bounds.X = margin;
				weapons.Bounds.Y = top;
				weapons.Bounds.Width = widget.Bounds.Width - 2 * margin;
				weapons.Bounds.Height = weapons.ContentHeight;
				widget.Bounds.Height = weapons.Bounds.Bottom + margin;
				lastHeight = widget.Bounds.Height;
				lastWidth = widget.Bounds.Width;
			};
		}
	}
}
