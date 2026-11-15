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
	/// Binds the mod's graphics quality checkboxes on the Display settings panel (listed after DisplaySettingsLogic).
	/// Both settings apply immediately; the stock settings panel saves them when it closes.
	/// </summary>
	public class PxDisplaySettingsLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public PxDisplaySettingsLogic(Widget widget)
		{
			var ds = Game.Settings.Graphics;

			var hdWorld = widget.Get<CheckboxWidget>("PX_HD_WORLD_CHECKBOX");
			hdWorld.IsChecked = () => ds.NativeResolutionWorld;
			hdWorld.OnClick = () =>
			{
				ds.NativeResolutionWorld ^= true;
				Game.Renderer.RefreshWorldBuffer();
			};

			var smoothMotion = widget.Get<CheckboxWidget>("PX_SMOOTH_MOTION_CHECKBOX");
			smoothMotion.IsChecked = () => ds.SmoothMotion;
			smoothMotion.OnClick = () => ds.SmoothMotion ^= true;

			// The passes these two switch off are built when a world loads, so the change lands on the next
			// match rather than the one being played. Both are the difference between a slideshow and a
			// playable frame rate on an integrated GPU.
			var groundEffects = widget.Get<CheckboxWidget>("PX_GROUND_EFFECTS_CHECKBOX");
			groundEffects.IsChecked = () => ds.GroundEffects;
			groundEffects.OnClick = () => ds.GroundEffects ^= true;

			var weatherEffects = widget.Get<CheckboxWidget>("PX_WEATHER_EFFECTS_CHECKBOX");
			weatherEffects.IsChecked = () => ds.WeatherEffects;
			weatherEffects.OnClick = () => ds.WeatherEffects ^= true;
		}
	}
}
