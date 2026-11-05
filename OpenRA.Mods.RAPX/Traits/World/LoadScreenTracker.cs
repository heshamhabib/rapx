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
using OpenRA.Mods.RAPX.LoadScreens;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World | SystemActors.EditorWorld)]
	[Desc("Tells FullscreenImageLoadScreen which kind of world is loading and when it has finished,",
		"so it can pick the right title and learn how long each kind of load takes.")]
	public class LoadScreenTrackerInfo : TraitInfo
	{
		public override object Create(ActorInitializer init)
		{
			FullscreenImageLoadScreen.LastWorldType = init.World.Type;
			return new LoadScreenTracker();
		}
	}

	public sealed class LoadScreenTracker : IPostWorldLoaded
	{
		void IPostWorldLoaded.PostWorldLoaded(World w, WorldRenderer wr)
		{
			FullscreenImageLoadScreen.WorldLoaded();
		}
	}
}
