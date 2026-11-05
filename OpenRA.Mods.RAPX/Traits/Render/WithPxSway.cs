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
using System.Reflection;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Makes the actor's HD (true colour) sprites sway in the wind like a tree: the trunk base stays put and the",
		"crown bends. Every actor has its own rhythm, and slow gusts roll across the map so forests move in waves.",
		"Purely cosmetic (local clock).")]
	public class WithPxSwayInfo : TraitInfo
	{
		[Desc("Row of the trunk base as a fraction of the sprite height from its top (rows below it never move).")]
		public readonly float Pivot = 0.8f;

		[Desc("Sideways movement of the top of the sprite, as a fraction of the sprite height.")]
		public readonly float Amplitude = 0.035f;

		[Desc("Seconds per sway.")]
		public readonly float Period = 3.4f;

		[Desc("Map cells between gust fronts; gusts move with GustSpeed cells per second.")]
		public readonly float GustLength = 14f;
		public readonly float GustSpeed = 2.5f;

		public override object Create(ActorInitializer init) { return new WithPxSway(this); }
	}

	public class WithPxSway : IRenderModifier
	{
		// SpriteRenderable keeps its sprite and scale private
		static readonly FieldInfo SpriteField = typeof(SpriteRenderable).GetField("sprite", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo ScaleField = typeof(SpriteRenderable).GetField("scale", BindingFlags.NonPublic | BindingFlags.Instance);

		readonly WithPxSwayInfo info;
		float phase;
		float gustPos;
		bool placed;
		PxWeatherManager weather;

		public WithPxSway(WithPxSwayInfo info)
		{
			this.info = info;
		}

		// The actor's position is only known once it is in the world, so the per-tree rhythm is set on first render
		void Place(Actor self)
		{
			placed = true;
			weather = self.World.WorldActor.TraitOrDefault<PxWeatherManager>();
			if (weather != null && !weather.Enabled)
				weather = null;

			// Cheap position hash: neighbouring trees get unrelated phases
			var c = self.World.Map.CellContaining(self.CenterPosition);
			var h = (uint)(c.X * 73856093) ^ (uint)(c.Y * 19349663);
			h ^= h >> 13;
			h *= 0x5bd1e995;
			phase = (h & 0xffff) / 65535f * MathF.PI * 2;
			gustPos = (c.X + c.Y) * 0.7f;
		}

		IEnumerable<IRenderable> IRenderModifier.ModifyRender(Actor self, WorldRenderer wr, IEnumerable<IRenderable> r)
		{
			if (!placed)
				Place(self);

			var t = Game.RunTime / 1000f;
			var w = MathF.PI * 2 / info.Period;

			// Gust envelope travelling diagonally across the map, plus this tree's own sway
			var gust = 0.55f + 0.45f * MathF.Sin((t * info.GustSpeed - gustPos) * MathF.PI * 2 / info.GustLength);
			var sway = gust * (0.75f * MathF.Sin(t * w + phase) + 0.25f * MathF.Sin(t * w * 2.3f + phase * 1.7f));

			// Weather wind: livelier sway plus a steady lean downwind that grows in the gusts
			if (weather != null)
			{
				var f = weather.Frame();
				var strength = Math.Max(0, f.Wind - 0.15f);
				sway = sway * (1 + 1.8f * strength) + f.WindDir.X * strength * (1.2f + 0.8f * gust);
			}

			foreach (var renderable in r)
			{
				if (renderable is SpriteRenderable sr && SpriteField?.GetValue(sr) is Sprite sprite && sprite.Channel == TextureChannel.RGBA)
				{
					var scale = (float)ScaleField.GetValue(sr);
					var height = scale * sprite.Size.Y;
					yield return new PxSwayRenderable(sprite, sr.Pos, WVec.Zero, sr.ZOffset, scale, sr.Tint, sr.Alpha,
						info.Pivot, sway * info.Amplitude * height);
				}
				else
					yield return renderable;
			}
		}

		IEnumerable<Rectangle> IRenderModifier.ModifyScreenBounds(Actor self, WorldRenderer wr, IEnumerable<Rectangle> r)
		{
			return r;
		}
	}
}
