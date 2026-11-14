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

	public class PxRenderRangeDome : IRenderAnnotationsWhenSelected, IRenderAnnotations, INotifyCreated
	{
		public readonly PxRenderRangeDomeInfo Info;
		readonly Actor self;
		AttackBase attack;
		PxInterceptor[] interceptors = Array.Empty<PxInterceptor>();

		public PxRenderRangeDome(Actor self, PxRenderRangeDomeInfo info)
		{
			Info = info;
			this.self = self;
		}

		void INotifyCreated.Created(Actor self)
		{
			// Look the weapons up once every trait exists: inherited from ^Defense, this trait is constructed
			// before the actor's AttackBase and PxInterceptors, so a constructor lookup finds nothing
			attack = self.TraitOrDefault<AttackBase>();
			interceptors = self.TraitsImplementing<PxInterceptor>().ToArray();
		}

		WDist Range(out bool offline)
		{
			// AttackBase.GetMaximumRange skips paused armaments (low power, still building, a Prism Tower feeding its
			// neighbour), which made the dome vanish when selected, so read them directly: paused still counts as
			// covered. Weapons and interceptors switched off entirely keep showing as a footprint only.
			var range = WDist.Zero;
			var offlineRange = WDist.Zero;
			if (Info.RangeCircleMode == RangeCircleMode.Minimum)
			{
				if (attack != null)
				{
					var min = WDist.MaxValue;
					foreach (var a in attack.Armaments)
						if (!a.IsTraitDisabled && a.Weapon.MinRange < min)
							min = a.Weapon.MinRange;

					if (min != WDist.MaxValue)
						range = min;
				}
			}
			else
			{
				if (attack != null)
				{
					foreach (var a in attack.Armaments)
					{
						var r = a.MaxRange();
						var active = !attack.IsTraitDisabled && !a.IsTraitDisabled;
						if (active && r > range)
							range = r;
						else if (!active && r > offlineRange)
							offlineRange = r;
					}
				}

				foreach (var i in interceptors)
				{
					if (!i.IsTraitDisabled && i.EffectiveRange > range)
						range = i.EffectiveRange;
					else if (i.IsTraitDisabled && i.EffectiveRange > offlineRange)
						offlineRange = i.EffectiveRange;
				}
			}

			offline = range == WDist.Zero && offlineRange > WDist.Zero;
			if (offline)
				return offlineRange;

			return range == WDist.Zero ? Info.FallbackRange : range;
		}

		public IEnumerable<IRenderable> RangeRenderables(bool lite)
		{
			if (!self.IsInWorld || !self.Owner.IsAlliedWith(self.World.RenderPlayer))
				yield break;

			var range = Range(out var offline);
			if (range == WDist.Zero)
				yield break;

			yield return Info.RangeRenderable(self.CenterPosition, range, lite || offline);
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
