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
using OpenRA.Primitives;

namespace OpenRA.Graphics
{
	public class SpriteRenderable : IPalettedRenderable, IModifyableRenderable, IFinalizedRenderable
	{
		public static readonly IEnumerable<IRenderable> None = Array.Empty<IRenderable>();

		readonly Sprite sprite;
		readonly WPos pos;
		readonly float scale;
		readonly WAngle rotation = WAngle.Zero;

		public SpriteRenderable(Sprite sprite, WPos pos, WVec offset, int zOffset, PaletteReference palette, float scale, float alpha,
			float3 tint, TintModifiers tintModifiers, bool isDecoration, WAngle rotation)
		{
			this.sprite = sprite;
			this.pos = pos;
			Offset = offset;
			ZOffset = zOffset;
			Palette = palette;
			this.scale = scale;
			this.rotation = rotation;
			Tint = tint;
			IsDecoration = isDecoration;
			TintModifiers = tintModifiers;
			Alpha = alpha;

			// PERF: Remove useless palette assignments for RGBA sprites
			// HACK: This is working around the fact that palettes are defined on traits rather than sequences
			// and can be removed once this has been fixed
			if (sprite.Channel == TextureChannel.RGBA && !(palette?.HasColorShift ?? false))
				Palette = null;
		}

		public SpriteRenderable(Sprite sprite, WPos pos, WVec offset, int zOffset, PaletteReference palette, float scale, float alpha,
			float3 tint, TintModifiers tintModifiers, bool isDecoration)
			: this(sprite, pos, offset, zOffset, palette, scale, alpha, tint, tintModifiers, isDecoration, WAngle.Zero) { }

		public WPos Pos => pos + Offset;
		public WVec Offset { get; }
		public PaletteReference Palette { get; }
		public int ZOffset { get; }
		public bool IsDecoration { get; }

		public float Alpha { get; }
		public float3 Tint { get; }
		public TintModifiers TintModifiers { get; }

		public IPalettedRenderable WithPalette(PaletteReference newPalette)
		{
			return new SpriteRenderable(sprite, pos, Offset, ZOffset, newPalette, scale, Alpha, Tint, TintModifiers, IsDecoration, rotation);
		}

		public IRenderable WithZOffset(int newOffset)
		{
			return new SpriteRenderable(sprite, pos, Offset, newOffset, Palette, scale, Alpha, Tint, TintModifiers, IsDecoration, rotation);
		}

		public IRenderable OffsetBy(in WVec vec)
		{
			return new SpriteRenderable(sprite, pos + vec, Offset, ZOffset, Palette, scale, Alpha, Tint, TintModifiers, IsDecoration, rotation);
		}

		public IRenderable AsDecoration()
		{
			return new SpriteRenderable(sprite, pos, Offset, ZOffset, Palette, scale, Alpha, Tint, TintModifiers, true, rotation);
		}

		public IModifyableRenderable WithAlpha(float newAlpha)
		{
			return new SpriteRenderable(sprite, pos, Offset, ZOffset, Palette, scale, newAlpha, Tint, TintModifiers, IsDecoration, rotation);
		}

		public IModifyableRenderable WithTint(in float3 newTint, TintModifiers newTintModifiers)
		{
			return new SpriteRenderable(sprite, pos, Offset, ZOffset, Palette, scale, Alpha, newTint, newTintModifiers, IsDecoration, rotation);
		}

		float3 ScreenPosition(WorldRenderer wr)
		{
			return DrawPosition(sprite, wr.Screen3DPxPosition(pos) + wr.ScreenPxOffset(Offset), scale);
		}

		/// <summary>
		/// The location to pass to SpriteRenderer.DrawSprite so a sprite is centred on <paramref name="screenPos"/> (moved by
		/// its own offset), snapped to whole pixels by truncating half its scaled size.
		/// RAPX: a sprite trimmed to its visible pixels at load time (<see cref="PaddedSprite"/>) is placed from the full frame
		/// it was cut from, so its pixels land exactly where the untrimmed frame's would at any scale and on mirrored axes.
		/// A centred trim also keeps the quad's centre, the pivot of rotated draws, on the full frame's centre.
		/// </summary>
		public static float3 DrawPosition(Sprite sprite, in float3 screenPos, float scale)
		{
			var s = 0.5f * scale * sprite.Size;
			if (sprite is not PaddedSprite p)
				return screenPos - new float3((int)s.X, (int)s.Y, s.Z);

			// Where the full frame's drawing anchor would be, then CropOrigin texels into it (mirrored axes have a negative
			// PaddedSize and are drawn from the opposite edge), less the trimmed sprite's own offset that DrawSprite adds back
			var f = 0.5f * scale * p.PaddedSize;
			var dx = p.PaddedOffset.X + (p.PaddedSize.X < 0 ? -p.CropOrigin.X : p.CropOrigin.X) - p.Offset.X;
			var dy = p.PaddedOffset.Y + (p.PaddedSize.Y < 0 ? -p.CropOrigin.Y : p.CropOrigin.Y) - p.Offset.Y;
			return screenPos - new float3((int)f.X, (int)f.Y, s.Z) + new float3(scale * dx, scale * dy, 0);
		}

		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void Render(WorldRenderer wr)
		{
			var wsr = Game.Renderer.WorldSpriteRenderer;
			var t = Alpha * Tint;
			if (wr.TerrainLighting != null && (TintModifiers & TintModifiers.IgnoreWorldTint) == 0)
				t *= wr.TerrainLighting.TintAt(pos);

			// Shader interprets negative alpha as a flag to use the tint colour directly instead of multiplying the sprite colour
			var a = Alpha;
			if ((TintModifiers & TintModifiers.ReplaceColor) != 0)
				a *= -1;

			wsr.DrawSprite(sprite, Palette, ScreenPosition(wr), scale, t, a, rotation.RendererRadians());
		}

		public void RenderDebugGeometry(WorldRenderer wr)
		{
			var pos = ScreenPosition(wr) + sprite.Offset;
			var tl = wr.Viewport.WorldToViewPx(pos);
			var br = wr.Viewport.WorldToViewPx(pos + sprite.Size);
			if (rotation == WAngle.Zero)
				Game.Renderer.RgbaColorRenderer.DrawRect(tl, br, 1, Color.Red);
			else
				Game.Renderer.RgbaColorRenderer.DrawPolygon(Util.RotateQuad(tl, br - tl, rotation.RendererRadians()), 1, Color.Red);
		}

		public Rectangle ScreenBounds(WorldRenderer wr)
		{
			var screenOffset = ScreenPosition(wr) + sprite.Offset;
			return Util.BoundingRectangle(screenOffset, sprite.Size, rotation.RendererRadians());
		}
	}
}
