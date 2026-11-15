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
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA.Mods.Common.Graphics
{
	public class DefaultSpriteSequenceLoader : ISpriteSequenceLoader
	{
		public readonly int BgraSheetSize = 2048;
		public readonly int IndexedSheetSize = 2048;

		static readonly MiniYaml NoData = new(null);

		public DefaultSpriteSequenceLoader(ModData modData)
		{
			var metadata = modData.Manifest.Get<SpriteSequenceFormat>().Metadata;
			if (metadata.TryGetValue("BgraSheetSize", out var yaml))
				BgraSheetSize = FieldLoader.GetValue<int>("BgraSheetSize", yaml.Value);

			if (metadata.TryGetValue("IndexedSheetSize", out yaml))
				IndexedSheetSize = FieldLoader.GetValue<int>("IndexedSheetSize", yaml.Value);

			// RAPX: true colour files whose transparent borders are trimmed at load time. Both lists are
			// filename globs: * matches within one folder, ** across folders.
			if (metadata.TryGetValue("CropTransparent", out yaml))
				cropIncludes = FieldLoader.GetValue<string[]>("CropTransparent", yaml.Value).Select(GlobToRegex).ToArray();

			if (metadata.TryGetValue("CropTransparentExclude", out yaml))
				cropExcludes = FieldLoader.GetValue<string[]>("CropTransparentExclude", yaml.Value).Select(GlobToRegex).ToArray();

			// RAPX: true colour files shrunk at load time to the largest size they can be drawn at (same glob syntax).
			if (metadata.TryGetValue("Downscale", out yaml))
				downscaleIncludes = FieldLoader.GetValue<string[]>("Downscale", yaml.Value).Select(GlobToRegex).ToArray();

			if (metadata.TryGetValue("DownscaleExclude", out yaml))
				downscaleExcludes = FieldLoader.GetValue<string[]>("DownscaleExclude", yaml.Value).Select(GlobToRegex).ToArray();

			if (metadata.TryGetValue("DownscaleMaxMagnification", out yaml))
				downscaleMaxMagnification = FieldLoader.GetValue<float>("DownscaleMaxMagnification", yaml.Value);

			if (metadata.TryGetValue("DownscaleMinFactor", out yaml))
				downscaleMinFactor = FieldLoader.GetValue<float>("DownscaleMinFactor", yaml.Value);

			if (metadata.TryGetValue("DownscaleOversample", out yaml))
				downscaleOversample = Math.Max(1f, FieldLoader.GetValue<float>("DownscaleOversample", yaml.Value));

			if (metadata.TryGetValue("DownscaleFilter", out yaml))
				DownscaledFrame.Filter = FieldLoader.GetValue<SpriteDownscaleFilter>("DownscaleFilter", yaml.Value);

			this.modData = modData;
		}

		readonly Regex[] cropIncludes = Array.Empty<Regex>();
		readonly Regex[] cropExcludes = Array.Empty<Regex>();

		readonly ModData modData;
		readonly Regex[] downscaleIncludes = Array.Empty<Regex>();
		readonly Regex[] downscaleExcludes = Array.Empty<Regex>();

		// Screen pixels per world pixel the art must stay sharp up to; 0 = the viewport's maximum zoom for this window
		readonly float downscaleMaxMagnification;
		readonly float downscaleMinFactor = 1.1f;

		// Source texels kept per screen pixel at the maximum magnification (1 = exactly one, larger = sharper, more memory)
		readonly float downscaleOversample = 1f;

		public bool CanDownscale(string filename)
		{
			return downscaleIncludes.Any(r => r.IsMatch(filename)) && !downscaleExcludes.Any(r => r.IsMatch(filename));
		}

		/// <summary>
		/// RAPX: the most screen pixels one world pixel can cover, so art is never shrunk below one texel per screen
		/// pixel at any zoom the player can reach. 0 outside the game (utility commands), where nothing is shrunk.
		/// </summary>
		public float MaxMagnification()
		{
			if (downscaleMaxMagnification > 0)
				return downscaleMaxMagnification;

			if (Game.Renderer == null || Game.Settings == null)
				return 0;

			return Viewport.ZoomRange(modData.Manifest.Get<WorldViewportSizes>(), Game.Settings.Graphics).MaxZoom;
		}

		/// <summary>
		/// RAPX: a downscale request for a sequence drawn at <paramref name="scale"/> whose files all match the
		/// Downscale globs, or null when its art is already no larger than it can be shown.
		/// </summary>
		public SpriteDownscaleRequest DownscaleRequest(IEnumerable<string> filenames, float scale)
		{
			if (downscaleIncludes.Length == 0 || scale <= 0)
				return null;

			var any = false;
			foreach (var f in filenames)
			{
				if (!CanDownscale(f))
					return null;

				any = true;
			}

			if (!any)
				return null;

			var magnification = MaxMagnification();
			if (magnification <= 0)
				return null;

			var factor = 1f / (scale * magnification * downscaleOversample);
			return factor >= downscaleMinFactor ? new SpriteDownscaleRequest(factor, downscaleMinFactor) : null;
		}

		static Regex GlobToRegex(string glob)
		{
			var pattern = Regex.Escape(glob).Replace(@"\*\*", ".*").Replace(@"\*", "[^/]*");
			return new Regex("^" + pattern + "$", RegexOptions.CultureInvariant);
		}

		public SpriteCropMode CropMode(string filename, bool rotates)
		{
			if (!cropIncludes.Any(r => r.IsMatch(filename)) || cropExcludes.Any(r => r.IsMatch(filename)))
				return SpriteCropMode.None;

			return rotates ? SpriteCropMode.Centred : SpriteCropMode.Tight;
		}

		public virtual ISpriteSequence CreateSequence(
			ModData modData, string tileset, SpriteCache cache, string image, string sequence, MiniYaml data, MiniYaml defaults)
		{
			return new DefaultSpriteSequence(cache, this, image, sequence, data, defaults);
		}

		int ISpriteSequenceLoader.BgraSheetSize => BgraSheetSize;
		int ISpriteSequenceLoader.IndexedSheetSize => IndexedSheetSize;

		IReadOnlyDictionary<string, ISpriteSequence> ISpriteSequenceLoader.ParseSequences(
			ModData modData, string tileset, SpriteCache cache, MiniYamlNode imageNode)
		{
			var sequences = new Dictionary<string, ISpriteSequence>();
			var node = imageNode.Value.NodeWithKeyOrDefault("Defaults");
			var defaults = node?.Value ?? NoData;
			imageNode = imageNode.WithValue(imageNode.Value.WithNodes(imageNode.Value.Nodes.Remove(node)));

			foreach (var sequenceNode in imageNode.Value.Nodes)
			{
				using (new Support.PerfTimer($"new Sequence(\"{imageNode.Key}\")", 20))
				{
					try
					{
						var sequence = CreateSequence(modData, tileset, cache, imageNode.Key, sequenceNode.Key, sequenceNode.Value, defaults);
						((DefaultSpriteSequence)sequence).ReserveSprites(modData, tileset, cache, sequenceNode.Value, defaults);
						sequences.Add(sequenceNode.Key, sequence);
					}
					catch (Exception e)
					{
						throw new InvalidDataException($"Failed to parse sequences for {imageNode.Key}.{sequenceNode.Key} at {imageNode.Value.Nodes[0].Location}:\n{e}");
					}
				}
			}

			return new ReadOnlyDictionary<string, ISpriteSequence>(sequences);
		}
	}

	public struct SpriteSequenceField<T>
	{
		public string Key;
		public T DefaultValue;

		public SpriteSequenceField(string key, T defaultValue)
		{
			Key = key;
			DefaultValue = defaultValue;
		}
	}

	[Desc("Generic sprite sequence implementation, mostly unencumbered with game- or artwork-specific logic.")]
	public class DefaultSpriteSequence : ISpriteSequence
	{
		protected class SpriteReservation
		{
			public int Token;
			public float3 Offset;
			public bool FlipX;
			public bool FlipY;
			public float ZRamp;
			public BlendMode BlendMode;
			public int[] Frames;
		}

		protected readonly struct ReservationInfo
		{
			public readonly string Filename;
			public readonly List<int> LoadFrames;
			public readonly int[] Frames;
			public readonly MiniYamlNode.SourceLocation Location;

			public ReservationInfo(string filename, int[] loadFrames, int[] frames, MiniYamlNode.SourceLocation location)
				: this(filename, loadFrames?.ToList(), frames, location) { }

			public ReservationInfo(string filename, List<int> loadFrames, int[] frames, MiniYamlNode.SourceLocation location)
			{
				Filename = filename;
				LoadFrames = loadFrames;
				Frames = frames;
				Location = location;
			}
		}

		[Desc("File name of the sprite to use for this sequence.")]
		protected static readonly SpriteSequenceField<string> Filename = new(nameof(Filename), null);

		[Desc("File name pattern to build the sprite to use for this sequence.")]
		protected static readonly SpriteSequenceField<string> FilenamePattern = new(nameof(FilenamePattern), null);

		[Desc("Frame index to start from.")]
		protected static readonly SpriteSequenceField<int> Start = new(nameof(Start), 0);

		[Desc("Number of frames to use. Does not have to be the total amount the sprite sheet has.")]
		protected static readonly SpriteSequenceField<int> Length = new(nameof(Length), 1);

		[Desc("Overrides Length if a different number of frames is defined between facings.")]
		protected static readonly SpriteSequenceField<int> Stride = new(nameof(Stride), -1);

		[Desc("The number of facings that are provided by sprite frames. Use negative values to rotate counter-clockwise.")]
		protected static readonly SpriteSequenceField<int> Facings = new(nameof(Facings), 1);

		[Desc("The total number of facings for the sequence. " +
			"If >Facings, the closest facing sprite will be rotated to match. " +
			"Use negative values to rotate counter-clockwise.")]
		protected static readonly SpriteSequenceField<int?> InterpolatedFacings = new(nameof(InterpolatedFacings), null);

		[Desc("Time (in milliseconds at default game speed) to wait until playing the next frame in the animation.")]
		protected static readonly SpriteSequenceField<int> Tick = new(nameof(Tick), 40);

		[Desc("Value controlling the Z-order. A higher values means rendering on top of other sprites at the same position. " +
			"Use power of 2 values to avoid glitches.")]
		protected static readonly SpriteSequenceField<WDist> ZOffset = new(nameof(ZOffset), WDist.Zero);

		[Desc("Additional sprite depth Z offset to apply as a function of sprite Y (0: vertical, 1: flat on terrain)")]
		protected static readonly SpriteSequenceField<int> ZRamp = new(nameof(ZRamp), 0);

		[Desc("If the shadow is not part of the sprite, but baked into the same sprite sheet at a fixed offset, " +
			"set this to the frame index where it starts.")]
		protected static readonly SpriteSequenceField<int> ShadowStart = new(nameof(ShadowStart), -1);

		[Desc("Set Z-Offset for the separate shadow. Used by the later Westwood 2.5D titles.")]
		protected static readonly SpriteSequenceField<WDist> ShadowZOffset = new(nameof(ShadowZOffset), new WDist(-5));

		[Desc("The individual frames to play instead of going through them sequentially from the `Start`.")]
		protected static readonly SpriteSequenceField<int[]> Frames = new(nameof(Frames), null);

		[Desc("Don't apply terrain lighting or colored overlays.")]
		protected static readonly SpriteSequenceField<bool> IgnoreWorldTint = new(nameof(IgnoreWorldTint), false);

		[Desc("Adjusts the rendered size of the sprite")]
		protected static readonly SpriteSequenceField<float> Scale = new(nameof(Scale), 1);

		[Desc("Play the sprite sequence back and forth.")]
		protected static readonly SpriteSequenceField<bool> Reverses = new(nameof(Reverses), false);

		[Desc("Support a frame order where each animation step is split per each direction.")]
		protected static readonly SpriteSequenceField<bool> Transpose = new(nameof(Transpose), false);

		[Desc("Mirror on the X axis.")]
		protected static readonly SpriteSequenceField<bool> FlipX = new(nameof(FlipX), false);

		[Desc("Mirror on the Y axis.")]
		protected static readonly SpriteSequenceField<bool> FlipY = new(nameof(FlipY), false);

		[Desc("Change the position in-game on X, Y, Z.")]
		protected static readonly SpriteSequenceField<float3> Offset = new(nameof(Offset), float3.Zero);

		[Desc("Apply an OpenGL/Photoshop inspired blend mode.")]
		protected static readonly SpriteSequenceField<BlendMode> BlendMode = new(nameof(BlendMode), OpenRA.BlendMode.Alpha);

		[Desc("Create a virtual sprite file by concatenating one or more frames from multiple files, with optional transformations applied. " +
			"All defined frames will be loaded into memory, even if unused, so use this property with care.")]
		protected static readonly SpriteSequenceField<MiniYaml> Combine = new(nameof(Combine), null);

		[Desc("Sets transparency - use one value to set for all frames or provide a value for each frame.")]
		protected static readonly SpriteSequenceField<float[]> Alpha = new(nameof(Alpha), null);

		[Desc("Fade the animation from fully opaque on the first frame to fully transparent after the last frame.")]
		protected static readonly SpriteSequenceField<bool> AlphaFade = new(nameof(AlphaFade), false);

		[Desc("Name of the file containing the depth data sprite.")]
		protected static readonly SpriteSequenceField<string> DepthSprite = new(nameof(DepthSprite), null);

		[Desc("Frame index containing the depth data.")]
		protected static readonly SpriteSequenceField<int> DepthSpriteFrame = new(nameof(DepthSpriteFrame), 0);

		[Desc("X, Y offset to apply to the depth sprite.")]
		protected static readonly SpriteSequenceField<float2> DepthSpriteOffset = new(nameof(DepthSpriteOffset), float2.Zero);

		protected static readonly MiniYaml NoData = new(null);
		protected static readonly int[] FirstFrame = { 0 };

		protected readonly ISpriteSequenceLoader Loader;

		protected string image;
		protected List<SpriteReservation> spritesToLoad = new();
		protected Sprite[] sprites;
		protected Sprite[] shadowSprites;
		protected bool reverseFacings;
		protected bool reverses;

		protected int start;
		protected int shadowStart;
		protected int? length;
		protected int? stride;
		protected bool transpose;

		protected int facings;
		protected int? interpolatedFacings;
		protected int tick;
		protected int zOffset;
		protected int shadowZOffset;
		protected bool ignoreWorldTint;
		protected float scale;

		// RAPX: how much the cache may shrink this sequence's files (null = not at all); Applied is known after loading
		protected SpriteDownscaleRequest downscale;
		protected float[] alpha;
		protected bool alphaFade;
		protected Rectangle? bounds;

		protected int? depthSpriteReservation;
		protected float2 depthSpriteOffset;

		protected void ThrowIfUnresolved()
		{
			if (bounds == null)
				throw new InvalidOperationException($"Unable to query unresolved sequence {image}.{Name}.");
		}

		int ISpriteSequence.Length
		{
			get
			{
				ThrowIfUnresolved();
				return length.Value;
			}
		}

		int ISpriteSequence.Facings => interpolatedFacings ?? facings;
		int ISpriteSequence.Tick => tick;
		int ISpriteSequence.ZOffset => zOffset;
		int ISpriteSequence.ShadowZOffset => shadowZOffset;
		bool ISpriteSequence.IgnoreWorldTint => ignoreWorldTint;
		float ISpriteSequence.Scale => GetScale();
		Rectangle ISpriteSequence.Bounds
		{
			get
			{
				ThrowIfUnresolved();
				return bounds.Value;
			}
		}

		public string Name { get; }

		protected static T LoadField<T>(string key, T fallback, MiniYaml data, MiniYaml defaults = null)
		{
			var node = data.NodeWithKeyOrDefault(key) ?? defaults?.NodeWithKeyOrDefault(key);
			if (node == null)
				return fallback;

			return FieldLoader.GetValue<T>(key, node.Value.Value);
		}

		protected static T LoadField<T>(SpriteSequenceField<T> field, MiniYaml data, MiniYaml defaults = null)
		{
			return LoadField(field, data, defaults, out _);
		}

		protected static T LoadField<T>(SpriteSequenceField<T> field, MiniYaml data, MiniYaml defaults, out MiniYamlNode.SourceLocation location)
		{
			var node = data.NodeWithKeyOrDefault(field.Key) ?? defaults?.NodeWithKeyOrDefault(field.Key);
			if (node == null)
			{
				location = default;
				return field.DefaultValue;
			}

			location = node.Location;
			return FieldLoader.GetValue<T>(field.Key, node.Value.Value);
		}

		protected static Rectangle FlipRectangle(Rectangle rect, bool flipX, bool flipY)
		{
			var left = flipX ? rect.Right : rect.Left;
			var top = flipY ? rect.Bottom : rect.Top;
			var right = flipX ? rect.Left : rect.Right;
			var bottom = flipY ? rect.Top : rect.Bottom;

			return Rectangle.FromLTRB(left, top, right, bottom);
		}

		protected static List<int> CalculateFrameIndices(
			int start, int? length, int stride, int facings, int[] frames, bool transpose, bool reverseFacings, int shadowStart)
		{
			// Request all frames
			if (length == null)
				return null;

			// Only request the subset of frames that we actually need
			var usedFrames = new List<int>();
			for (var facing = 0; facing < facings; facing++)
			{
				var facingInner = reverseFacings ? (facings - facing) % facings : facing;
				for (var frame = 0; frame < length.Value; frame++)
				{
					var i = transpose ? frame * facings + facingInner :
						facingInner * stride + frame;

					usedFrames.Add(frames?[i] ?? start + i);
				}
			}

			if (shadowStart >= 0)
			{
				var shadowOffset = shadowStart - start;
				var frameCount = usedFrames.Count;
				for (var i = 0; i < frameCount; i++)
					usedFrames.Add(usedFrames[i] + shadowOffset);
			}

			return usedFrames;
		}

		protected virtual IEnumerable<ReservationInfo> ParseFilenames(ModData modData, string tileset, int[] frames, MiniYaml data, MiniYaml defaults)
		{
			var filenamePatternNode = data.NodeWithKeyOrDefault(FilenamePattern.Key) ?? defaults.NodeWithKeyOrDefault(FilenamePattern.Key);
			if (!string.IsNullOrEmpty(filenamePatternNode?.Value.Value))
			{
				var patternStart = LoadField("Start", 0, filenamePatternNode.Value);
				var patternCount = LoadField("Count", 1, filenamePatternNode.Value);

				return Enumerable.Range(patternStart, patternCount).Select(i =>
					new ReservationInfo(filenamePatternNode.Value.Value.FormatInvariant(i),
						FirstFrame, FirstFrame, filenamePatternNode.Location));
			}

			var filename = LoadField(Filename, data, defaults, out var location);

			var loadFrames = CalculateFrameIndices(start, length, stride ?? length ?? 0, facings, frames, transpose, reverseFacings, shadowStart);
			return new[] { new ReservationInfo(filename, loadFrames, frames, location) };
		}

		protected virtual IEnumerable<ReservationInfo> ParseCombineFilenames(ModData modData, string tileset, int[] frames, MiniYaml data)
		{
			var filename = LoadField(Filename, data, null, out var location);
			if (frames == null && LoadField<string>(Length.Key, null, data) != "*")
			{
				var subStart = LoadField("Start", 0, data);
				var subLength = LoadField("Length", 1, data);
				frames = Exts.MakeArray(subLength, i => subStart + i);
			}

			yield return new ReservationInfo(filename, frames, frames, location);
		}

		public DefaultSpriteSequence(SpriteCache cache, ISpriteSequenceLoader loader, string image, string sequence, MiniYaml data, MiniYaml defaults)
		{
			this.image = image;
			Name = sequence;
			Loader = loader;

			start = LoadField(Start, data, defaults);

			length = null;
			var lengthLocation = default(MiniYamlNode.SourceLocation);
			if (LoadField<string>(Length.Key, null, data, defaults) != "*")
				length = LoadField(Length, data, defaults, out lengthLocation);

			stride = LoadField(Stride.Key, length, data, defaults);
			facings = LoadField(Facings, data, defaults, out var facingsLocation);
			interpolatedFacings = LoadField(InterpolatedFacings, data, defaults, out var interpolatedFacingsLocation);

			tick = LoadField(Tick, data, defaults);
			zOffset = LoadField(ZOffset, data, defaults).Length;

			shadowStart = LoadField(ShadowStart, data, defaults);
			shadowZOffset = LoadField(ShadowZOffset, data, defaults).Length;

			ignoreWorldTint = LoadField(IgnoreWorldTint, data, defaults);
			scale = LoadField(Scale, data, defaults);

			reverses = LoadField(Reverses, data, defaults);
			transpose = LoadField(Transpose, data, defaults);
			alpha = LoadField(Alpha, data, defaults);
			alphaFade = LoadField(AlphaFade, data, defaults, out var alphaFadeLocation);

			var depthSprite = LoadField(DepthSprite, data, defaults, out var depthSpriteLocation);
			if (!string.IsNullOrEmpty(depthSprite))
				depthSpriteReservation = cache.ReserveSprites(depthSprite, new[] { LoadField(DepthSpriteFrame, data, defaults) }, depthSpriteLocation);

			depthSpriteOffset = LoadField(DepthSpriteOffset, data, defaults);

			if (facings < 0)
			{
				reverseFacings = true;
				facings = -facings;
			}

			// Facings must be an integer factor of 1024 (i.e. 1024 / facings is an integer) to allow the frames to be
			// mapped uniformly over the full rotation range. This implies that it is a power of 2.
			if (facings == 0 || facings > 1024 || !Exts.IsPowerOf2(facings))
				throw new YamlException(
					$"{facingsLocation}: {Facings.Key} must be within the (positive or negative) range of 1 to 1024, and a power of 2.");

			if (interpolatedFacings != null &&
				(interpolatedFacings < 2 ||
				interpolatedFacings <= facings ||
				interpolatedFacings > 1024 ||
				!Exts.IsPowerOf2(interpolatedFacings.Value)))
				throw new YamlException(
					$"{interpolatedFacingsLocation}: {InterpolatedFacings.Key} must be greater than {Facings.Key}, " +
					"within the range of 2 to 1024, and a power of 2.");

			if (length != null && length <= 0)
				throw new YamlException($"{lengthLocation}: {Length.Key} must be positive.");

			if (length == null && facings > 1)
				throw new YamlException($"{facingsLocation}: {Facings.Key} cannot be used with {Length.Key}: *.");

			if (alphaFade && alpha != null)
				throw new YamlException($"{alphaFadeLocation}: {AlphaFade.Key} cannot be used with {Alpha.Key}.");
		}

		public virtual void ReserveSprites(ModData modData, string tileset, SpriteCache cache, MiniYaml data, MiniYaml defaults)
		{
			var frames = LoadField(Frames, data, defaults);
			var flipX = LoadField(FlipX, data, defaults);
			var flipY = LoadField(FlipY, data, defaults);
			var zRamp = LoadField(ZRamp, data, defaults);
			var offset = LoadField(Offset, data, defaults);
			var blendMode = LoadField(BlendMode, data, defaults);

			var combineNode = data.NodeWithKeyOrDefault(Combine.Key);
			if (combineNode != null)
			{
				for (var i = 0; i < combineNode.Value.Nodes.Length; i++)
				{
					var subData = combineNode.Value.Nodes[i].Value;
					var subOffset = LoadField(Offset, subData, NoData);
					var subFlipX = LoadField(FlipX, subData, NoData);
					var subFlipY = LoadField(FlipY, subData, NoData);
					var subFrames = LoadField(Frames, subData);

					foreach (var f in ParseCombineFilenames(modData, tileset, subFrames, subData))
					{
						spritesToLoad.Add(new SpriteReservation
						{
							Token = cache.ReserveSprites(f.Filename, f.LoadFrames, f.Location, crop: CropMode(f.Filename)),
							Offset = subOffset + offset,
							FlipX = subFlipX ^ flipX,
							FlipY = subFlipY ^ flipY,
							BlendMode = blendMode,
							ZRamp = zRamp,
							Frames = f.Frames
						});
					}
				}
			}
			else
			{
				var files = ParseFilenames(modData, tileset, frames, data, defaults).ToList();

				// RAPX: a depth sprite must keep the size of the sprites it is paired with, so such sequences stay full size
				if (depthSpriteReservation == null)
					downscale = (Loader as DefaultSpriteSequenceLoader)?.DownscaleRequest(files.Select(f => f.Filename), scale);

				foreach (var f in files)
				{
					spritesToLoad.Add(new SpriteReservation
					{
						Token = cache.ReserveSprites(f.Filename, f.LoadFrames, f.Location, crop: CropMode(f.Filename), downscale: downscale),
						Offset = offset,
						FlipX = flipX,
						FlipY = flipY,
						BlendMode = blendMode,
						ZRamp = zRamp,
						Frames = f.Frames,
					});
				}
			}
		}

		SpriteCropMode CropMode(string filename)
		{
			// Sequences with interpolated facings are drawn rotated about the sprite centre
			return (Loader as DefaultSpriteSequenceLoader)?.CropMode(filename, interpolatedFacings != null) ?? SpriteCropMode.None;
		}

		/// <summary>
		/// RAPX: places a cropped sprite so its pixels land exactly where the uncropped frame's would.
		/// SpriteRenderable truncates half the scaled sprite size to whole pixels, so the crop's offset
		/// absorbs the difference that truncation makes between the cropped and the full size.
		/// </summary>
		Sprite ResolvePadded(PaddedSprite p, SpriteReservation r)
		{
			var odx = r.Offset.X + (r.FlipX ? -p.PaddedOffset.X : p.PaddedOffset.X);
			var ody = r.Offset.Y + (r.FlipY ? -p.PaddedOffset.Y : p.PaddedOffset.Y);
			var odz = r.Offset.Z + p.PaddedOffset.Z + r.ZRamp * ody;

			var fullW = (int)Math.Abs(p.PaddedSize.X);
			var fullH = (int)Math.Abs(p.PaddedSize.Y);
			var w = p.Bounds.Width;
			var h = p.Bounds.Height;
			var x0 = r.FlipX ? fullW - p.CropOrigin.X - w : p.CropOrigin.X;
			var y0 = r.FlipY ? fullH - p.CropOrigin.Y - h : p.CropOrigin.Y;

			var s = GetScale();
			if (s <= 0)
				s = 1;

			var dx = odx + x0 + ((int)(0.5f * s * w) - (int)(0.5f * s * fullW)) / s;
			var dy = ody + y0 + ((int)(0.5f * s * h) - (int)(0.5f * s * fullH)) / s;

			var sprite = new Sprite(p.Sheet, FlipRectangle(p.Bounds, r.FlipX, r.FlipY), r.ZRamp, new float3(dx, dy, odz), p.Channel, r.BlendMode);
			var paddedSize = new float2(r.FlipX ? -fullW : fullW, r.FlipY ? -fullH : fullH);
			return new PaddedSprite(sprite, new float3(odx, ody, odz), paddedSize, p.CropOrigin);
		}

		public virtual void ResolveSprites(SpriteCache cache)
		{
			if (bounds != null)
				return;

			// RAPX: the files were shrunk by this factor, so draw them that much larger and move the sequence's own
			// pixel offsets (which are in sprite pixels) into the smaller pixels. The result is drawn exactly as before.
			var shrunk = downscale?.Applied ?? 1f;
			if (shrunk > 1f)
			{
				scale *= shrunk;
				foreach (var r in spritesToLoad)
					r.Offset /= shrunk;
			}

			Sprite depthSprite = null;
			if (depthSpriteReservation != null)
				depthSprite = cache.ResolveSprites(depthSpriteReservation.Value).First(s => s != null);

			var allSprites = spritesToLoad.SelectMany(r =>
			{
				var resolved = cache.ResolveSprites(r.Token);
				if (r.Frames != null)
					resolved = r.Frames.Select(f => resolved[f]).ToArray();

				return resolved.Select(s =>
				{
					if (s == null)
						return null;

					if (s is PaddedSprite padded && depthSprite == null)
						return ResolvePadded(padded, r);

					var dx = r.Offset.X + (r.FlipX ? -s.Offset.X : s.Offset.X);
					var dy = r.Offset.Y + (r.FlipY ? -s.Offset.Y : s.Offset.Y);
					var dz = r.Offset.Z + s.Offset.Z + r.ZRamp * dy;
					var sprite = new Sprite(s.Sheet, FlipRectangle(s.Bounds, r.FlipX, r.FlipY), r.ZRamp, new float3(dx, dy, dz), s.Channel, r.BlendMode);
					if (depthSprite == null)
						return sprite;

					var cw = (depthSprite.Bounds.Left + depthSprite.Bounds.Right) / 2 + (int)(s.Offset.X + depthSpriteOffset.X);
					var ch = (depthSprite.Bounds.Top + depthSprite.Bounds.Bottom) / 2 + (int)(s.Offset.Y + depthSpriteOffset.Y);
					var w = s.Bounds.Width / 2;
					var h = s.Bounds.Height / 2;

					return new SpriteWithSecondaryData(sprite, depthSprite.Sheet, Rectangle.FromLTRB(cw - w, ch - h, cw + w, ch + h), depthSprite.Channel);
				});
			}).ToArray();

			length ??= allSprites.Length - start;

			if (alpha != null)
			{
				if (alpha.Length == 1)
					alpha = Exts.MakeArray(length.Value, _ => alpha[0]);
				else if (alpha.Length != length.Value)
					throw new YamlException($"Sequence {image}.{Name} must define either 1 or {length.Value} Alpha values.");
			}
			else if (alphaFade)
				alpha = Exts.MakeArray(length.Value, i => float2.Lerp(1f, 0f, i / (length.Value - 1f)));

			// Reindex sprites to order facings anti-clockwise and remove unused frames
			var index = CalculateFrameIndices(start, length.Value, stride ?? length.Value, facings, null, transpose, reverseFacings, -1);
			if (reverses)
			{
				index.AddRange(index.Skip(1).Take(length.Value - 2).Reverse());
				alpha = alpha?.Concat(alpha.Skip(1).Take(length.Value - 2).Reverse()).ToArray();

				length = 2 * length - 2;
			}

			if (index.Count == 0)
				throw new YamlException($"Sequence {image}.{Name} does not define any frames.");

			var minIndex = index.Min();
			var maxIndex = index.Max();
			if (minIndex < 0 || maxIndex >= allSprites.Length)
				throw new YamlException($"Sequence {image}.{Name} uses frames between {minIndex}..{maxIndex}, but only 0..{allSprites.Length - 1} exist.");

			sprites = index.Select(f => allSprites[f]).ToArray();
			if (shadowStart >= 0)
				shadowSprites = index.Select(f => allSprites[f - start + shadowStart]).ToArray();

			bounds = sprites.Concat(shadowSprites ?? Enumerable.Empty<Sprite>()).Select(OffsetSpriteBounds).Union();
		}

		protected static Rectangle OffsetSpriteBounds(Sprite sprite)
		{
			// RAPX: cropped sprites report the bounds of the full frame they were cut from
			if (sprite is PaddedSprite p)
				return new Rectangle(
					(int)(p.PaddedOffset.X - p.PaddedSize.X / 2),
					(int)(p.PaddedOffset.Y - p.PaddedSize.Y / 2),
					(int)p.PaddedSize.X, (int)p.PaddedSize.Y);

			if (sprite == null || sprite.Bounds.IsEmpty)
				return Rectangle.Empty;

			return new Rectangle(
				(int)(sprite.Offset.X - sprite.Size.X / 2),
				(int)(sprite.Offset.Y - sprite.Size.Y / 2),
				sprite.Bounds.Width, sprite.Bounds.Height);
		}

		public Sprite GetSprite(int frame)
		{
			return GetSprite(frame, WAngle.Zero);
		}

		public (Sprite Sprite, WAngle Rotation) GetSpriteWithRotation(int frame, WAngle facing)
		{
			var rotation = WAngle.Zero;
			if (interpolatedFacings != null)
				rotation = Util.GetInterpolatedFacingRotation(facing, Math.Abs(facings), interpolatedFacings.Value);

			return (GetSprite(frame, facing), rotation);
		}

		public Sprite GetShadow(int frame, WAngle facing)
		{
			if (shadowSprites == null)
				return null;

			var index = GetFacingFrameOffset(facing) * length.Value + frame % length.Value;
			var sprite = shadowSprites[index];
			if (sprite == null)
				throw new InvalidOperationException($"Attempted to query unloaded shadow sprite from {image}.{Name} frame={frame} facing={facing}.");

			return sprite;
		}

		public virtual Sprite GetSprite(int frame, WAngle facing)
		{
			ThrowIfUnresolved();
			var index = GetFacingFrameOffset(facing) * length.Value + frame % length.Value;
			var sprite = sprites[index];
			if (sprite == null)
				throw new InvalidOperationException($"Attempted to query unloaded sprite from {image}.{Name} frame={frame} facing={facing}.");

			return sprite;
		}

		protected virtual int GetFacingFrameOffset(WAngle facing)
		{
			return Util.IndexFacing(facing, facings);
		}

		public virtual float GetAlpha(int frame)
		{
			return alpha?[frame] ?? 1f;
		}

		protected virtual float GetScale()
		{
			return scale;
		}
	}
}
