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
using OpenRA.FileSystem;
using OpenRA.Network;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Graphics
{
	public interface ISpriteSequence
	{
		string Name { get; }
		int Length { get; }
		int Facings { get; }
		int Tick { get; }
		int ZOffset { get; }
		int ShadowZOffset { get; }
		Rectangle Bounds { get; }
		bool IgnoreWorldTint { get; }
		float Scale { get; }
		void ResolveSprites(SpriteCache cache);
		Sprite GetSprite(int frame);
		Sprite GetSprite(int frame, WAngle facing);
		(Sprite Sprite, WAngle Rotation) GetSpriteWithRotation(int frame, WAngle facing);
		Sprite GetShadow(int frame, WAngle facing);
		float GetAlpha(int frame);

		/// <summary>RAPX: the sprite cache reservations ResolveSprites needs, so a deferred sequence can load on its own
		/// (SequenceSet.GetSequence). Null: unknown, the whole image loads.</summary>
		IEnumerable<int> ReservationTokens => null;
	}

	public interface ISpriteSequenceLoader
	{
		int BgraSheetSize { get; }
		int IndexedSheetSize { get; }
		IReadOnlyDictionary<string, ISpriteSequence> ParseSequences(ModData modData, string tileSet, SpriteCache cache, MiniYamlNode node);
	}

	/// <summary>
	/// RAPX: on the world actor, picks the images a newly loaded map may leave unloaded until something first asks for
	/// them (SequenceSet.GetSequence loads them then), e.g. other nations' units in a skirmish. Null: load everything.
	/// </summary>
	public interface ISpriteLoadPolicyInfo : ITraitInfoInterface
	{
		Func<string, bool> DeferredImages(ModData modData, Map map, WorldType type, Session lobbyInfo);
	}

	public sealed class SequenceSet : IDisposable
	{
		readonly ModData modData;
		readonly string tileSet;
		readonly IReadOnlyDictionary<string, IReadOnlyDictionary<string, ISpriteSequence>> images;
		public SpriteCache SpriteCache { get; }

		// RAPX: the sprite reservations each image made ([First, End) tokens), images still to load on first use, and the
		// background loader filling the shared store for later maps
		readonly Dictionary<string, (int First, int End)> imageTokens = new();
		HashSet<string> deferredImages;
		SpriteCache.Prefetcher prefetcher;

		public SequenceSet(IReadOnlyFileSystem fileSystem, ModData modData, string tileSet, MiniYaml additionalSequences,
			SharedSpriteStore sharedSprites = null, Func<string, bool> canShareFile = null)
		{
			this.modData = modData;
			this.tileSet = tileSet;
			SpriteCache = new SpriteCache(fileSystem, modData.SpriteLoaders, modData.SpriteSequenceLoader.BgraSheetSize, modData.SpriteSequenceLoader.IndexedSheetSize,
				shared: sharedSprites, canShare: canShareFile);
			using (new Support.PerfTimer("LoadSequences"))
				images = Load(fileSystem, additionalSequences);
		}

		public ISpriteSequence GetSequence(string image, string sequence)
		{
			if (!images.TryGetValue(image, out var sequences))
				throw new InvalidOperationException($"Image `{image}` does not have any sequences defined.");

			if (!sequences.TryGetValue(sequence, out var seq))
				throw new InvalidOperationException($"Image `{image}` does not have a sequence named `{sequence}`.");

			if (deferredImages != null && deferredImages.Contains(image) && !loadedSequences.Contains(seq))
				LoadSequence(image, seq);

			return seq;
		}

		public IEnumerable<string> Images => images.Keys;

		public bool HasSequence(string image, string sequence)
		{
			if (!images.TryGetValue(image, out var sequences))
				throw new InvalidOperationException($"Image `{image}` does not have any sequences defined.");

			return sequences.ContainsKey(sequence);
		}

		public IEnumerable<string> Sequences(string image)
		{
			if (!images.TryGetValue(image, out var sequences))
				throw new InvalidOperationException($"Image `{image}` does not have any sequences defined.");

			return sequences.Keys;
		}

		IReadOnlyDictionary<string, IReadOnlyDictionary<string, ISpriteSequence>> Load(IReadOnlyFileSystem fileSystem, MiniYaml additionalSequences)
		{
			var nodes = MiniYaml.Load(fileSystem, modData.Manifest.Sequences, additionalSequences);
			var images = new Dictionary<string, IReadOnlyDictionary<string, ISpriteSequence>>();
			foreach (var node in nodes)
			{
				// Nodes starting with ^ are inheritable but never loaded directly
				if (node.Key.StartsWith(ActorInfo.AbstractActorPrefix))
					continue;

				var first = SpriteCache.NextReservationToken;
				images[node.Key] = modData.SpriteSequenceLoader.ParseSequences(modData, tileSet, SpriteCache, node);
				imageTokens[node.Key] = (first, SpriteCache.NextReservationToken);
			}

			return images;
		}

		public void LoadSprites()
		{
			LoadSprites(null);
		}

		/// <summary>
		/// RAPX: loads the sprites of every image except those <paramref name="defer"/> picks, which load when something
		/// first asks for them (or in the background, see <see cref="Prefetch"/>). Null loads everything.
		/// </summary>
		public void LoadSprites(Func<string, bool> defer)
		{
			if (defer == null)
			{
				SpriteCache.LoadReservations(modData);
				foreach (var sequences in images.Values)
					foreach (var sequence in sequences)
						sequence.Value.ResolveSprites(SpriteCache);

				return;
			}

			deferredImages = images.Keys.Where(defer).ToHashSet();

			// A missing file still fails the map load right away, as it did when every image loaded up front
			foreach (var (filename, location) in SpriteCache.ReservedFiles())
				if (!SpriteCache.FileExists(filename))
					throw new System.IO.FileNotFoundException($"{location}: {filename} not found", filename);

			var now = new HashSet<int>();
			foreach (var (image, (first, end)) in imageTokens)
				if (!deferredImages.Contains(image))
					for (var t = first; t < end; t++)
						now.Add(t);

			SpriteCache.LoadReservations(modData, now);
			foreach (var (image, sequences) in images)
				if (!deferredImages.Contains(image))
					foreach (var sequence in sequences)
						sequence.Value.ResolveSprites(SpriteCache);

			Log.Write("perf", $"SequenceSet: {deferredImages.Count} of {images.Count} images load on first use");
		}

		// Sequences of deferred images loaded on their own so far (an image leaves deferredImages once all are)
		readonly HashSet<ISpriteSequence> loadedSequences = new();

		/// <summary>Loads one sequence of a deferred image when something first asks for it (e.g. only the sidebar icon), or
		/// the whole image when the sequence cannot say which reservations it needs. The sheets keep their buffers and
		/// reach the GPU when next drawn, so many small loads cost one upload.</summary>
		void LoadSequence(string image, ISpriteSequence sequence)
		{
			var clock = System.Diagnostics.Stopwatch.StartNew();
			var tokens = sequence.ReservationTokens?.ToHashSet();
			var all = images[image].Values;
			if (tokens == null)
			{
				var (first, end) = imageTokens[image];
				tokens = Enumerable.Range(first, end - first).ToHashSet();
				SpriteCache.LoadReservations(modData, tokens, false);
				foreach (var s in all)
				{
					s.ResolveSprites(SpriteCache);
					loadedSequences.Add(s);
				}
			}
			else
			{
				SpriteCache.LoadReservations(modData, tokens, false);
				sequence.ResolveSprites(SpriteCache);
				loadedSequences.Add(sequence);
			}

			if (all.All(loadedSequences.Contains))
			{
				deferredImages.Remove(image);
				foreach (var s in all)
					loadedSequences.Remove(s);
			}

			Log.Write("perf", $"SequenceSet: loaded `{image}.{sequence.Name}` on first use in {clock.ElapsedMilliseconds} ms");
		}

		/// <summary>RAPX: images still waiting to load on first use.</summary>
		public IReadOnlyCollection<string> DeferredImages => (IReadOnlyCollection<string>)deferredImages ?? Array.Empty<string>();

		/// <summary>
		/// RAPX: starts (or extends) loading these deferred images' files into the shared sprite store on background
		/// threads, so maps loaded after this one find them ready. Call <see cref="PrefetchStep"/> regularly to pack them.
		/// </summary>
		public void Prefetch(IEnumerable<string> imageNames, int threads)
		{
			if (deferredImages == null)
				return;

			var tokens = new List<int>();
			foreach (var image in imageNames)
				if (deferredImages.Contains(image) && imageTokens.TryGetValue(image, out var range))
					for (var t = range.First; t < range.End; t++)
						tokens.Add(t);

			if (tokens.Count == 0)
				return;

			prefetcher ??= SpriteCache.StartPrefetch(threads);
			prefetcher.Queue(modData, tokens);
		}

		/// <summary>RAPX: packs prefetched sprites for up to <paramref name="budgetMs"/> milliseconds. True while work remains.</summary>
		public bool PrefetchStep(double budgetMs)
		{
			return prefetcher != null && prefetcher.Step(budgetMs);
		}

		/// <summary>RAPX: files prefetched so far, and queued in all.</summary>
		public (int Packed, int Queued) PrefetchProgress => prefetcher != null ? (prefetcher.Packed, prefetcher.Queued) : (0, 0);

		public void Dispose()
		{
			prefetcher?.Stop(modData);
			prefetcher = null;
			SpriteCache.Dispose();
		}
	}
}
