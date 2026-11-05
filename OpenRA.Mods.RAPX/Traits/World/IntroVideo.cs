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
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Plays a fullscreen video over the main menu the first time the shellmap loads after the game starts.")]
	public class IntroVideoInfo : TraitInfo
	{
		[FieldLoader.Require]
		[Desc("Video file to play.")]
		public readonly string Video = null;

		[Desc("Widget tree that plays the video.")]
		public readonly string Widget = "INTRO_VIDEO";

		public override object Create(ActorInitializer init) { return new IntroVideo(this); }
	}

	public class IntroVideo : IPostWorldLoaded
	{
		static bool played;
		readonly IntroVideoInfo info;

		public IntroVideo(IntroVideoInfo info)
		{
			this.info = info;
		}

		void IPostWorldLoaded.PostWorldLoaded(World world, WorldRenderer wr)
		{
			if (played || world.Type != WorldType.Shellmap)
				return;

			played = true;

			// The intro is optional: a checkout without the video still boots straight to the menu
			if (!Game.ModData.DefaultFileSystem.Exists(info.Video))
				return;

			// Wait for the main menu to finish setting itself up so the video is drawn on top
			Game.RunAfterTick(() => Ui.OpenWindow(info.Widget, new WidgetArgs { { "video", info.Video } }));
		}
	}
}
