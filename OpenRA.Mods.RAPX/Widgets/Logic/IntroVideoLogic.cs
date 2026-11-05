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
using OpenRA.Video;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	public class IntroVideoLogic : ChromeLogic
	{
		[ObjectCreator.UseCtor]
		public IntroVideoLogic(Widget widget, string video)
		{
			var player = widget.Get<PxIntroPlayerWidget>("PLAYER");
			var musicWasPlaying = Game.Sound.MusicPlaying;

			void Close()
			{
				Ui.CloseWindow();
				if (musicWasPlaying)
					Game.Sound.PlayMusic();
			}

			IVideo loaded = null;
			try
			{
				using (var stream = Game.ModData.DefaultFileSystem.Open(video))
					loaded = VideoLoader.GetVideo(stream, true, Game.ModData.VideoLoaders);
			}
			catch (Exception e)
			{
				Log.Write("debug", $"Failed to load intro video {video}: {e.Message}");
			}

			if (loaded == null)
			{
				Game.RunAfterTick(Close);
				return;
			}

			Game.Sound.PauseMusic();
			player.Play(loaded, Close);
		}
	}
}
