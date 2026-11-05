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
using System.IO;
using System.Threading;
using OpenRA.Video;
using StbImageSharp;

namespace OpenRA.Mods.RAPX.VideoLoaders
{
	/// <summary>
	/// Loads .rpv videos: a sequence of JPEG frames plus raw PCM audio, produced from
	/// ordinary video files by tools/make-video.py.
	/// </summary>
	public class RpvLoader : IVideoLoader
	{
		public bool TryParseVideo(Stream s, bool useFramePadding, out IVideo video)
		{
			video = null;

			var start = s.Position;
			if (s.Length - start < 4 || s.ReadASCII(4) != RpvVideo.Magic)
			{
				s.Position = start;
				return false;
			}

			video = new RpvVideo(s, useFramePadding);
			return true;
		}
	}

	/// <summary>
	/// Layout (little endian): "RPXV", u16 width, u16 height, u16 frame count, u8 framerate,
	/// u8 audio channels, i32 sample rate, u8 sample bits, i32 audio length, audio PCM,
	/// then for each frame an i32 length followed by the JPEG data.
	/// </summary>
	/// <remarks>
	/// Frames are streamed from disk when the source is a file, and decoded ahead of playback on
	/// background threads: a 1080p JPEG takes ~40 ms to decode, too slow for the render thread and
	/// barely fast enough for a single worker.
	/// </remarks>
	public sealed class RpvVideo : IVideo
	{
		public const string Magic = "RPXV";

		const int Lookahead = 4;
		static readonly int WorkerCount = Math.Clamp(Environment.ProcessorCount - 2, 1, 3);

		public ushort FrameCount { get; }
		public byte Framerate { get; }
		public ushort Width { get; }
		public ushort Height { get; }

		public int CurrentFrameIndex { get; private set; }

		public bool HasAudio => AudioData.Length > 0;
		public byte[] AudioData { get; }
		public int AudioChannels { get; }
		public int SampleBits { get; }
		public int SampleRate { get; }

		// JPEG data in memory, or its location in the file when streaming
		readonly byte[][] frames;
		readonly long[] offsets;
		readonly int[] lengths;
		readonly string path;

		readonly int stride;
		readonly int frameSize;

		// Shared with the decoder threads, guarded by sync
		readonly object sync = new();
		readonly Dictionary<int, byte[]> ready = new();
		readonly Stack<byte[]> pool = new();
		readonly List<int> stale = new();
		int workers;
		int inFlight;
		int wanted;
		int nextToDecode;

		byte[] shown;
		int shownIndex = -1;

		public RpvVideo(Stream s, bool useFramePadding)
		{
			Width = s.ReadUInt16();
			Height = s.ReadUInt16();
			FrameCount = s.ReadUInt16();
			Framerate = s.ReadUInt8();
			AudioChannels = s.ReadUInt8();
			SampleRate = s.ReadInt32();
			SampleBits = s.ReadUInt8();
			AudioData = s.ReadBytes(s.ReadInt32());

			if (s is FileStream file)
			{
				path = file.Name;
				offsets = new long[FrameCount];
				lengths = new int[FrameCount];
				for (var i = 0; i < FrameCount; i++)
				{
					lengths[i] = s.ReadInt32();
					offsets[i] = s.Position;
					s.Seek(lengths[i], SeekOrigin.Current);
				}
			}
			else
			{
				frames = new byte[FrameCount][];
				for (var i = 0; i < FrameCount; i++)
					frames[i] = s.ReadBytes(s.ReadInt32());
			}

			stride = useFramePadding ? Exts.NextPowerOf2(Width) : Width;
			var rows = useFramePadding ? Exts.NextPowerOf2(Height) : Height;
			frameSize = 4 * stride * rows;
			shown = new byte[frameSize];
		}

		/// <summary>
		/// The newest decoded frame that is not ahead of playback: when the decoders fall behind,
		/// the video drops frames instead of freezing.
		/// </summary>
		public byte[] CurrentFrameData
		{
			get
			{
				var index = Math.Min(CurrentFrameIndex, FrameCount - 1);
				if (FrameCount == 0 || index == shownIndex)
					return shown;

				lock (sync)
				{
					wanted = index;
					for (; workers < WorkerCount && nextToDecode < FrameCount; workers++)
						new Thread(DecodeLoop) { Name = "RPV decoder", IsBackground = true }.Start();

					Monitor.PulseAll(sync);

					// Nothing is on screen yet, so the first frame is worth waiting for
					while (shownIndex < 0 && NewestReady(index) < 0)
						Monitor.Wait(sync);

					var best = NewestReady(index);
					if (best > shownIndex)
					{
						pool.Push(shown);
						shown = ready[best];
						ready.Remove(best);
						shownIndex = best;
					}

					// Recycle frames that playback has moved past
					stale.Clear();
					foreach (var k in ready.Keys)
						if (k <= index)
							stale.Add(k);

					foreach (var k in stale)
					{
						pool.Push(ready[k]);
						ready.Remove(k);
					}

					Monitor.PulseAll(sync);
				}

				return shown;
			}
		}

		public void AdvanceFrame()
		{
			if (CurrentFrameIndex < FrameCount)
				CurrentFrameIndex++;
		}

		public void Reset()
		{
			CurrentFrameIndex = 0;
			lock (sync)
			{
				wanted = 0;
				nextToDecode = 0;
				shownIndex = -1;
				foreach (var buffer in ready.Values)
					pool.Push(buffer);

				ready.Clear();
				Monitor.PulseAll(sync);
			}
		}

		int NewestReady(int index)
		{
			var best = -1;
			foreach (var k in ready.Keys)
				if (k <= index && k > best)
					best = k;

			return best;
		}

		void DecodeLoop()
		{
			var file = path != null ? new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read) : null;
			try
			{
				while (true)
				{
					int index;
					byte[] buffer;
					lock (sync)
					{
						nextToDecode = Math.Max(nextToDecode, wanted);

						// Done: let the thread end (and its file close); playback or a Reset starts new ones
						if (nextToDecode >= FrameCount)
						{
							workers--;
							return;
						}

						if (ready.Count + inFlight >= Lookahead)
						{
							Monitor.Wait(sync);
							continue;
						}

						index = nextToDecode++;
						inFlight++;
						buffer = pool.Count > 0 ? pool.Pop() : new byte[frameSize];
					}

					DecodeFrame(ReadFrame(file, index), buffer);

					lock (sync)
					{
						inFlight--;
						if (index > shownIndex)
							ready[index] = buffer;
						else
							pool.Push(buffer);

						Monitor.PulseAll(sync);
					}
				}
			}
			finally
			{
				file?.Dispose();
			}
		}

		byte[] ReadFrame(FileStream file, int index)
		{
			if (frames != null)
				return frames[index];

			file.Position = offsets[index];
			return file.ReadBytes(lengths[index]);
		}

		void DecodeFrame(byte[] jpeg, byte[] frameData)
		{
			var image = ImageResult.FromMemory(jpeg, ColorComponents.RedGreenBlueAlpha);
			var src = image.Data;
			var w = Math.Min(image.Width, Width);
			var h = Math.Min(image.Height, Height);

			// RGBA -> BGRA, into the (possibly padded) frame buffer
			for (var y = 0; y < h; y++)
			{
				var si = 4 * y * image.Width;
				var di = 4 * y * stride;
				for (var x = 0; x < w; x++, si += 4, di += 4)
				{
					frameData[di] = src[si + 2];
					frameData[di + 1] = src[si + 1];
					frameData[di + 2] = src[si];
					frameData[di + 3] = 255;
				}
			}
		}
	}
}
