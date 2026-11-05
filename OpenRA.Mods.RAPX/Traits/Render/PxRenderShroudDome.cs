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
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Project X replacement for RenderShroudCircle: shows the CreatesShroud area as a translucent glass dome when selected or placed.")]
	public class PxRenderShroudDomeInfo : ConditionalTraitInfo, IPlaceBuildingDecorationInfo
	{
		[Desc("Hologram colour of the dome.")]
		public readonly Color Color = Color.FromArgb(60, 230, 180);

		[Desc("Dome height as a fraction of the range (1 = true hemisphere).")]
		public readonly float DomeHeight = 0.6f;

		[Desc("Overall opacity multiplier.")]
		public readonly float Opacity = 1f;

		public PxRangeDomeStyle Style => new(Color, DomeHeight, Opacity, false);

		public IEnumerable<IRenderable> RenderAnnotations(WorldRenderer wr, World w, ActorInfo ai, WPos centerPosition)
		{
			if (!EnabledByDefault)
				return Enumerable.Empty<IRenderable>();

			var range = ai.TraitInfos<CreatesShroudInfo>()
				.Where(csi => csi.EnabledByDefault)
				.Select(csi => csi.Range)
				.DefaultIfEmpty(WDist.Zero)
				.Max();

			var others = w.ActorsWithTrait<PxRenderShroudDome>()
				.SelectMany(a => a.Trait.RangeRenderables(a.Actor, true));

			if (range == WDist.Zero)
				return others;

			return others.Append(new PxRangeDomeRenderable(centerPosition, range, Style));
		}

		public override object Create(ActorInitializer init) { return new PxRenderShroudDome(this); }
	}

	public class PxRenderShroudDome : ConditionalTrait<PxRenderShroudDomeInfo>, IRenderAnnotationsWhenSelected
	{
		WDist range;

		public PxRenderShroudDome(PxRenderShroudDomeInfo info)
			: base(info) { }

		protected override void Created(Actor self)
		{
			range = self.TraitsImplementing<CreatesShroud>()
				.Select(cs => cs.Info.Range)
				.DefaultIfEmpty(WDist.Zero)
				.Max();

			base.Created(self);
		}

		public IEnumerable<IRenderable> RangeRenderables(Actor self, bool lite)
		{
			if (IsTraitDisabled || range == WDist.Zero || !self.IsInWorld || !self.Owner.IsAlliedWith(self.World.RenderPlayer))
				yield break;

			yield return new PxRangeDomeRenderable(self.CenterPosition, range, lite ? Info.Style.AsLite() : Info.Style);
		}

		IEnumerable<IRenderable> IRenderAnnotationsWhenSelected.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			return RangeRenderables(self, false);
		}

		bool IRenderAnnotationsWhenSelected.SpatiallyPartitionable => false;
	}
}
