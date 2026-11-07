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
	/// <summary>
	/// Main menu Extras > Catalogue button: hides the menu column (MainMenuLogic has no menu state for us)
	/// and opens PX_CATALOGUE_PANEL on top of the shellmap, whose world renders the model previews.
	/// </summary>
	public class PxCatalogueButtonLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxCatalogueButtonLogic(Widget widget)
		{
			var open = false;
			var menus = widget.Parent?.Parent;
			if (menus != null)
				menus.IsVisible = () => !open;

			((ButtonWidget)widget).OnClick = () =>
			{
				open = true;
				Game.OpenWindow("PX_CATALOGUE_PANEL", new WidgetArgs
				{
					{ "onExit", () => open = false }
				});
			};
		}
	}

	public class PxCatalogueLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxCatalogueLogic(Widget widget, Action onExit)
		{
			widget.Get<ButtonWidget>("BACK_BUTTON").OnClick = () =>
			{
				Ui.CloseWindow();
				onExit();
			};
		}
	}
}
