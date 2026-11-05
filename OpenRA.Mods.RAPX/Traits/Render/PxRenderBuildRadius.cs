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
	[Desc("Project X replacement for the BaseProvider range circle: shows the build radius as a hologram hexagon grid",
		"on the ground when selected (and, via PxShowBuildRadiusWhilePlacing, while placing a building).",
		"Like the stock circle it only shows when the lobby's build radius option is on. Hide the stock circle by giving",
		"BaseProvider transparent Circle*Color values.")]
	public class PxRenderBuildRadiusInfo : TraitInfo, Requires<BaseProviderInfo>
	{
		[Desc("Hologram colour while the base provider is ready.")]
		public readonly Color Color = Color.FromArgb(255, 196, 70);

		[Desc("Hologram colour while it is not ready (e.g. being captured).")]
		public readonly Color BlockedColor = Color.FromArgb(255, 70, 60);

		[Desc("Distance from a hexagon's centre to its corners.")]
		public readonly WDist HexSize = new(896);

		[Desc("Camera elevation in degrees that the hexes are drawn for, so they lie on the ground like the HD art",
			"(artsrc/units/render_sprites.py ELEVATION). 90 = straight top-down.")]
		public readonly float CameraElevation = 50f;

		[Desc("Overall opacity multiplier.")]
		public readonly float Opacity = 1f;

		public override object Create(ActorInitializer init) { return new PxRenderBuildRadius(init.Self, this); }
	}

	public class PxRenderBuildRadius : IRenderAnnotationsWhenSelected
	{
		readonly PxRenderBuildRadiusInfo info;
		readonly Actor self;
		readonly BaseProvider baseProvider;
		readonly bool buildRadiusEnabled;
		readonly bool allyBuildEnabled;

		public PxRenderBuildRadius(Actor self, PxRenderBuildRadiusInfo info)
		{
			this.info = info;
			this.self = self;
			baseProvider = self.Trait<BaseProvider>();
			var mapBuildRadius = self.World.WorldActor.TraitOrDefault<MapBuildRadius>();
			buildRadiusEnabled = mapBuildRadius != null && mapBuildRadius.BuildRadiusEnabled;
			allyBuildEnabled = mapBuildRadius != null && mapBuildRadius.AllyBuildRadiusEnabled;
		}

		public IEnumerable<IRenderable> RangeRenderables(bool lite)
		{
			// Same visibility rule as BaseProvider's own circle
			if (!buildRadiusEnabled || !self.IsInWorld || baseProvider.IsTraitDisabled)
				yield break;

			var renderPlayer = self.World.RenderPlayer;
			if (self.Owner != renderPlayer && !(allyBuildEnabled && self.Owner.IsAlliedWith(renderPlayer)))
				yield break;

			var range = baseProvider.Info.Range;
			if (range == WDist.Zero)
				yield break;

			var color = baseProvider.Ready() ? info.Color : info.BlockedColor;
			yield return new PxHexGridRenderable(self.CenterPosition, range, info.HexSize, color, lite ? info.Opacity * 0.7f : info.Opacity, lite,
				MathF.Sin(info.CameraElevation * MathF.PI / 180));
		}

		IEnumerable<IRenderable> IRenderAnnotationsWhenSelected.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			return RangeRenderables(false);
		}

		bool IRenderAnnotationsWhenSelected.SpatiallyPartitionable => false;
	}

	[Desc("While this building is being placed, shows the build radius of every PxRenderBuildRadius actor.")]
	public class PxShowBuildRadiusWhilePlacingInfo : TraitInfo<PxShowBuildRadiusWhilePlacing>, IPlaceBuildingDecorationInfo
	{
		public IEnumerable<IRenderable> RenderAnnotations(WorldRenderer wr, World w, ActorInfo ai, WPos centerPosition)
		{
			return w.ActorsWithTrait<PxRenderBuildRadius>().SelectMany(a => a.Trait.RangeRenderables(true));
		}
	}

	public class PxShowBuildRadiusWhilePlacing { }
}
