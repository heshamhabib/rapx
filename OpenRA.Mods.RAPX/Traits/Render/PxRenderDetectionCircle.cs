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
using System.Collections.Generic;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Project X replacement for RenderDetectionCircle: shows the DetectCloaked range (e.g. a submarine's sonar)",
		"as a see-through hologram hexagon grid on the ground with a bold ring at the exact range, when selected.")]
	public class PxRenderDetectionCircleInfo : TraitInfo, Requires<DetectCloakedInfo>
	{
		[Desc("Hologram colour.")]
		public readonly Color Color = Color.FromArgb(60, 230, 140);

		[Desc("Distance from a hexagon's centre to its corners.")]
		public readonly WDist HexSize = new(640);

		[Desc("Overall opacity multiplier.")]
		public readonly float Opacity = 1f;

		[Desc("Opacity of the hex cells and their lines only (lower = more see-through).")]
		public readonly float CellOpacity = 0.45f;

		[Desc("Thickness multiplier of the ring at the exact range.")]
		public readonly float RimWidth = 2.2f;

		[Desc("Camera elevation in degrees the hexes are drawn for (see PxRenderBuildRadius).")]
		public readonly float CameraElevation = 50f;

		[Desc("Draw without the rolling pulse and twinkling cells.")]
		public readonly bool Lite = false;

		public override object Create(ActorInitializer init) { return new PxRenderDetectionCircle(init.Self, this); }
	}

	public class PxRenderDetectionCircle : IRenderAnnotationsWhenSelected, INotifyCreated
	{
		readonly PxRenderDetectionCircleInfo info;
		DetectCloaked[] detectCloaked = Array.Empty<DetectCloaked>();

		public PxRenderDetectionCircle(Actor self, PxRenderDetectionCircleInfo info)
		{
			this.info = info;
		}

		// Traits listed after this one don't exist yet in the constructor
		void INotifyCreated.Created(Actor self)
		{
			detectCloaked = self.TraitsImplementing<DetectCloaked>().ToArray();
		}

		IEnumerable<IRenderable> IRenderAnnotationsWhenSelected.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			if (!self.IsInWorld || !self.Owner.IsAlliedWith(self.World.RenderPlayer))
				yield break;

			var range = detectCloaked.Where(d => !d.IsTraitDisabled).Select(d => d.Range).Append(WDist.Zero).Max();
			if (range == WDist.Zero)
				yield break;

			var tilt = MathF.Sin(info.CameraElevation * MathF.PI / 180);
			yield return new PxHexGridRenderable(self.CenterPosition, range, info.HexSize, info.Color, info.Opacity, info.Lite, tilt,
				info.CellOpacity, info.RimWidth);
		}

		bool IRenderAnnotationsWhenSelected.SpatiallyPartitionable => false;
	}
}
