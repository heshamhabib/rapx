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
using OpenRA.FileFormats;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Terrain;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World | SystemActors.EditorWorld)]
	[Desc("Draws HD art (artsrc/env/make_tiles.py) over classic terrain tiles that have it: bridges, fords, debris.",
		"One image per tile template, cut into its cells; drawn after the HD terrain pass, below smudges, ore and actors,",
		"and redrawn when tiles change (e.g. a bridge is destroyed).")]
	public class PxHDTilesInfo : TraitInfo
	{
		[Desc("Folder with one subfolder per tileset (lower case id) holding <template image>.png files.")]
		public readonly string Folder = "ra|bits/hd/tiles";

		[Desc("HD pixels per map cell.")]
		public readonly int CellSize = 72;

		public override object Create(ActorInitializer init) { return new PxHDTiles(init.World, this); }
	}

	public sealed class PxHDTiles : IWorldLoaded, IRenderOverlay, INotifyActorDisposing
	{
		const int EdgePadding = 2;

		readonly PxHDTilesInfo info;
		readonly Map map;

		// Template id -> one sprite per template cell (null where the template has no HD art)
		readonly Dictionary<ushort, Sprite[]> templates = new();
		readonly HashSet<ushort> missing = new();
		SheetBuilder sheetBuilder;
		TerrainSpriteLayer layer;
		bool disabled;

		public PxHDTiles(World world, PxHDTilesInfo info)
		{
			this.info = info;
			map = world.Map;

			// RAPX_NO_HD_TILES disables the effect for before/after comparisons
			disabled = !string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("RAPX_NO_HD_TILES"));
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			// A painted backdrop (PxMapBackdrop) replaces the whole terrain picture
			var backdrop = w.WorldActor.TraitOrDefault<PxMapBackdrop>();
			if (disabled || map.Rules.TerrainInfo is not ITemplatedTerrainInfo || (backdrop != null && backdrop.Active))
			{
				disabled = true;
				return;
			}

			sheetBuilder = new SheetBuilder(SheetType.BGRA);
			var empty = sheetBuilder.Add(new byte[4], SpriteFrameType.Rgba32, new Size(1, 1));
			layer = new TerrainSpriteLayer(w, wr, empty, BlendMode.Alpha, false);

			foreach (var cell in map.AllCells)
				UpdateCell(cell);

			map.Tiles.CellEntryChanged += UpdateCell;
		}

		Sprite[] TemplateSprites(ushort id)
		{
			if (templates.TryGetValue(id, out var sprites))
				return sprites;

			if (missing.Contains(id))
				return null;

			var terrain = (ITemplatedTerrainInfo)map.Rules.TerrainInfo;
			if (!terrain.Templates.TryGetValue(id, out var template) || template is not DefaultTerrainTemplateInfo t ||
				t.Images == null || t.Images.Length == 0 || t.PickAny)
			{
				missing.Add(id);
				return null;
			}

			var stem = System.IO.Path.GetFileNameWithoutExtension(t.Images[0]);
			var path = $"{info.Folder}/{map.Tileset.ToLowerInvariant()}/{stem}.png";
			var fs = Game.ModData.DefaultFileSystem;
			if (!fs.Exists(path))
			{
				missing.Add(id);
				return null;
			}

			Png png;
			using (var stream = fs.Open(path))
				png = new Png(stream);

			if (png.Width != template.Size.X * info.CellSize || png.Height != template.Size.Y * info.CellSize)
			{
				Log.Write("debug", $"PxHDTiles: {path} is {png.Width}x{png.Height}, expected {template.Size.X * info.CellSize}x{template.Size.Y * info.CellSize}");
				missing.Add(id);
				return null;
			}

			// The whole template goes into the sheet in one piece, so neighbouring cells sample each other at their
			// shared edge (no seams); each cell is a sub-sprite of it. The template's outer edge is extruded by
			// EdgePadding pixels: filtered sampling at that edge then reads the template's own edge pixels instead of
			// the empty sheet or another template next to it (which showed as hairlines between templates).
			const int Pad = EdgePadding;
			var whole = sheetBuilder.Add(Extrude(png.Data, png.Width, png.Height, Pad), png.Type,
				new Size(png.Width + 2 * Pad, png.Height + 2 * Pad));
			sprites = new Sprite[template.Size.X * template.Size.Y];
			for (var i = 0; i < sprites.Length; i++)
			{
				var x = whole.Bounds.X + Pad + i % template.Size.X * info.CellSize;
				var y = whole.Bounds.Y + Pad + i / template.Size.X * info.CellSize;
				sprites[i] = new Sprite(whole.Sheet, new Rectangle(x, y, info.CellSize, info.CellSize), whole.Channel);
			}

			templates[id] = sprites;
			return sprites;
		}

		/// <summary>Copies an image into a larger one with its border pixels repeated `pad` times on every side.</summary>
		static byte[] Extrude(byte[] data, int width, int height, int pad)
		{
			var bpp = data.Length / (width * height);
			var w = width + 2 * pad;
			var h = height + 2 * pad;
			var output = new byte[w * h * bpp];
			for (var y = 0; y < h; y++)
			{
				var sy = Math.Clamp(y - pad, 0, height - 1);
				for (var x = 0; x < w; x++)
				{
					var sx = Math.Clamp(x - pad, 0, width - 1);
					Buffer.BlockCopy(data, (sy * width + sx) * bpp, output, (y * w + x) * bpp, bpp);
				}
			}

			return output;
		}

		/// <summary>The HD art for one cell of a template, or null when there is none.</summary>
		public Sprite CellSprite(ushort template, int index)
		{
			if (disabled || sheetBuilder == null)
				return null;

			var sprites = TemplateSprites(template);
			return sprites != null && index >= 0 && index < sprites.Length ? sprites[index] : null;
		}

		public float CellScale => 24f / info.CellSize;

		void UpdateCell(CPos cell)
		{
			if (!map.Tiles.Contains(cell))
				return;

			var tile = map.Tiles[cell];
			var sprites = TemplateSprites(tile.Type);
			var sprite = sprites != null && tile.Index < sprites.Length ? sprites[tile.Index] : null;
			layer.Update(cell, sprite, null, 24f / info.CellSize);
		}

		void IRenderOverlay.Render(WorldRenderer wr)
		{
			if (!disabled)
				layer.Draw(wr.Viewport);
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			if (!disabled)
				map.Tiles.CellEntryChanged -= UpdateCell;

			layer?.Dispose();
			sheetBuilder?.Dispose();
		}
	}
}
