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
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Graphics
{
	/// <summary>
	/// An RGBA sprite drawn as horizontal bands that are shifted sideways by a sway function of their height above
	/// a pivot row (the tree's trunk base): the base stays put and the top bends. Cosmetic only.
	/// </summary>
	public class PxSwayRenderable : IRenderable, IFinalizedRenderable
	{
		const int Bands = 14;
		static readonly Dictionary<Sprite, Sprite[]> BandCache = new();

		readonly Sprite sprite;
		readonly float scale;
		readonly float3 tint;
		readonly float alpha;
		readonly float pivot;
		readonly float shift;

		// pivot: row of the trunk base as a fraction of the sprite height from its top;
		// shift: sideways shift of the sprite's top row, in screen pixels
		public PxSwayRenderable(Sprite sprite, WPos pos, WVec offset, int zOffset, float scale, float3 tint, float alpha,
			float pivot, float shift)
		{
			this.sprite = sprite;
			Pos = pos + offset;
			ZOffset = zOffset;
			this.scale = scale;
			this.tint = tint;
			this.alpha = alpha;
			this.pivot = pivot;
			this.shift = shift;
		}

		public WPos Pos { get; }
		public int ZOffset { get; }
		public bool IsDecoration => false;

		public IRenderable WithZOffset(int newOffset) { return new PxSwayRenderable(sprite, Pos, WVec.Zero, newOffset, scale, tint, alpha, pivot, shift); }
		public IRenderable OffsetBy(in WVec vec) { return new PxSwayRenderable(sprite, Pos + vec, WVec.Zero, ZOffset, scale, tint, alpha, pivot, shift); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		static Sprite[] BandsFor(Sprite s)
		{
			if (BandCache.TryGetValue(s, out var bands))
				return bands;

			bands = new Sprite[Bands];
			for (var i = 0; i < Bands; i++)
			{
				var y0 = s.Bounds.Y + s.Bounds.Height * i / Bands;
				var y1 = s.Bounds.Y + s.Bounds.Height * (i + 1) / Bands;
				bands[i] = new Sprite(s.Sheet, new Rectangle(s.Bounds.X, y0, s.Bounds.Width, y1 - y0), TextureChannel.RGBA);
			}

			BandCache[s] = bands;
			return bands;
		}

		// Sideways shift of a row at fraction v (0 = top) of the sprite: grows with height above the pivot
		float ShiftAt(float v)
		{
			if (v >= pivot)
				return 0;

			var u = 1 - v / pivot;
			return shift * u * u;
		}

		public void Render(WorldRenderer wr)
		{
			// Same placement as SpriteRenderable: the sprite is centred on its position
			var half = 0.5f * scale * sprite.Size;
			var location = wr.Screen3DPxPosition(Pos) - new float3((int)half.X, (int)half.Y, half.Z);
			var tl = location + scale * sprite.Offset;
			var size = scale * sprite.Size;

			var t = alpha * tint;
			if (wr.TerrainLighting != null)
				t *= wr.TerrainLighting.TintAt(Pos);

			var bands = BandsFor(sprite);
			var wsr = Game.Renderer.WorldRgbaSpriteRenderer;
			for (var i = 0; i < bands.Length; i++)
			{
				var v0 = (float)i / bands.Length;
				var v1 = (float)(i + 1) / bands.Length;
				var y0 = tl.Y + size.Y * v0;
				var y1 = tl.Y + size.Y * v1;
				var s0 = ShiftAt(v0);
				var s1 = ShiftAt(v1);
				wsr.DrawSprite(bands[i],
					new float3(tl.X + s0, y0, tl.Z), new float3(tl.X + size.X + s0, y0, tl.Z),
					new float3(tl.X + size.X + s1, y1, tl.Z), new float3(tl.X + s1, y1, tl.Z), t, alpha);
			}
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
