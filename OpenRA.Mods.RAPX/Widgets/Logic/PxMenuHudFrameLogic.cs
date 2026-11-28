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

using OpenRA.Graphics;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// The in-game menu hides the HUD, but the camera clamp and PxHudOcclusion still treat the sidebar and bottom panel
	/// as covering the world, so the half-drawn world under them would show. Empty HUD-styled panels fill the same
	/// space instead and frame the map view while the menu is open.
	/// </summary>
	public class PxMenuHudFrameLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxMenuHudFrameLogic(Widget widget)
		{
			var side = widget.GetOrNull("PX_HUD_FRAME_SIDE");
			var bottom = widget.GetOrNull("PX_HUD_FRAME_BOTTOM");

			var (_, _, right, under) = Viewport.ViewInsets?.Invoke() ?? (0, 0, 0, 0);
			var window = Game.Renderer.Resolution;

			if (side != null)
			{
				side.Bounds.X = window.Width - right;
				side.Bounds.Width = right;
				side.Bounds.Height = window.Height;
				side.IsVisible = () => right > 0;
			}

			if (bottom != null)
			{
				bottom.Bounds.Y = window.Height - under;
				bottom.Bounds.Width = window.Width - right;
				bottom.Bounds.Height = under;
				bottom.IsVisible = () => under > 0;
			}
		}
	}
}
