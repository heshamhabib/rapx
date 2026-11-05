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
	/// <summary>Waypoint mode key (IDEA-11): first press starts a route, second press sends it, Escape cancels.</summary>
	[ChromeLogicArgsHotkeys("PxWaypointModeKey")]
	public class PxWaypointHotkeyLogic : SingleHotkeyBaseLogic
	{
		[FluentReference]
		const string WaypointModeStarted = "notification-px-waypoint-mode";

		readonly World world;

		public readonly string ClickSound = ChromeMetrics.Get<string>("ClickSound");
		public readonly string ClickDisabledSound = ChromeMetrics.Get<string>("ClickDisabledSound");

		[ObjectCreator.UseCtor]
		public PxWaypointHotkeyLogic(Widget widget, ModData modData, World world, Dictionary<string, MiniYaml> logicArgs)
			: base(widget, modData, "PxWaypointModeKey", "WORLD_KEYHANDLER", logicArgs)
		{
			this.world = world;

			widget.Get<LogicKeyListenerWidget>("WORLD_KEYHANDLER").AddHandler(e =>
			{
				if (e.Event != KeyInputEvent.Down || e.Key != Keycode.ESCAPE || world.OrderGenerator is not PxWaypointOrderGenerator)
					return false;

				world.CancelInputMode();
				return true;
			});
		}

		protected override bool OnHotkeyActivated(KeyInput e)
		{
			if (world.IsGameOver || world.LocalPlayer == null)
				return false;

			if (world.OrderGenerator is PxWaypointOrderGenerator waypoints)
			{
				var orders = waypoints.SendRoute(world);
				orders.PlayVoiceForOrders();
				foreach (var o in orders)
					world.IssueOrder(o);

				return true;
			}

			if (!world.Selection.Actors.Any(PxWaypointOrderGenerator.CanMove))
			{
				Game.Sound.PlayNotification(world.Map.Rules, world.LocalPlayer, "Sounds", ClickDisabledSound, null);
				return false;
			}

			world.OrderGenerator = new PxWaypointOrderGenerator();
			TextNotificationsManager.AddFeedbackLine(WaypointModeStarted);
			Game.Sound.PlayNotification(world.Map.Rules, world.LocalPlayer, "Sounds", ClickSound, null);
			return true;
		}
	}
}
