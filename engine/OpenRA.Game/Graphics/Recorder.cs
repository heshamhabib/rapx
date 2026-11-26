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

namespace OpenRA.Graphics
{
	/// <summary>
	/// RAPX: set while a capture tool is recording the world for video. Recordings want the world without the HUD,
	/// so render paths that trim work hidden behind opaque HUD panels (<see cref="WorldRenderer.PostProcessScissor"/>)
	/// must not trim while this is set. Nothing in the tree records yet; a recorder sets this when one lands.
	/// </summary>
	public static class Recorder
	{
		public static bool Active;
	}
}
