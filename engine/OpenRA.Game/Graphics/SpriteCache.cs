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
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.ExceptionServices;
using System.Threading;
using System.Threading.Tasks;
using OpenRA.FileSystem;
using OpenRA.Primitives;

namespace OpenRA.Graphics
{
	public delegate ISpriteFrame AdjustFrame(ISpriteFrame input, int index, int total);

	public sealed class SpriteCache : IDisposable
	{
		public readonly Dictionary<SheetType, SheetBuilder> SheetBuilders;
		readonly ISpriteLoader[] loaders;
		readonly IReadOnlyFileSystem fileSystem;
		readonly SharedSpriteStore shared;
		readonly Func<string, bool> canShare;

		readonly Dictionary<
			int,
			(int[] Frames, MiniYamlNode.SourceLocation Location, AdjustFrame AdjustFrame, bool Premultiplied)> spriteReservations = new();
		readonly Dictionary<string, List<int>> reservationsByFilename = new();
		readonly Dictionary<string, SpriteCropMode> cropByFilename = new();

		readonly Dictionary<int, Sprite[]> resolvedSprites = new();

		readonly Dictionary<int, (string Filename, MiniYamlNode.SourceLocation Location)> missingFiles = new();

		int nextReservationToken = 1;

		public SpriteCache(
			IReadOnlyFileSystem fileSystem, ISpriteLoader[] loaders, int bgraSheetSize, int indexedSheetSize, int bgraSheetMargin = 1, int indexedSheetMargin = 1,
			SharedSpriteStore shared = null, Func<string, bool> canShare = null)
		{
			this.shared = shared;
			this.canShare = canShare;
			SheetBuilders = CreateSheetBuilders(bgraSheetSize, indexedSheetSize, bgraSheetMargin, indexedSheetMargin);

			this.fileSystem = fileSystem;
			this.loaders = loaders;
		}

		internal static Dictionary<SheetType, SheetBuilder> CreateSheetBuilders(
			int bgraSheetSize, int indexedSheetSize, int bgraSheetMargin = 1, int indexedSheetMargin = 1)
		{
			return new Dictionary<SheetType, SheetBuilder>
			{
				{ SheetType.Indexed, new SheetBuilder(SheetType.Indexed, indexedSheetSize, indexedSheetMargin) },
				{
					// True colour sprites are usually high resolution art drawn scaled down, so filter them smoothly
					SheetType.BGRA, new SheetBuilder(SheetType.BGRA, () =>
					{
						var sheet = SheetBuilder.AllocateSheet(SheetType.BGRA, bgraSheetSize);
						sheet.ScaleFilter = TextureScaleFilter.Linear;
						return sheet;
					}, bgraSheetMargin)
				}
			};
		}

		public int ReserveSprites(string filename, IEnumerable<int> frames, MiniYamlNode.SourceLocation location,
			AdjustFrame adjustFrame = null, bool premultiplied = false, SpriteCropMode crop = SpriteCropMode.None)
		{
			// A file shared by several sequences is cropped once, with the most careful mode any of them asks for.
			if (crop != SpriteCropMode.None && adjustFrame == null)
				cropByFilename[filename] = (SpriteCropMode)Math.Max((int)crop, (int)cropByFilename.GetValueOrDefault(filename));

			var token = nextReservationToken++;
			spriteReservations[token] = (frames?.ToArray(), location, adjustFrame, premultiplied);
			reservationsByFilename.GetOrAdd(filename, _ => new List<int>()).Add(token);
			return token;
		}

		static ISpriteFrame[] GetFrames(IReadOnlyFileSystem fileSystem, string filename, ISpriteLoader[] loaders)
		{
			if (!fileSystem.TryOpen(filename, out var stream))
				return null;

			using (stream)
				return ParseFrames(stream, filename, loaders);
		}

		static ISpriteFrame[] ParseFrames(Stream stream, string filename, ISpriteLoader[] loaders)
		{
			foreach (var loader in loaders)
				if (loader.TryParseSprite(stream, filename, out var frames, out _))
					return frames;

			return null;
		}

		public ISpriteFrame[] LoadFramesUncached(string filename)
		{
			return GetFrames(fileSystem, filename, loaders);
		}

		// RAPX: decode and pack about this many bytes of sprite files at a time, so decoded frames
		// are released batch by batch instead of all being held until the end.
		const int DecodeBatchBytes = 256 * 1024 * 1024;

		public void LoadReservations(ModData modData)
		{
			// RAPX: files whose sprites are all in the shared store (loaded by an earlier map) are resolved
			// without decoding them again; everything else is decoded on worker threads below.
			var toDecode = new List<(string Filename, SpriteCropMode Crop, List<int> Tokens)>();
			foreach (var (filename, tokens) in reservationsByFilename)
				if (!TryResolveShared(filename, tokens))
					toDecode.Add((filename, CropMode(filename), tokens));

			var spriteCache = new Dictionary<(
				string Filename,
				int FrameIndex,
				bool Premultiplied,
				AdjustFrame AdjustFrame),
				Sprite>();

			var decodeTime = new System.Diagnostics.Stopwatch();
			var packTime = new System.Diagnostics.Stopwatch();
			var batches = 0;
			for (var first = 0; first < toDecode.Count; batches++)
			{
				decodeTime.Start();
				var (decoded, next) = DecodeFiles(modData, toDecode, first, DecodeBatchBytes);
				decodeTime.Stop();

				packTime.Start();
				PackBatch(modData, toDecode, first, decoded, spriteCache);
				packTime.Stop();

				first = next;
			}

			Log.Write("perf", $"SpriteCache: decoded {toDecode.Count} files in {batches} batches: " +
				$"decode {decodeTime.ElapsedMilliseconds} ms, pack {packTime.ElapsedMilliseconds} ms");

			spriteReservations.Clear();
			spriteReservations.TrimExcess();
			reservationsByFilename.Clear();
			reservationsByFilename.TrimExcess();
			cropByFilename.Clear();

			foreach (var sb in SheetBuilders.Values)
				sb.Current.ReleaseBuffer();

			shared?.ReleaseBuffers();
		}

		void PackBatch(ModData modData, List<(string Filename, SpriteCropMode Crop, List<int> Tokens)> files, int first,
			ISpriteFrame[][] decoded, Dictionary<(string, int, bool, AdjustFrame), Sprite> spriteCache)
		{
			var pendingResolve = new List<(
				string Filename,
				int FrameIndex,
				int FrameCount,
				bool Premultiplied,
				AdjustFrame AdjustFrame,
				bool Shared,
				SpriteCropMode Crop,
				ISpriteFrame Frame,
				Sprite[] SpritesForToken)>();

			for (var n = 0; n < decoded.Length; n++)
			{
				var (filename, crop, tokens) = files[first + n];
				var loadedFrames = decoded[n];
				var shareFile = CanShare(filename);
				foreach (var token in tokens)
				{
					if (spriteReservations.TryGetValue(token, out var rs))
					{
						if (loadedFrames != null)
						{
							var resolved = new Sprite[loadedFrames.Length];
							resolvedSprites[token] = resolved;
							if (rs.Frames != null && rs.Frames.Any(i => i >= loadedFrames.Length))
								throw new InvalidOperationException($"{rs.Location}: {filename} does not contain frames: " +
									string.Join(',', rs.Frames.Where(f => f >= loadedFrames.Length)));

							var frames = rs.Frames ?? Enumerable.Range(0, loadedFrames.Length);
							var total = rs.Frames?.Length ?? loadedFrames.Length;
							var share = shareFile && rs.AdjustFrame == null;

							var j = 0;
							foreach (var i in frames)
							{
								var frame = loadedFrames[i];
								if (rs.AdjustFrame != null)
									frame = rs.AdjustFrame(frame, j++, total);
								pendingResolve.Add((filename, i, loadedFrames.Length, rs.Premultiplied, rs.AdjustFrame, share, crop, frame, resolved));
							}
						}
						else
						{
							resolvedSprites[token] = null;
							missingFiles[token] = (filename, rs.Location);
						}
					}
				}
			}

			// When the sheet builder is adding sprites, it reserves height for the tallest sprite seen along the row.
			// We can achieve better sheet packing by keeping sprites with similar heights together.
			pendingResolve.Sort((a, b) => a.Frame.Size.Height.CompareTo(b.Frame.Size.Height));
			for (var p = 0; p < pendingResolve.Count; p++)
			{
				var (filename, frameIndex, frameCount, premultiplied, adjustFrame, share, crop, frame, spritesForToken) = pendingResolve[p];

				// Premultiplied and non-premultiplied sprites must be cached separately
				// to cover the case where the same image is requested in both versions.
				spritesForToken[frameIndex] = spriteCache.GetOrAdd(
					(filename, frameIndex, premultiplied, adjustFrame),
					_ =>
					{
						var sheetType = SheetBuilder.FrameTypeToSheetType(frame.Type);
						if (!share)
							return AddFrame(SheetBuilders[sheetType], frame, premultiplied);

						var sharedFrames = shared.GetOrAddFile(filename, premultiplied, crop, frameCount);
						return sharedFrames[frameIndex] ??= AddFrame(shared.SheetBuilders[sheetType], frame, premultiplied);
					});

				// Let the frame's pixels be collected as soon as they are in a sheet
				pendingResolve[p] = default;
				modData.LoadScreen?.Display();
			}

			Array.Clear(decoded);
		}

		static Sprite AddFrame(SheetBuilder builder, ISpriteFrame frame, bool premultiplied)
		{
			var sprite = builder.Add(frame, premultiplied);
			if (frame is CroppedFrame c)
				return new PaddedSprite(sprite, new float3(c.PaddedOffset, 0), new float2(c.PaddedSize.Width, c.PaddedSize.Height), c.CropOrigin);

			return sprite;
		}

		SpriteCropMode CropMode(string filename)
		{
			return cropByFilename.GetValueOrDefault(filename);
		}

		bool CanShare(string filename)
		{
			return shared != null && (canShare == null || canShare(filename));
		}

		bool TryResolveShared(string filename, List<int> tokens)
		{
			if (!CanShare(filename))
				return false;

			var found = new List<(int Token, Sprite[] Resolved)>(tokens.Count);
			foreach (var token in tokens)
			{
				if (!spriteReservations.TryGetValue(token, out var rs))
					continue;

				if (rs.AdjustFrame != null || !shared.TryGetFile(filename, rs.Premultiplied, CropMode(filename), out var sharedFrames))
					return false;

				if (rs.Frames != null && rs.Frames.Any(i => i >= sharedFrames.Length))
					throw new InvalidOperationException($"{rs.Location}: {filename} does not contain frames: " +
						string.Join(',', rs.Frames.Where(f => f >= sharedFrames.Length)));

				var resolved = new Sprite[sharedFrames.Length];
				foreach (var i in rs.Frames ?? Enumerable.Range(0, sharedFrames.Length))
				{
					if (sharedFrames[i] == null)
						return false;

					resolved[i] = sharedFrames[i];
				}

				found.Add((token, resolved));
			}

			foreach (var (token, resolved) in found)
				resolvedSprites[token] = resolved;

			return true;
		}

		/// <summary>
		/// RAPX: reads files in order on this thread (packages such as .mix are not thread safe), starting at
		/// <paramref name="first"/> and stopping after about <paramref name="budgetBytes"/>, and parses them on
		/// worker threads while keeping the load screen updated. Returns the frames of each file read (null when
		/// it is missing or no loader understood it) and the index of the first file not read.
		/// </summary>
		(ISpriteFrame[][] Frames, int Next) DecodeFiles(ModData modData,
			List<(string Filename, SpriteCropMode Crop, List<int> Tokens)> files, int first, long budgetBytes)
		{
			var results = new List<ISpriteFrame[]>();
			var workerCount = Math.Max(1, Math.Min(Environment.ProcessorCount - 1, 8));
			Exception workerError = null;
			using var queue = new BlockingCollection<(int Index, byte[] Data)>(workerCount * 2);
			var workers = Enumerable.Range(0, workerCount).Select(_ => Task.Run(() =>
			{
				foreach (var (index, data) in queue.GetConsumingEnumerable())
				{
					if (Volatile.Read(ref workerError) != null)
						continue;

					try
					{
						var (filename, crop, _) = files[first + index];
						using var stream = new MemoryStream(data, false);
						var frames = ParseFrames(stream, filename, loaders);
						if (frames != null && crop != SpriteCropMode.None)
							for (var f = 0; f < frames.Length; f++)
								frames[f] = CroppedFrame.Crop(frames[f], crop);

						lock (results)
							results[index] = frames;
					}
					catch (Exception e)
					{
						Interlocked.CompareExchange(ref workerError, e, null);
					}
				}
			})).ToArray();

			var next = first;
			try
			{
				long bytesRead = 0;
				while (next < files.Count && bytesRead < budgetBytes && Volatile.Read(ref workerError) == null)
				{
					var index = next++ - first;
					lock (results)
						results.Add(null);

					if (!fileSystem.TryOpen(files[first + index].Filename, out var stream))
						continue;

					byte[] data;
					using (stream)
						data = stream.ReadAllBytes();

					bytesRead += data.Length;
					while (!queue.TryAdd((index, data), 20))
						modData.LoadScreen?.Display();

					modData.LoadScreen?.Display();
				}
			}
			finally
			{
				queue.CompleteAdding();
				while (!Task.WaitAll(workers, 20))
					modData.LoadScreen?.Display();
			}

			if (workerError != null)
				ExceptionDispatchInfo.Capture(workerError).Throw();

			return (results.ToArray(), next);
		}

		public Sprite[] ResolveSprites(int token)
		{
			if (!resolvedSprites.Remove(token, out var resolved))
				throw new InvalidOperationException($"{nameof(token)} {token} has either already been resolved, or was never reserved via {nameof(ReserveSprites)}");

			resolvedSprites.TrimExcess();

			if (missingFiles.TryGetValue(token, out var r))
				throw new FileNotFoundException($"{r.Location}: {r.Filename} not found", r.Filename);

			return resolved;
		}

		public IEnumerable<(string Filename, MiniYamlNode.SourceLocation Location)> MissingFiles => missingFiles.Values.ToHashSet();

		public void Dispose()
		{
			foreach (var sb in SheetBuilders.Values)
				sb.Dispose();
		}
	}

	/// <summary>
	/// RAPX: a true colour frame with its fully transparent border removed. Cropping keeps the visible
	/// pixels where they were (the offset moves with the crop) and remembers the full frame for bounds.
	/// </summary>
	sealed class CroppedFrame : ISpriteFrame
	{
		// Skip crops that save less than this share of the frame: not worth an extra sprite rectangle.
		const float MinSaving = 0.2f;

		public SpriteFrameType Type { get; private init; }
		public Size Size { get; private init; }
		public Size FrameSize { get; private init; }
		public float2 Offset { get; private init; }
		public byte[] Data { get; private init; }
		public bool DisableExportPadding => false;

		public float2 PaddedOffset { get; private init; }
		public Size PaddedSize { get; private init; }
		public int2 CropOrigin { get; private init; }

		public static ISpriteFrame Crop(ISpriteFrame frame, SpriteCropMode mode)
		{
			if (frame.Type != SpriteFrameType.Bgra32 && frame.Type != SpriteFrameType.Rgba32)
				return frame;

			var width = frame.Size.Width;
			var height = frame.Size.Height;
			var data = frame.Data;
			if (width == 0 || height == 0 || data.Length < 4 * width * height)
				return frame;

			// Visible bounding box (alpha > 0)
			int left = width, right = -1, top = -1, bottom = -1;
			for (var y = 0; y < height; y++)
			{
				var row = 4 * y * width;
				var first = -1;
				for (var x = 0; x < width; x++)
				{
					if (data[row + 4 * x + 3] != 0)
					{
						first = x;
						break;
					}
				}

				if (first < 0)
					continue;

				var last = first;
				for (var x = width - 1; x > first; x--)
				{
					if (data[row + 4 * x + 3] != 0)
					{
						last = x;
						break;
					}
				}

				if (top < 0)
					top = y;

				bottom = y;
				left = Math.Min(left, first);
				right = Math.Max(right, last);
			}

			int x0, y0, w, h;
			if (top < 0)
			{
				// Fully transparent: keep an empty sprite
				x0 = y0 = w = h = 0;
			}
			else if (mode == SpriteCropMode.Centred)
			{
				// Same margin on both sides of each axis, so the crop centre stays the frame centre
				x0 = Math.Min(left, width - 1 - right);
				y0 = Math.Min(top, height - 1 - bottom);
				w = width - 2 * x0;
				h = height - 2 * y0;
			}
			else
			{
				x0 = left;
				y0 = top;
				w = right - left + 1;
				h = bottom - top + 1;
			}

			if (w * h > (1 - MinSaving) * width * height)
				return frame;

			var cropped = new byte[4 * w * h];
			for (var y = 0; y < h; y++)
				Buffer.BlockCopy(data, 4 * ((y0 + y) * width + x0), cropped, 4 * y * w, 4 * w);

			return new CroppedFrame
			{
				Type = frame.Type,
				Size = new Size(w, h),
				FrameSize = frame.FrameSize,
				Offset = frame.Offset + new float2(x0 + w / 2f - width / 2f, y0 + h / 2f - height / 2f),
				Data = cropped,
				PaddedOffset = frame.Offset,
				PaddedSize = frame.Size,
				CropOrigin = new int2(x0, y0)
			};
		}
	}

	/// <summary>
	/// RAPX: sprites kept for the lifetime of the mod so that later maps (the skirmish after the menu
	/// shellmap, or the menu after a match) reuse them instead of decoding every file again.
	/// Only files that come from the mod (not from a map package) and need no per-sequence frame
	/// adjustment are stored here. The sheets are owned by this store, not by any map.
	/// </summary>
	public sealed class SharedSpriteStore : IDisposable
	{
		public readonly Dictionary<SheetType, SheetBuilder> SheetBuilders;
		readonly Dictionary<(string Filename, bool Premultiplied, SpriteCropMode Crop), Sprite[]> files = new();

		public SharedSpriteStore(int bgraSheetSize, int indexedSheetSize)
		{
			SheetBuilders = SpriteCache.CreateSheetBuilders(bgraSheetSize, indexedSheetSize);
		}

		public bool TryGetFile(string filename, bool premultiplied, SpriteCropMode crop, out Sprite[] sprites)
		{
			return files.TryGetValue((filename, premultiplied, crop), out sprites);
		}

		public Sprite[] GetOrAddFile(string filename, bool premultiplied, SpriteCropMode crop, int frameCount)
		{
			return files.GetOrAdd((filename, premultiplied, crop), _ => new Sprite[frameCount]);
		}

		public void ReleaseBuffers()
		{
			foreach (var sb in SheetBuilders.Values)
				sb.Current.ReleaseBuffer();
		}

		public void Dispose()
		{
			foreach (var sb in SheetBuilders.Values)
				sb.Dispose();

			files.Clear();
		}
	}
}
