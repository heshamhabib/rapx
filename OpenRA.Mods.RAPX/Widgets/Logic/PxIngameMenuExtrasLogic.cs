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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Adds "Controls" (above the buttons that leave the game) and "Exit to Desktop" (last) to the in-game menu
	/// built by IngameMenuLogic. Must be listed after IngameMenuLogic so the stock buttons already exist.
	/// </summary>
	public class PxIngameMenuExtrasLogic : ChromeLogic
	{
		[FluentReference]
		const string ControlsButton = "menu-ingame-px-controls";

		[FluentReference]
		const string ExitButton = "menu-ingame-px-exit-desktop";

		[FluentReference]
		const string ExitTitle = "dialog-px-exit-desktop.title";

		[FluentReference]
		const string ExitPrompt = "dialog-px-exit-desktop.prompt";

		[FluentReference]
		const string ExitAccept = "dialog-px-exit-desktop.confirm";

		[FluentReference]
		const string ExitCancel = "dialog-px-exit-desktop.cancel";

		// Stock buttons that end or leave the game: Controls goes above them so they sit next to Exit to Desktop
		static readonly string[] LeaveButtons = { "SURRENDER", "RESTART", "BACK_TO_EDITOR", "ABORT_MISSION" };

		readonly Widget container;
		readonly List<ButtonWidget> buttons;
		readonly int stride;
		bool hidden;

		[ObjectCreator.UseCtor]
		public PxIngameMenuExtrasLogic(Widget widget, ModData modData, World world)
		{
			var menu = widget.Get("INGAME_MENU");
			container = menu.Get("MENU_BUTTONS");
			buttons = container.Children.OfType<ButtonWidget>().ToList();
			if (buttons.Count == 0)
				return;

			// Same spacing as the stock buttons (falls back to the button height plus a gap)
			stride = buttons.Count > 1
				? buttons[^1].Bounds.Y - buttons[^2].Bounds.Y
				: buttons[^1].Bounds.Height + 10;

			// Hide the menu (and the info panel) while one of our dialogs is open
			var containerVisible = container.IsVisible;
			container.IsVisible = () => !hidden && containerVisible();
			var panelRoot = menu.GetOrNull("PANEL_ROOT");
			if (panelRoot != null)
			{
				var panelVisible = panelRoot.IsVisible;
				panelRoot.IsVisible = () => !hidden && panelVisible();
			}

			if (world.Type == WorldType.Regular)
			{
				var leave = buttons.FindIndex(b => LeaveButtons.Contains(b.Id));
				AddButton("PX_CONTROLS", ControlsButton, leave < 0 ? buttons.Count : leave, () =>
				{
					hidden = true;
					Ui.OpenWindow("PX_CONTROLS_PANEL", new WidgetArgs
					{
						{ "onExit", () => hidden = false }
					});
				});
			}

			AddButton("EXIT_DESKTOP", ExitButton, buttons.Count, () =>
			{
				hidden = true;
				ConfirmationDialogs.ButtonPrompt(modData,
					title: ExitTitle,
					text: ExitPrompt,
					onConfirm: Game.Exit,
					confirmText: ExitAccept,
					onCancel: () => hidden = false,
					cancelText: ExitCancel);
			});
		}

		/// <summary>Inserts a button at <paramref name="index"/> in the visible order, pushing the ones below it down.</summary>
		void AddButton(string id, string label, int index, Action onClick)
		{
			var last = buttons[^1];
			var button = (ButtonWidget)last.Clone();
			button.Id = id;
			button.Bounds.Y = index < buttons.Count ? buttons[index].Bounds.Y : last.Bounds.Y + stride;
			for (var i = index; i < buttons.Count; i++)
				buttons[i].Bounds.Y += stride;

			var text = FluentProvider.GetMessage(label);
			button.GetText = () => text;
			button.IsDisabled = () => false;
			button.OnClick = onClick;
			container.AddChild(button);
			buttons.Insert(index, button);

			// Grow the panel and keep it vertically centred, like IngameMenuLogic does
			container.Bounds.Height += stride;
			container.Bounds.Y -= stride / 2;
		}
	}
}
