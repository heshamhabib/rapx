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

using OpenRA.Mods.Common.Widgets;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Binds the CONTROL_SCHEME_DROPDOWN (and optional CONTROL_SCHEME_DESC label) found under the widget.
	/// Used on the Input settings panel and on the first-launch introduction prompt.
	/// </summary>
	public class PxControlSchemeLogic : ChromeLogic
	{
		// Checking every hotkey is cheap but not free, so the current scheme is re-read a few times per second
		const int RefreshMs = 250;

		readonly ModData modData;
		string current;
		long lastRefresh = -RefreshMs;

		[ObjectCreator.UseCtor]
		public PxControlSchemeLogic(Widget widget, ModData modData)
		{
			this.modData = modData;

			var dropdown = widget.GetOrNull<DropDownButtonWidget>("CONTROL_SCHEME_DROPDOWN");
			if (dropdown != null)
			{
				dropdown.GetText = () => PxControlSchemes.Name(Current());
				dropdown.OnMouseDown = _ =>
				{
					ScrollItemWidget SetupItem(string scheme, ScrollItemWidget itemTemplate)
					{
						var item = ScrollItemWidget.Setup(itemTemplate,
							() => Current() == scheme,
							() =>
							{
								PxControlSchemes.Apply(modData, scheme);
								current = scheme;
							});
						item.Get<LabelWidget>("LABEL").GetText = () => PxControlSchemes.Name(scheme);
						return item;
					}

					dropdown.ShowDropDown("LABEL_DROPDOWN_TEMPLATE", 500, PxControlSchemes.Presets, SetupItem);
				};
			}

			var desc = widget.GetOrNull<LabelWidget>("CONTROL_SCHEME_DESC");
			if (desc != null)
				desc.GetText = () => PxControlSchemes.Description(Current());
		}

		string Current()
		{
			if (current == null || Game.RunTime - lastRefresh >= RefreshMs)
			{
				current = PxControlSchemes.Current(modData);
				lastRefresh = Game.RunTime;
			}

			return current;
		}
	}
}
