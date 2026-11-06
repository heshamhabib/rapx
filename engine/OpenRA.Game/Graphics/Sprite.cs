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
using OpenRA.Primitives;

namespace OpenRA.Graphics
{
	public class Sprite
	{
		public readonly Rectangle Bounds;
		public readonly Sheet Sheet;
		public readonly BlendMode BlendMode;
		public readonly TextureChannel Channel;
		public readonly float ZRamp;
		public readonly float3 Size;
		public readonly float3 Offset;
		public readonly float Top, Left, Bottom, Right;

		public Sprite(Sheet sheet, Rectangle bounds, TextureChannel channel, float scale = 1)
			: this(sheet, bounds, 0, float2.Zero, channel, BlendMode.Alpha, scale) { }

		public Sprite(Sheet sheet, Rectangle bounds, float zRamp, in float3 offset, TextureChannel channel, BlendMode blendMode = BlendMode.Alpha, float scale = 1f)
		{
			Sheet = sheet;
			Bounds = bounds;
			Offset = offset;
			ZRamp = zRamp;
			Channel = channel;
			Size = scale * new float3(bounds.Size.Width, bounds.Size.Height, bounds.Size.Height * zRamp);
			BlendMode = blendMode;

			// Some GPUs suffer from precision issues when rendering into non 1:1 framebuffers that result
			// in rendering a line of texels that sample outside the sprite rectangle.
			// Insetting the texture coordinates by a small fraction of a pixel avoids this
			// with negligible impact on the 1:1 rendering case.
			const float Inset = 1 / 128f;
			Left = (Math.Min(bounds.Left, bounds.Right) + Inset) / sheet.Size.Width;
			Top = (Math.Min(bounds.Top, bounds.Bottom) + Inset) / sheet.Size.Height;
			Right = (Math.Max(bounds.Left, bounds.Right) - Inset) / sheet.Size.Width;
			Bottom = (Math.Max(bounds.Top, bounds.Bottom) - Inset) / sheet.Size.Height;
		}
	}

	/// <summary>How the sprite cache may trim fully transparent pixels from a file's frames when it loads them.</summary>
	public enum SpriteCropMode
	{
		None,

		/// <summary>Crop to the visible pixels.</summary>
		Tight,

		/// <summary>Crop evenly around the frame centre, so sprites rotated about their centre still turn about the same point.</summary>
		Centred
	}

	/// <summary>
	/// RAPX: a sprite cut down to its visible pixels that remembers the full frame it came from.
	/// Sequence bounds and auto selection sizes use the full frame, so they stay as if the padding were still there.
	/// </summary>
	public class PaddedSprite : Sprite
	{
		/// <summary>Offset of the full frame's centre (the offset the uncropped sprite would have).</summary>
		public readonly float3 PaddedOffset;

		/// <summary>Size of the full frame (negative on a flipped axis, like <see cref="Sprite.Size"/>).</summary>
		public readonly float2 PaddedSize;

		/// <summary>Top-left of the cropped rectangle inside the full (unflipped) frame.</summary>
		public readonly int2 CropOrigin;

		public PaddedSprite(Sprite s, in float3 paddedOffset, in float2 paddedSize, int2 cropOrigin)
			: base(s.Sheet, s.Bounds, s.ZRamp, s.Offset, s.Channel, s.BlendMode)
		{
			PaddedOffset = paddedOffset;
			PaddedSize = paddedSize;
			CropOrigin = cropOrigin;
		}
	}

	public class SpriteWithSecondaryData : Sprite
	{
		public readonly Sheet SecondarySheet;
		public readonly Rectangle SecondaryBounds;
		public readonly TextureChannel SecondaryChannel;
		public readonly float SecondaryTop, SecondaryLeft, SecondaryBottom, SecondaryRight;

		public SpriteWithSecondaryData(Sprite s, Sheet secondarySheet, Rectangle secondaryBounds, TextureChannel secondaryChannel)
			: base(s.Sheet, s.Bounds, s.ZRamp, s.Offset, s.Channel, s.BlendMode)
		{
			SecondarySheet = secondarySheet;
			SecondaryBounds = secondaryBounds;
			SecondaryChannel = secondaryChannel;
			SecondaryLeft = (float)Math.Min(secondaryBounds.Left, secondaryBounds.Right) / s.Sheet.Size.Width;
			SecondaryTop = (float)Math.Min(secondaryBounds.Top, secondaryBounds.Bottom) / s.Sheet.Size.Height;
			SecondaryRight = (float)Math.Max(secondaryBounds.Left, secondaryBounds.Right) / s.Sheet.Size.Width;
			SecondaryBottom = (float)Math.Max(secondaryBounds.Top, secondaryBounds.Bottom) / s.Sheet.Size.Height;
		}
	}

	public enum TextureChannel : byte
	{
		Red = 0,
		Green = 1,
		Blue = 2,
		Alpha = 3,
		RGBA = 4
	}
}
