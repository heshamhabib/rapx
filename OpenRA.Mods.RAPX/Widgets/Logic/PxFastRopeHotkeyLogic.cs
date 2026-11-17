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

using System.Collections.Generic;
using System.Linq;
using OpenRA.Mods.Common.Lint;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Mods.Common.Widgets.Logic;
using OpenRA.Mods.RAPX.Orders;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>Fast-rope key (IDEA-47, G): pick a landing zone for the selected transport helicopters.
	/// Pressing it again or Escape leaves the mode.</summary>
	[ChromeLogicArgsHotkeys("PxFastRopeKey")]
	public class PxFastRopeHotkeyLogic : SingleHotkeyBaseLogic
	{
		[FluentReference]
		const string FastRopeModeStarted = "notification-px-fast-rope-mode";

		[FluentReference]
		const string NothingToRope = "notification-px-fast-rope-none";

		readonly World world;

		public readonly string ClickSound = ChromeMetrics.Get<string>("ClickSound");
		public readonly string ClickDisabledSound = ChromeMetrics.Get<string>("ClickDisabledSound");

		[ObjectCreator.UseCtor]
		public PxFastRopeHotkeyLogic(Widget widget, ModData modData, World world, Dictionary<string, MiniYaml> logicArgs)
			: base(widget, modData, "PxFastRopeKey", "WORLD_KEYHANDLER", logicArgs)
		{
			this.world = world;

			widget.Get<LogicKeyListenerWidget>("WORLD_KEYHANDLER").AddHandler(e =>
			{
				if (e.Event != KeyInputEvent.Down || e.Key != Keycode.ESCAPE || world.OrderGenerator is not PxFastRopeOrderGenerator)
					return false;

				world.CancelInputMode();
				return true;
			});
		}

		protected override bool OnHotkeyActivated(KeyInput e)
		{
			if (world.IsGameOver || world.LocalPlayer == null)
				return false;

			if (world.OrderGenerator is PxFastRopeOrderGenerator)
			{
				world.CancelInputMode();
				return true;
			}

			if (!world.Selection.Actors.Any(PxFastRopeOrderGenerator.CanRope))
			{
				TextNotificationsManager.AddFeedbackLine(NothingToRope);
				Game.Sound.PlayNotification(world.Map.Rules, world.LocalPlayer, "Sounds", ClickDisabledSound, null);
				return false;
			}

			world.OrderGenerator = new PxFastRopeOrderGenerator();
			TextNotificationsManager.AddFeedbackLine(FastRopeModeStarted);
			Game.Sound.PlayNotification(world.Map.Rules, world.LocalPlayer, "Sounds", ClickSound, null);
			return true;
		}
	}
}
