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

		// RAPX: every reservation's downscale request per file (null = that reservation needs the file at full size)
		readonly Dictionary<string, List<SpriteDownscaleRequest>> downscaleByFilename = new();
		readonly HashSet<SpriteDownscaleRequest> downscaleRequests = new();
		long downscaleTexelsBefore, downscaleTexelsAfter;
		int downscaledFiles;

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
			AdjustFrame adjustFrame = null, bool premultiplied = false, SpriteCropMode crop = SpriteCropMode.None,
			SpriteDownscaleRequest downscale = null)
		{
			// A file shared by several sequences is cropped once, with the most careful mode any of them asks for.
			if (crop != SpriteCropMode.None && adjustFrame == null)
				cropByFilename[filename] = (SpriteCropMode)Math.Max((int)crop, (int)cropByFilename.GetValueOrDefault(filename));

			// RAPX: a file is shrunk once, by the smallest factor any of its sequences can live with (see ResolveDownscaleFactors)
			if (adjustFrame != null)
				downscale = null;

			downscaleByFilename.GetOrAdd(filename, _ => new List<SpriteDownscaleRequest>()).Add(downscale);
			if (downscale != null)
			{
				downscaleRequests.Add(downscale);
				if (!downscale.Filenames.Contains(filename))
					downscale.Filenames.Add(filename);
			}

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

		/// <summary>
		/// RAPX: settles how much each file is shrunk. A file gets the smallest factor among the sequences that use it
		/// (1 when any of them needs it unchanged), and a sequence that spans several files must use one factor for all
		/// of them, so its factor drops to the smallest of its files. Repeats until nothing changes (factors only ever
		/// fall, so this ends). Factors below a request's minimum are not worth a resample and become 1.
		/// </summary>
		Dictionary<string, float> ResolveDownscaleFactors()
		{
			var factors = new Dictionary<string, float>(downscaleByFilename.Count);
			bool changed;
			do
			{
				changed = false;
				foreach (var (filename, requests) in downscaleByFilename)
				{
					var factor = float.MaxValue;
					foreach (var r in requests)
						factor = Math.Min(factor, r?.Applied ?? 1f);

					factors[filename] = factor;
				}

				foreach (var r in downscaleRequests)
				{
					var factor = r.Applied;
					foreach (var f in r.Filenames)
						factor = Math.Min(factor, factors[f]);

					if (factor < r.Minimum)
						factor = 1f;

					if (factor < r.Applied)
					{
						r.Applied = factor;
						changed = true;
					}
				}
			}
			while (changed);

			return factors;
		}

		public void LoadReservations(ModData modData)
		{
			var downscales = ResolveDownscaleFactors();

			// RAPX: files whose sprites are all in the shared store (loaded by an earlier map) are resolved
			// without decoding them again; everything else is decoded on worker threads below.
			var toDecode = new List<(string Filename, SpriteCropMode Crop, float Downscale, List<int> Tokens)>();
			foreach (var (filename, tokens) in reservationsByFilename)
				if (!TryResolveShared(filename, tokens, downscales[filename]))
					toDecode.Add((filename, CropMode(filename), downscales[filename], tokens));

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

			var ownSheets = SheetBuilders.Values.Sum(sb => sb.AllSheets.Count());
			var sharedSheets = shared?.SheetBuilders.Values.Sum(sb => sb.AllSheets.Count()) ?? 0;
			Log.Write("perf", $"SpriteCache: downscaled {downscaledFiles} of {toDecode.Count} decoded files: " +
				$"{downscaleTexelsBefore / 1000000} -> {downscaleTexelsAfter / 1000000} megatexels; " +
				$"sheets: {ownSheets} per map + {sharedSheets} shared");

			spriteReservations.Clear();
			spriteReservations.TrimExcess();
			reservationsByFilename.Clear();
			reservationsByFilename.TrimExcess();
			cropByFilename.Clear();
			downscaleByFilename.Clear();
			downscaleRequests.Clear();

			foreach (var sb in SheetBuilders.Values)
				sb.Current.ReleaseBuffer();

			shared?.ReleaseBuffers();
		}

		void PackBatch(ModData modData, List<(string Filename, SpriteCropMode Crop, float Downscale, List<int> Tokens)> files, int first,
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
				float Downscale,
				ISpriteFrame Frame,
				Sprite[] SpritesForToken)>();

			for (var n = 0; n < decoded.Length; n++)
			{
				var (filename, crop, downscale, tokens) = files[first + n];
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
								pendingResolve.Add((filename, i, loadedFrames.Length, rs.Premultiplied, rs.AdjustFrame, share, crop, downscale, frame, resolved));
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
				var (filename, frameIndex, frameCount, premultiplied, adjustFrame, share, crop, downscale, frame, spritesForToken) = pendingResolve[p];

				// Premultiplied and non-premultiplied sprites must be cached separately
				// to cover the case where the same image is requested in both versions.
				spritesForToken[frameIndex] = spriteCache.GetOrAdd(
					(filename, frameIndex, premultiplied, adjustFrame),
					_ =>
					{
						var sheetType = SheetBuilder.FrameTypeToSheetType(frame.Type);
						if (!share)
							return AddFrame(SheetBuilders[sheetType], frame, premultiplied);

						var sharedFrames = shared.GetOrAddFile(filename, premultiplied, crop, downscale, frameCount);
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

		bool TryResolveShared(string filename, List<int> tokens, float downscale)
		{
			if (!CanShare(filename))
				return false;

			var found = new List<(int Token, Sprite[] Resolved)>(tokens.Count);
			foreach (var token in tokens)
			{
				if (!spriteReservations.TryGetValue(token, out var rs))
					continue;

				if (rs.AdjustFrame != null || !shared.TryGetFile(filename, rs.Premultiplied, CropMode(filename), downscale, out var sharedFrames))
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
			List<(string Filename, SpriteCropMode Crop, float Downscale, List<int> Tokens)> files, int first, long budgetBytes)
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
						var (filename, crop, downscale, _) = files[first + index];
						using var stream = new MemoryStream(data, false);
						var frames = ParseFrames(stream, filename, loaders);

						// Shrink before cropping, so the crop sees the pixels that will be drawn
						if (frames != null && downscale > 1f)
						{
							long before = 0, after = 0;
							for (var f = 0; f < frames.Length; f++)
							{
								before += (long)frames[f].Size.Width * frames[f].Size.Height;
								frames[f] = DownscaledFrame.Downscale(frames[f], downscale);
								after += (long)frames[f].Size.Width * frames[f].Size.Height;
							}

							Interlocked.Add(ref downscaleTexelsBefore, before);
							Interlocked.Add(ref downscaleTexelsAfter, after);
							Interlocked.Increment(ref downscaledFiles);
						}

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
	/// RAPX: asks the sprite cache to shrink a sequence's files at load time. Artwork is often far larger than it is
	/// ever drawn, so the cache resamples it down to what the viewport can show at its maximum zoom. One request is
	/// shared by all the files of a sequence, so they end up with the same factor and the sequence can scale by it.
	/// </summary>
	public sealed class SpriteDownscaleRequest
	{
		/// <summary>Factor the sequence would like its files shrunk by (greater than 1).</summary>
		public readonly float Requested;

		/// <summary>Factors below this are not worth a resample: the file is kept as is (factor 1).</summary>
		public readonly float Minimum;

		/// <summary>Factor the files were actually shrunk by, known after the cache has loaded them. 1 = unchanged.</summary>
		public float Applied { get; internal set; }

		internal readonly List<string> Filenames = new();

		public SpriteDownscaleRequest(float requested, float minimum)
		{
			Requested = Applied = Math.Max(1f, requested);
			Minimum = Math.Max(1f, minimum);
		}
	}

	/// <summary>
	/// RAPX: a true colour frame resampled to a smaller size with a box or Lanczos-3 filter (widened to the shrink
	/// factor). Colours are weighted by alpha, so transparent texels do not darken edges. Sizes and offsets shrink
	/// with the pixels.
	/// </summary>
	public enum SpriteDownscaleFilter
	{
		/// <summary>Area average: every source texel goes into exactly one output texel. Cheapest, slightly softer.</summary>
		Box,

		/// <summary>Lanczos-3 windowed sinc: sharper edges, about three times the resampling time.</summary>
		Lanczos
	}

	public sealed class DownscaledFrame : ISpriteFrame
	{
		/// <summary>Filter used for every downscale. Set once by the sequence loader from the mod's metadata.</summary>
		public static SpriteDownscaleFilter Filter = SpriteDownscaleFilter.Box;

		public SpriteFrameType Type { get; private init; }
		public Size Size { get; private init; }
		public Size FrameSize { get; private init; }
		public float2 Offset { get; private init; }
		public byte[] Data { get; private init; }
		public bool DisableExportPadding => false;

		public static ISpriteFrame Downscale(ISpriteFrame frame, float factor)
		{
			if (factor <= 1f)
				return frame;

			var stride = frame.Type switch
			{
				SpriteFrameType.Bgra32 or SpriteFrameType.Rgba32 => 4,
				SpriteFrameType.Bgr24 or SpriteFrameType.Rgb24 => 3,
				_ => 0
			};

			var sw = frame.Size.Width;
			var sh = frame.Size.Height;
			if (stride == 0 || sw == 0 || sh == 0 || frame.Data.Length < stride * sw * sh)
				return frame;

			var dw = Math.Max(1, (int)Math.Round(sw / factor));
			var dh = Math.Max(1, (int)Math.Round(sh / factor));
			if (dw >= sw && dh >= sh)
				return frame;

			var fx = sw / (float)dw;
			var fy = sh / (float)dh;
			return new DownscaledFrame
			{
				Type = frame.Type,
				Size = new Size(dw, dh),
				FrameSize = new Size(
					Math.Max(1, (int)Math.Round(frame.FrameSize.Width / fx)),
					Math.Max(1, (int)Math.Round(frame.FrameSize.Height / fy))),
				Offset = new float2(frame.Offset.X / fx, frame.Offset.Y / fy),
				Data = Resample(frame.Data, stride, sw, sh, dw, dh)
			};
		}

		const int LanczosLobes = 3;

		static double Lanczos(double x)
		{
			if (x == 0)
				return 1;

			if (x <= -LanczosLobes || x >= LanczosLobes)
				return 0;

			var px = Math.PI * x;
			return LanczosLobes * Math.Sin(px) * Math.Sin(px / LanczosLobes) / (px * px);
		}

		// For each output texel along one axis: the first source texel it covers and the share of each covered texel
		static (int[] Starts, float[][] Weights) BoxWeights(int src, int dst)
		{
			var starts = new int[dst];
			var weights = new float[dst][];
			var f = src / (double)dst;
			for (var i = 0; i < dst; i++)
			{
				var lo = i * f;
				var hi = Math.Min(src, (i + 1) * f);
				var first = (int)lo;
				var last = Math.Min(src - 1, (int)Math.Ceiling(hi) - 1);
				starts[i] = first;
				var w = new float[last - first + 1];
				for (var s = first; s <= last; s++)
					w[s - first] = (float)((Math.Min(hi, s + 1) - Math.Max(lo, s)) / f);

				weights[i] = w;
			}

			return (starts, weights);
		}

		static (int[] Starts, float[][] Weights) Weights(int src, int dst)
		{
			return Filter == SpriteDownscaleFilter.Lanczos ? LanczosWeights(src, dst) : BoxWeights(src, dst);
		}

		// For each output texel along one axis: the first source texel its filter touches and the (normalised) weight
		// of each touched texel. The filter is stretched by the shrink factor so it covers the whole source footprint.
		static (int[] Starts, float[][] Weights) LanczosWeights(int src, int dst)
		{
			var starts = new int[dst];
			var weights = new float[dst][];
			var f = src / (double)dst;
			var radius = LanczosLobes * f;
			for (var i = 0; i < dst; i++)
			{
				var centre = (i + 0.5) * f - 0.5;
				var first = Math.Max(0, (int)Math.Ceiling(centre - radius));
				var last = Math.Min(src - 1, (int)Math.Floor(centre + radius));
				var w = new float[last - first + 1];
				var sum = 0.0;
				for (var s = first; s <= last; s++)
				{
					var v = Lanczos((s - centre) / f);
					w[s - first] = (float)v;
					sum += v;
				}

				if (sum != 0)
					for (var k = 0; k < w.Length; k++)
						w[k] = (float)(w[k] / sum);

				starts[i] = first;
				weights[i] = w;
			}

			return (starts, weights);
		}

		// Fixed-point weights: 255 * 255 * (sum of |weights| < 1.3) * 4096 stays well inside an int
		const int WeightShift = 12;
		const int WeightOne = 1 << WeightShift;

		static int[][] ToFixed(float[][] weights)
		{
			var fixedWeights = new int[weights.Length][];
			for (var i = 0; i < weights.Length; i++)
			{
				var w = weights[i];
				var f = new int[w.Length];
				for (var k = 0; k < w.Length; k++)
					f[k] = (int)Math.Round(w[k] * WeightOne);

				fixedWeights[i] = f;
			}

			return fixedWeights;
		}

		static byte[] Resample(byte[] source, int stride, int sw, int sh, int dw, int dh)
		{
			var hasAlpha = stride == 4;
			var (xStarts, xWeightsF) = Weights(sw, dw);
			var (yStarts, yWeightsF) = Weights(sh, dh);
			var xWeights = ToFixed(xWeightsF);
			var yWeights = ToFixed(yWeightsF);

			// Pass 1: rows, into alpha-weighted (premultiplied) texels, 8 fractional bits
			var src = source.AsSpan();
			var rows = new int[sh * dw * 4];
			var rowSpan = rows.AsSpan();
			for (var y = 0; y < sh; y++)
			{
				var srcRow = src.Slice(y * sw * stride, sw * stride);
				var dstRow = rowSpan.Slice(y * dw * 4, dw * 4);
				for (var x = 0; x < dw; x++)
				{
					int c0 = 0, c1 = 0, c2 = 0, a = 0;
					var w = xWeights[x];
					var s = xStarts[x] * stride;
					if (hasAlpha)
					{
						for (var k = 0; k < w.Length; k++, s += stride)
						{
							// alpha * weight has 12 fractional bits; shift to 8 so colours fit in 32 bits
							var alpha = (srcRow[s + 3] * w[k]) >> 4;
							c0 += srcRow[s] * alpha;
							c1 += srcRow[s + 1] * alpha;
							c2 += srcRow[s + 2] * alpha;
							a += alpha;
						}
					}
					else
					{
						for (var k = 0; k < w.Length; k++, s += stride)
						{
							var alpha = (255 * w[k]) >> 4;
							c0 += srcRow[s] * alpha;
							c1 += srcRow[s + 1] * alpha;
							c2 += srcRow[s + 2] * alpha;
							a += alpha;
						}
					}

					var d = x * 4;
					dstRow[d] = c0;
					dstRow[d + 1] = c1;
					dstRow[d + 2] = c2;
					dstRow[d + 3] = a;
				}
			}

			// Pass 2: columns (weights shifted back out as we go), then back to straight alpha bytes
			var dst = new byte[dw * dh * stride];
			var rowStride = dw * 4;
			for (var y = 0; y < dh; y++)
			{
				var w = yWeights[y];
				var first = yStarts[y] * rowStride;
				for (var x = 0; x < dw; x++)
				{
					long c0 = 0, c1 = 0, c2 = 0, a = 0;
					var s = first + x * 4;
					for (var k = 0; k < w.Length; k++, s += rowStride)
					{
						c0 += (long)rowSpan[s] * w[k];
						c1 += (long)rowSpan[s + 1] * w[k];
						c2 += (long)rowSpan[s + 2] * w[k];
						a += (long)rowSpan[s + 3] * w[k];
					}

					var d = (y * dw + x) * stride;
					if (a > 0)
					{
						dst[d] = (byte)Math.Clamp((c0 + a / 2) / a, 0, 255);
						dst[d + 1] = (byte)Math.Clamp((c1 + a / 2) / a, 0, 255);
						dst[d + 2] = (byte)Math.Clamp((c2 + a / 2) / a, 0, 255);
					}

					if (hasAlpha)
					{
						// a carries 8 + 12 fractional bits
						var alpha = (a + (1 << 19)) >> 20;
						dst[d + 3] = (byte)Math.Clamp(alpha, 0, 255);
					}
				}
			}

			return dst;
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
		readonly Dictionary<(string Filename, bool Premultiplied, SpriteCropMode Crop, float Downscale), Sprite[]> files = new();

		public SharedSpriteStore(int bgraSheetSize, int indexedSheetSize)
		{
			SheetBuilders = SpriteCache.CreateSheetBuilders(bgraSheetSize, indexedSheetSize);
		}

		public bool TryGetFile(string filename, bool premultiplied, SpriteCropMode crop, float downscale, out Sprite[] sprites)
		{
			return files.TryGetValue((filename, premultiplied, crop, downscale), out sprites);
		}

		public Sprite[] GetOrAddFile(string filename, bool premultiplied, SpriteCropMode crop, float downscale, int frameCount)
		{
			return files.GetOrAdd((filename, premultiplied, crop, downscale), _ => new Sprite[frameCount]);
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
