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
using System.Reflection;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Scales an aircraft's sprites with its height: full size at cruise altitude, LandedScale on the ground, eased",
		"in between (reads as perspective: high = closer to the camera). Lets big jets park on airfields made for small",
		"ones. List it before WithShadow so the shadow follows.")]
	public class PxAltitudeScaleInfo : TraitInfo, Requires<AircraftInfo>
	{
		[Desc("Sprite scale when landed, relative to the flying size.")]
		public readonly float LandedScale = 0.6f;

		[Desc("Height at which the full size is reached (default: the aircraft's CruiseAltitude).")]
		public readonly WDist FullScaleAltitude = WDist.Zero;

		public override object Create(ActorInitializer init) { return new PxAltitudeScale(init.Self, this); }
	}

	public class PxAltitudeScale : IRenderModifier
	{
		static readonly FieldInfo SpriteField = typeof(SpriteRenderable).GetField("sprite", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo PosField = typeof(SpriteRenderable).GetField("pos", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo ScaleField = typeof(SpriteRenderable).GetField("scale", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo RotationField = typeof(SpriteRenderable).GetField("rotation", BindingFlags.NonPublic | BindingFlags.Instance);

		readonly PxAltitudeScaleInfo info;
		readonly int fullAltitude;

		public PxAltitudeScale(Actor self, PxAltitudeScaleInfo info)
		{
			this.info = info;
			var aircraft = self.Info.TraitInfo<AircraftInfo>();
			fullAltitude = Math.Max(1, info.FullScaleAltitude.Length > 0 ? info.FullScaleAltitude.Length : aircraft.CruiseAltitude.Length);
		}

		public float LandedScale => info.LandedScale;

		public float Factor(Actor self)
		{
			var height = self.World.Map.DistanceAboveTerrain(self.CenterPosition).Length;
			var t = Math.Clamp((float)height / fullAltitude, 0f, 1f);
			t = t * t * (3 - 2 * t); // smoothstep: settles gently onto the ground and into cruise
			return info.LandedScale + (1 - info.LandedScale) * t;
		}

		IEnumerable<IRenderable> IRenderModifier.ModifyRender(Actor self, WorldRenderer wr, IEnumerable<IRenderable> r)
		{
			var k = Factor(self);
			if (k > 0.999f)
				return r;

			return r.Select(x => Scale(x, k));
		}

		/// <summary>Scales a sprite (size and offset) by k around its position; other renderables are kept as they are.</summary>
		public static IRenderable Scale(IRenderable r, float k, int zOffset = 0)
		{
			if (r is not SpriteRenderable s)
				return r;

			var sprite = (Sprite)SpriteField.GetValue(s);
			var pos = (WPos)PosField.GetValue(s);
			var scale = (float)ScaleField.GetValue(s);
			var rotation = (WAngle)RotationField.GetValue(s);
			var offset = new WVec((int)(s.Offset.X * k), (int)(s.Offset.Y * k), (int)(s.Offset.Z * k));
			return new SpriteRenderable(sprite, pos, offset, s.ZOffset + zOffset, s.Palette, scale * k, s.Alpha, s.Tint,
				s.TintModifiers, s.IsDecoration, rotation);
		}

		IEnumerable<Rectangle> IRenderModifier.ModifyScreenBounds(Actor self, WorldRenderer wr, IEnumerable<Rectangle> r)
		{
			return r;
		}
	}
}
