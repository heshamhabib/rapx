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
	/// <summary>Main menu Language button: hides the menu column and opens PX_LANGUAGE_PANEL.</summary>
	public class PxLanguageButtonLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxLanguageButtonLogic(Widget widget)
		{
			var open = false;
			var menus = widget.Parent?.Parent;
			if (menus != null)
				menus.IsVisible = () => !open;

			((ButtonWidget)widget).OnClick = () =>
			{
				open = true;
				Game.OpenWindow("PX_LANGUAGE_PANEL", new WidgetArgs
				{
					{ "onExit", () => open = false }
				});
			};
		}
	}

	/// <summary>
	/// Saves the picked language to Game.Settings.Player.Language and reloads the mod, which rebuilds the
	/// translations (FluentProvider) and the fonts (the language may swap them) the same way a mod switch does.
	/// </summary>
	public class PxLanguageLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxLanguageLogic(Widget widget, Action onExit)
		{
			var languages = widget.Get<PxLanguageWidget>("LANGUAGES");

			void Apply(string id)
			{
				if (id == FluentLanguages.SelectedId)
					return;

				Game.Settings.Player.Language = id;
				Game.Settings.Save();
				var mod = Game.ModData.Manifest.Id;
				Game.RunAfterTick(() => Game.InitializeMod(mod, new Arguments()));
			}

			languages.OnActivate = Apply;

			widget.Get<ButtonWidget>("BACK_BUTTON").OnClick = () =>
			{
				Ui.CloseWindow();
				onExit();
			};

			var apply = widget.Get<ButtonWidget>("APPLY_BUTTON");
			apply.IsDisabled = () => languages.Selected == FluentLanguages.SelectedId;
			apply.IsHighlighted = () => !apply.IsDisabled();
			apply.OnClick = () => Apply(languages.Selected);
		}
	}
}
