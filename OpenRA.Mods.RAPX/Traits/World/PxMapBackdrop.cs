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
using System.IO;
using System.Threading.Tasks;
using OpenRA.FileFormats;
using OpenRA.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World | SystemActors.EditorWorld)]
	[Desc("Draws a painted backdrop (one unique pre-rendered picture of the whole map, IDEA-28) instead of the terrain tiles.",
		"The picture ships inside the map package as chunks <Prefix>-<column>-<row>.png, each ChunkCells x ChunkCells cells",
		"of the map's playable area. Maps without the chunks keep their tiles. Drawn below smudges, ore and actors;",
		"the tiles still decide where units can move.")]
	public class PxMapBackdropInfo : TraitInfo
	{
		[Desc("File name prefix of the chunks in the map package.")]
		public readonly string Prefix = "backdrop";

		[Desc("Backdrop pixels per map cell. Chunks must be power-of-two textures: 64 px x 16 cells = 1024 px.")]
		public readonly int CellSize = 64;

		[Desc("Map cells per chunk side.")]
		public readonly int ChunkCells = 16;

		public override object Create(ActorInitializer init) { return new PxMapBackdrop(init.World, this); }
	}

	public sealed class PxMapBackdrop : IWorldLoaded, IRenderOverlay, INotifyActorDisposing
	{
		// TerrainSpriteLayer can draw from SpriteRenderer.SheetCount sheets; one of them holds the empty sprite
		const int ChunksPerLayer = SpriteRenderer.SheetCount - 1;

		readonly PxMapBackdropInfo info;
		readonly Map map;
		readonly List<Sheet> sheets = new();
		readonly List<TerrainSpriteLayer> layers = new();
		Sheet emptySheet;

		/// <summary>True when this map has a backdrop; other terrain overlays (HD tiles) stay hidden under it.</summary>
		public bool Active { get; }

		public PxMapBackdrop(World world, PxMapBackdropInfo info)
		{
			this.info = info;
			map = world.Map;

			// RAPX_NO_BACKDROP shows the plain tiles, for before/after comparisons and checking the gameplay cells
			Active = string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("RAPX_NO_BACKDROP")) &&
				map.Package != null && map.Package.Contains(ChunkName(0, 0));
		}

		string ChunkName(int column, int row) => $"{info.Prefix}-{column}-{row}.png";

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			if (!Active)
				return;

			emptySheet = new Sheet(SheetType.BGRA, new Size(1, 1));
			var empty = new Sprite(emptySheet, new Rectangle(0, 0, 1, 1), TextureChannel.RGBA);
			var bounds = map.Bounds;
			var scale = (float)map.Grid.TileSize.Width / info.CellSize;
			var columns = (bounds.Width + info.ChunkCells - 1) / info.ChunkCells;
			var rows = (bounds.Height + info.ChunkCells - 1) / info.ChunkCells;

			// Read the chunks in order (map packages are not thread safe), decode them in parallel,
			// then upload them here on the render thread
			var chunks = new List<(int Column, int Row, byte[] Data)>();
			for (var row = 0; row < rows; row++)
			{
				for (var column = 0; column < columns; column++)
				{
					var name = ChunkName(column, row);
					if (!map.Package.Contains(name))
					{
						Log.Write("debug", $"PxMapBackdrop: {map.Title} has no {name}");
						continue;
					}

					using (var stream = map.Package.GetStream(name))
						chunks.Add((column, row, stream.ReadAllBytes()));
				}
			}

			var decoded = new Sheet[chunks.Count];
			var parallel = new ParallelOptions { MaxDegreeOfParallelism = System.Math.Max(1, System.Environment.ProcessorCount - 1) };
			Parallel.For(0, chunks.Count, parallel, i =>
			{
				using var stream = new MemoryStream(chunks[i].Data, false);
				var png = new Png(stream);
				var chunk = new Sheet(SheetType.BGRA, new Size(png.Width, png.Height));
				Util.FastCopyIntoSprite(new Sprite(chunk, new Rectangle(0, 0, png.Width, png.Height), TextureChannel.Red), png);
				decoded[i] = chunk;
			});

			TerrainSpriteLayer layer = null;
			for (var i = 0; i < chunks.Count; i++)
			{
				var (column, row, _) = chunks[i];
				var sheet = decoded[i];
				sheet.ScaleFilter = TextureScaleFilter.Linear;
				sheet.ReleaseBuffer();
				sheets.Add(sheet);

				if (layer == null || sheets.Count % ChunksPerLayer == 1)
				{
					layer = new TerrainSpriteLayer(w, wr, empty, BlendMode.Alpha, true);
					layers.Add(layer);
				}

				// Each cell is a sub-sprite of its chunk; the chunk's own sheet clamps at its edges, so there are no seams
				var cellsX = System.Math.Min(info.ChunkCells, sheet.Size.Width / info.CellSize);
				var cellsY = System.Math.Min(info.ChunkCells, sheet.Size.Height / info.CellSize);
				for (var y = 0; y < cellsY; y++)
				{
					for (var x = 0; x < cellsX; x++)
					{
						var cell = new MPos(bounds.X + column * info.ChunkCells + x, bounds.Y + row * info.ChunkCells + y).ToCPos(map);
						if (!map.Contains(cell))
							continue;

						var sprite = new Sprite(sheet, new Rectangle(x * info.CellSize, y * info.CellSize, info.CellSize, info.CellSize),
							TextureChannel.RGBA);
						layer.Update(cell, sprite, null, scale);
					}
				}
			}
		}

		void IRenderOverlay.Render(WorldRenderer wr)
		{
			foreach (var layer in layers)
				layer.Draw(wr.Viewport);
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			foreach (var layer in layers)
				layer.Dispose();

			foreach (var sheet in sheets)
				sheet.Dispose();

			emptySheet?.Dispose();
			layers.Clear();
			sheets.Clear();
		}
	}
}
