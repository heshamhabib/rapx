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

using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Turns on the music player's Shuffle option whenever a game starts, so MusicPlaylist",
		"plays the soundtrack in a fresh random order each match instead of the music.yaml order.",
		"The player can still untick Shuffle in the music player for the rest of that match.")]
	public class PxShuffleMusicInfo : TraitInfo
	{
		public override object Create(ActorInitializer init)
		{
			// MusicPlaylist only reads this when picking the next track, so setting it here is early enough.
			// Not saved to settings.yaml: it is re-applied every match anyway.
			Game.Settings.Sound.Shuffle = true;
			return new PxShuffleMusic();
		}
	}

	public sealed class PxShuffleMusic { }
}
