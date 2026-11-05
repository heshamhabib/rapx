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

using OpenRA.FileFormats;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	public enum FullscreenImageFit { Cover, Contain }

	/// <summary>Draws a standalone PNG scaled to cover the widget bounds (cropping the overflow) or to fit inside them.</summary>
	public class FullscreenImageWidget : Widget
	{
		public string Image = null;

		[Desc("Cover fills the bounds and crops the overflow; Contain shows the whole image, leaving the rest uncovered.")]
		public FullscreenImageFit Fit = FullscreenImageFit.Cover;

		[Desc("Which part of the image stays visible when it is wider than the screen: 0 = left edge, 0.5 = center, 1 = right edge.")]
		public float HorizontalAlign = 0.5f;

		readonly ModData modData;
		Sheet sheet;
		Sprite sprite;

		[ObjectCreator.UseCtor]
		public FullscreenImageWidget(ModData modData)
		{
			this.modData = modData;
		}

		public override void Draw()
		{
			sprite ??= LoadImage(modData, Image, out sheet);

			var (pos, size) = Fit == FullscreenImageFit.Contain
				? ContainRect(sprite.Size.XY, RenderBounds)
				: CoverRect(sprite.Size.XY, RenderBounds, HorizontalAlign);
			WidgetUtils.DrawSprite(sprite, pos, size);
		}

		/// <summary>Load a PNG of any size, padding it onto a power-of-two sheet as the renderer requires.</summary>
		public static Sprite LoadImage(ModData modData, string path, out Sheet sheet, BlendMode blendMode = BlendMode.Alpha)
		{
			using (var stream = modData.DefaultFileSystem.Open(path))
			{
				var png = new Png(stream);
				sheet = new Sheet(SheetType.BGRA, new Size(png.Width, png.Height).NextPowerOf2());
				var sprite = new Sprite(sheet, new Rectangle(0, 0, png.Width, png.Height), 0, float3.Zero, TextureChannel.RGBA, blendMode);
				Util.FastCopyIntoSprite(sprite, png);
				sheet.ReleaseBuffer();
				sheet.GetTexture().ScaleFilter = TextureScaleFilter.Linear;
				return sprite;
			}
		}

		/// <summary>Scale an image of the given size so it fully covers bounds, centered vertically.</summary>
		public static (float2 Pos, float2 Size) CoverRect(float2 imageSize, Rectangle bounds, float horizontalAlign = 0.5f)
		{
			var scale = System.Math.Max(bounds.Width / imageSize.X, bounds.Height / imageSize.Y);
			var size = scale * imageSize;
			var pos = new float2(bounds.X + (bounds.Width - size.X) * horizontalAlign, bounds.Y + (bounds.Height - size.Y) / 2);
			return (pos, size);
		}

		/// <summary>Scale an image of the given size so it fits entirely inside bounds, centered.</summary>
		public static (float2 Pos, float2 Size) ContainRect(float2 imageSize, Rectangle bounds)
		{
			var scale = System.Math.Min(bounds.Width / imageSize.X, bounds.Height / imageSize.Y);
			var size = scale * imageSize;
			var pos = new float2(bounds.X + (bounds.Width - size.X) / 2, bounds.Y + (bounds.Height - size.Y) / 2);
			return (pos, size);
		}

		public override void Removed()
		{
			base.Removed();
			sheet?.Dispose();
			sheet = null;
			sprite = null;
		}
	}
}
