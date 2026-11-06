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
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	public enum PxRangeShape { Dome, Hex }

	[Desc("Project X replacement for RenderRangeCircle: shows weapon coverage when selected or placed, either as a",
		"translucent glass dome (air defence) or as a hologram hexagon grid on the ground (land defence).")]
	public class PxRenderRangeDomeInfo : TraitInfo, IPlaceBuildingDecorationInfo, IRulesetLoaded
	{
		[Desc("Also show every allied dome of this kind while this modifier is held (Alt: see the gaps in coverage).")]
		public readonly Modifiers OverlayModifier = Modifiers.Alt;

		[Desc("Domes of the same type are all shown while placing a building of that type.")]
		public readonly string RangeCircleType = null;

		[Desc("Range to draw if no armaments are available.")]
		public readonly WDist FallbackRange = WDist.Zero;

		[Desc("Which range to show. Valid values are `Maximum`, and `Minimum`.")]
		public readonly RangeCircleMode RangeCircleMode = RangeCircleMode.Maximum;

		[Desc("Hologram colour of the dome.")]
		public readonly Color Color = Color.FromArgb(70, 210, 255);

		[Desc("Dome height as a fraction of the range (1 = true hemisphere).")]
		public readonly float DomeHeight = 0.45f;

		[Desc("Overall opacity multiplier.")]
		public readonly float Opacity = 1f;

		[Desc("`Dome` = glass hemisphere, `Hex` = hexagon grid on the ground.")]
		public readonly PxRangeShape Shape = PxRangeShape.Dome;

		[Desc("Hex shape only: distance from a hexagon's centre to its corners.")]
		public readonly WDist HexSize = new(640);

		[Desc("Hex shape only: camera elevation in degrees the hexes are drawn for (see PxRenderBuildRadius).")]
		public readonly float CameraElevation = 50f;

		Lazy<WDist> range;

		public PxRangeDomeStyle Style => new(Color, DomeHeight, Opacity, RangeCircleMode == RangeCircleMode.Minimum);

		public IEnumerable<IRenderable> RenderAnnotations(WorldRenderer wr, World w, ActorInfo ai, WPos centerPosition)
		{
			if (range == null || range.Value == WDist.Zero)
				return SpriteRenderable.None;

			var others = w.ActorsWithTrait<PxRenderRangeDome>()
				.Where(a => a.Trait.Info.RangeCircleType == RangeCircleType)
				.SelectMany(a => a.Trait.RangeRenderables(true));

			return others.Append(RangeRenderable(centerPosition, range.Value, false));
		}

		public IRenderable RangeRenderable(WPos centre, WDist range, bool lite)
		{
			if (Shape == PxRangeShape.Hex)
				return new PxHexGridRenderable(centre, range, HexSize, Color, lite ? Opacity * 0.7f : Opacity, lite,
					MathF.Sin(CameraElevation * MathF.PI / 180));

			return new PxRangeDomeRenderable(centre, range, lite ? Style.AsLite() : Style);
		}

		public override object Create(ActorInitializer init) { return new PxRenderRangeDome(init.Self, this); }

		public void RulesetLoaded(Ruleset rules, ActorInfo ai)
		{
			// ArmamentInfo.ModifiedRange is set by RulesetLoaded, so defer the lookup.
			range = Exts.Lazy(() =>
			{
				// Air defence (PxInterceptor) covers its own range, often beyond its anti-aircraft guns
				var interceptors = ai.TraitInfos<PxInterceptorInfo>().Where(i => i.EnabledByDefault).Select(i => i.Range);
				var armaments = ai.TraitInfos<ArmamentInfo>().Where(a => a.EnabledByDefault).Select(a => a.ModifiedRange);
				var ranges = interceptors.Concat(armaments).ToList();
				return ranges.Count > 0 ? ranges.Max() : FallbackRange;
			});
		}
	}

	public class PxRenderRangeDome : IRenderAnnotationsWhenSelected, IRenderAnnotations
	{
		public readonly PxRenderRangeDomeInfo Info;
		readonly Actor self;
		readonly AttackBase attack;
		readonly PxInterceptor[] interceptors;

		public PxRenderRangeDome(Actor self, PxRenderRangeDomeInfo info)
		{
			Info = info;
			this.self = self;
			attack = self.TraitOrDefault<AttackBase>();
			interceptors = self.TraitsImplementing<PxInterceptor>().ToArray();
		}

		WDist Range()
		{
			var range = attack == null ? WDist.Zero
				: Info.RangeCircleMode == RangeCircleMode.Minimum ? attack.GetMinimumRange() : attack.GetMaximumRange();
			if (Info.RangeCircleMode == RangeCircleMode.Maximum)
				foreach (var i in interceptors)
					if (!i.IsTraitDisabled && i.EffectiveRange > range)
						range = i.EffectiveRange;

			return range == WDist.Zero ? Info.FallbackRange : range;
		}

		public IEnumerable<IRenderable> RangeRenderables(bool lite)
		{
			if (!self.IsInWorld || !self.Owner.IsAlliedWith(self.World.RenderPlayer))
				yield break;

			var range = Range();
			if (range == WDist.Zero)
				yield break;

			yield return Info.RangeRenderable(self.CenterPosition, range, lite);
		}

		IEnumerable<IRenderable> IRenderAnnotationsWhenSelected.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			return RangeRenderables(false);
		}

		bool IRenderAnnotationsWhenSelected.SpatiallyPartitionable => false;

		IEnumerable<IRenderable> IRenderAnnotations.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			// Held modifier: every allied dome (selected ones draw through RenderAnnotationsWhenSelected)
			if (!Game.GetModifierKeys().HasModifier(Info.OverlayModifier) || self.World.Selection.Contains(self))
				return SpriteRenderable.None;

			return RangeRenderables(true);
		}

		bool IRenderAnnotations.SpatiallyPartitionable => false;
	}
}
