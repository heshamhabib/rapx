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
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Project X replacement for WithRangeCircle / RenderJammerCircle: shows a fixed range as a translucent glass dome",
		"(or only its ground footprint) when selected or placing a structure of the same type.")]
	public class PxWithRangeDomeInfo : ConditionalTraitInfo, IPlaceBuildingDecorationInfo
	{
		[Desc("Domes of the same type are all shown while placing a building of that type.")]
		public readonly string Type = null;

		[FieldLoader.Require]
		[Desc("Radius of the dome.")]
		public readonly WDist Range = WDist.Zero;

		[Desc("Hologram colour of the dome.")]
		public readonly Color Color = Color.FromArgb(70, 210, 255);

		[Desc("Dome height as a fraction of the range (1 = true hemisphere).")]
		public readonly float DomeHeight = 0.45f;

		[Desc("Overall opacity multiplier.")]
		public readonly float Opacity = 1f;

		[Desc("Draw only the ground footprint and rim, no glass shell (for inner zones nested in a bigger dome).")]
		public readonly bool Lite = false;

		[Desc("Player relationships which will be able to see the dome.")]
		public readonly PlayerRelationship ValidRelationships = PlayerRelationship.Ally;

		public PxRangeDomeStyle Style => new(Color, DomeHeight, Opacity, Lite);

		public IEnumerable<IRenderable> RenderAnnotations(WorldRenderer wr, World w, ActorInfo ai, WPos centerPosition)
		{
			if (!EnabledByDefault)
				yield break;

			yield return new PxRangeDomeRenderable(centerPosition, Range, Style);

			foreach (var a in w.ActorsWithTrait<PxWithRangeDome>())
				if (a.Trait.Info.Type == Type)
					foreach (var r in a.Trait.RangeRenderables(a.Actor, true))
						yield return r;
		}

		public override object Create(ActorInitializer init) { return new PxWithRangeDome(this); }
	}

	public class PxWithRangeDome : ConditionalTrait<PxWithRangeDomeInfo>, IRenderAnnotationsWhenSelected
	{
		public PxWithRangeDome(PxWithRangeDomeInfo info)
			: base(info) { }

		public IEnumerable<IRenderable> RangeRenderables(Actor self, bool lite)
		{
			if (IsTraitDisabled || Info.Range == WDist.Zero || !self.IsInWorld)
				yield break;

			var p = self.World.RenderPlayer;
			if (p != null && !Info.ValidRelationships.HasRelationship(self.Owner.RelationshipWith(p)) && !(p.Spectating && !p.NonCombatant))
				yield break;

			yield return new PxRangeDomeRenderable(self.CenterPosition, Info.Range, lite ? Info.Style.AsLite() : Info.Style);
		}

		IEnumerable<IRenderable> IRenderAnnotationsWhenSelected.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			return RangeRenderables(self, false);
		}

		bool IRenderAnnotationsWhenSelected.SpatiallyPartitionable => false;
	}
}
