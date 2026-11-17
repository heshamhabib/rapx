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
	/// <summary>Runs after ProductionTooltipLogic (list it second in the template's Logic): swaps the plain DESC label
	/// for PxTooltipDesc@PXDESC (body text plus strong/weak tag rows with icons), adds the ARMAMENT block
	/// (PxWeaponLoadout@WEAPONS) under it, and grows the tooltip to fit both.</summary>
	public class PxProductionTooltipWeaponsLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxProductionTooltipWeaponsLogic(Widget widget, TooltipContainerWidget tooltipContainer, World world, Func<ProductionIcon> getTooltipIcon)
		{
			var weapons = widget.Get<PxWeaponLoadoutWidget>("WEAPONS");
			var desc = widget.Get<LabelWidget>("DESC");
			var pxDesc = widget.Get<PxTooltipDescWidget>("PXDESC");
			var backdrop = widget.Get("PXBACKDROP");
			var margin = desc.Bounds.X;
			var inner = tooltipContainer.BeforeRender;
			var lastHeight = -1;
			var lastWidth = -1;
			ActorInfo lastActor = null;
			var right = new[] { "COST", "COST_ICON", "TIME", "TIME_ICON", "POWER", "POWER_ICON" };

			desc.IsVisible = () => false;
			pxDesc.IsVisible = () => true;

			tooltipContainer.BeforeRender = () =>
			{
				inner?.Invoke();
				var actor = getTooltipIcon()?.Actor;
				weapons.SetActor(actor, world.Map.Rules);
				pxDesc.SetText(desc.GetText?.Invoke());

				// ProductionTooltipLogic lays the tooltip out again whenever its content changes: redo ours after it
				if (actor == lastActor && widget.Bounds.Height == lastHeight && widget.Bounds.Width == lastWidth)
					return;

				lastActor = actor;

				// The description: where DESC was, as wide as its tag rows need; the price column moves right to make room
				var grow = Math.Max(0, pxDesc.ContentWidth - desc.Bounds.Width);
				pxDesc.Bounds.X = desc.Bounds.X;
				pxDesc.Bounds.Y = desc.Bounds.Y + 2;
				pxDesc.Bounds.Width = Math.Max(desc.Bounds.Width, pxDesc.ContentWidth);
				pxDesc.Bounds.Height = pxDesc.ContentHeight;

				var rightBottom = 0;
				foreach (var id in right)
				{
					var w = widget.GetOrNull(id);
					if (w == null)
						continue;

					w.Bounds.X += grow;
					if (w.IsVisible())
						rightBottom = Math.Max(rightBottom, w.Bounds.Bottom);
				}

				var width = widget.Bounds.Width + grow;
				var bottom = Math.Max(pxDesc.Bounds.Bottom, rightBottom);

				weapons.Visible = weapons.ContentHeight > 0;
				if (weapons.Visible)
				{
					var extra = Math.Max(0, weapons.ContentWidth + 2 * margin - width);
					foreach (var id in right)
					{
						var w = widget.GetOrNull(id);
						if (w != null)
							w.Bounds.X += extra;
					}

					width += extra;
					weapons.Bounds.X = margin;
					weapons.Bounds.Y = bottom + 6;
					weapons.Bounds.Width = width - 2 * margin;
					weapons.Bounds.Height = weapons.ContentHeight;
					bottom = weapons.Bounds.Bottom;
				}

				widget.Bounds.Width = width;
				widget.Bounds.Height = bottom + margin;
				backdrop.Bounds = new WidgetBounds(3, 3, widget.Bounds.Width - 6, widget.Bounds.Height - 6);
				lastHeight = widget.Bounds.Height;
				lastWidth = widget.Bounds.Width;
			};
		}
	}
}
