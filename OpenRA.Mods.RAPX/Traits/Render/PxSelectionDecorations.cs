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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.RAPX.Graphics;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Selection decorations that draw the Project X styled health and status bars.")]
	public class PxSelectionDecorationsInfo : SelectionDecorationsInfo
	{
		[Desc("Height of the health bar in screen pixels, including its frame.")]
		public readonly int HealthBarHeight = 8;

		[Desc("Height of each extra (production, charge, ...) bar in screen pixels, including its frame.")]
		public readonly int ExtraBarHeight = 5;

		[Desc("Approximate width of one health bar segment in screen pixels. 0 disables segments.")]
		public readonly int SegmentWidth = 7;

		[Desc("Horizontal slant of the bar ends in screen pixels.")]
		public readonly int Skew = 4;

		public override object Create(ActorInitializer init) { return new PxSelectionDecorations(init.Self, this); }
	}

	public class PxSelectionDecorations : SelectionDecorations
	{
		readonly PxSelectionDecorationsInfo info;
		readonly Interactable interactable;

		public PxSelectionDecorations(Actor self, PxSelectionDecorationsInfo info)
			: base(self, info)
		{
			this.info = info;
			interactable = self.Trait<Interactable>();
		}

		protected override IEnumerable<IRenderable> RenderSelectionBars(Actor self, WorldRenderer wr, bool displayHealth, bool displayExtra)
		{
			// Project X shows bars only on selected actors, ignoring hover and the "Status Bars" setting.
			if (interactable is not Selectable || !self.World.Selection.Contains(self))
				yield break;

			displayHealth = displayExtra = true;

			var bounds = interactable.DecorationBounds(self, wr);
			yield return new PxSelectionBarsRenderable(self.CenterPosition, self, bounds, info, displayHealth, displayExtra);
		}
	}
}
