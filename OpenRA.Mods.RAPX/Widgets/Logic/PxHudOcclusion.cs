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
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// PERF: the in-game sidebar and bottom panel are opaque and the world view continues under them (about a third of the
	/// window at 2940x1846), so the full-screen passes (terrain detail, cloud shadows, weather, shroud) skip the pixels
	/// they cover. Set as WorldRenderer.VisibleViewArea by the sidebar logics, which also publish Viewport.ViewInsets.
	/// </summary>
	public static class PxHudOcclusion
	{
		// World pixels of the covered area still drawn around the visible part: passes read their neighbours' pixels up to
		// ~14 world pixels away (painted-map water refraction, rain ripples, heat haze), and each pass chains on the last
		const int Margin = 32;

		// RAPX_NO_HUD_CLIP=1 draws the passes under the HUD too, for before/after comparisons
		static readonly bool Disabled = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_NO_HUD_CLIP"));

		public static Rectangle? VisibleViewArea(WorldRenderer wr)
		{
			if (Disabled || Viewport.ViewInsets == null || wr.World.Type != WorldType.Regular)
				return null;

			var (left, top, right, bottom) = Viewport.ViewInsets();
			if (left <= 0 && top <= 0 && right <= 0 && bottom <= 0)
				return null;

			// Blast waves bend the picture by up to tens of world pixels around big explosions: draw everything meanwhile
			var waves = wr.World.WorldActor.TraitOrDefault<PxBlastWaves>();
			if (waves != null && ((IRenderPostProcessPass)waves).Enabled)
				return null;

			// UI pixels to world pixels, as Viewport.CenterLimits converts the same insets
			var scale = Game.Settings.Graphics.UIScale / wr.Viewport.Zoom;
			var view = wr.Viewport.BottomRight - wr.Viewport.TopLeft;
			return Rectangle.FromLTRB(
				Math.Max(0, (int)(left * scale) - Margin),
				Math.Max(0, (int)(top * scale) - Margin),
				view.X - (int)(right * scale) + Margin,
				view.Y - (int)(bottom * scale) + Margin);
		}
	}
}
