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
	/// The standalone music window (main menu Extras and the in-game menu): hosts the same
	/// LOBBY_MUSIC_BIN player the lobby Music tab shows, plus a Back button.
	/// </summary>
	public class PxMusicPanelLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxMusicPanelLogic(Widget widget, World world, Action onExit)
		{
			Ui.LoadWidget("LOBBY_MUSIC_BIN", widget.Get("PLAYER_ROOT"), new WidgetArgs
			{
				{ "onExit", () => { } },
				{ "world", world }
			});

			widget.Get<ButtonWidget>("BACK_BUTTON").OnClick = () =>
			{
				Ui.CloseWindow();
				onExit();
			};
		}
	}
}
