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
using OpenRA.FileFormats;
using OpenRA.FileSystem;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World | SystemActors.EditorWorld)]
	[Desc("Re-renders the classic terrain with high resolution photo textures (grass, dirt, rock, rough ground, beach,",
		"animated water) after it is drawn.")]
	public class TerrainDetailTexturesInfo : TraitInfo
	{
		[FieldLoader.Require]
		[Desc("Tilesets the effect applies to (its colour classification is tuned per palette).")]
		public readonly HashSet<string> Tilesets = new();

		[FieldLoader.Require]
		public readonly string Grass = null;

		[FieldLoader.Require]
		public readonly string Dirt = null;

		[FieldLoader.Require]
		public readonly string Rock = null;

		[Desc("Optional textures for cells whose terrain type is in RoughTypes / BeachTypes / WaterTypes / RiverTypes.",
			"Rough and beach replace the land materials there; water and river replace the water pixels (animated).",
			"Without Water the classic (palette animated) water is kept.")]
		public readonly string Rough = null;
		public readonly string Beach = null;
		public readonly string Water = null;
		public readonly string River = null;

		public readonly HashSet<string> RoughTypes = new() { "Rough" };
		public readonly HashSet<string> BeachTypes = new() { "Beach" };
		public readonly HashSet<string> WaterTypes = new() { "Water", "Bridge" };
		public readonly HashSet<string> RiverTypes = new() { "River" };

		[Desc("World pixels covered by one repeat of each texture.")]
		public readonly float GrassRepeat = 96;
		public readonly float DirtRepeat = 120;
		public readonly float RockRepeat = 96;
		public readonly float RoughRepeat = 96;
		public readonly float BeachRepeat = 120;
		public readonly float WaterRepeat = 192;
		public readonly float RiverRepeat = 144;

		[Desc("World pixels per second the water textures drift.")]
		public readonly float WaterFlow = 6f;

		[Desc("How much of the classic water's light and dark detail (waves, foam, palette shimmer) shows on the HD water (0-1).")]
		public readonly float WaterDetail = 0.45f;

		[Desc("Cliffs: 0 = classic cliff art with texture grain, 1 = the HD cliff texture lit by the classic light and",
			"dark faces (keeps the cliff's shape, loses the classic pixels).")]
		public readonly float RockDetail = 0.8f;

		[Desc("Mean luminance of the classic cliff colour (used to light the HD cliff texture). When RockColors are",
			"given, their mean is used instead.")]
		public readonly float RockLum = 0.42f;

		[Desc("Brightness of the twinkling sun glints on HD water (0 = none).")]
		public readonly float WaterGlints = 0.7f;

		[Desc("How much the water and river textures are recoloured towards WaterTintColor (0 = texture colour).")]
		public readonly float WaterTint = 0f;
		public readonly Color WaterTintColor = Color.FromArgb(112, 134, 140);

		[Desc("How much of the classic terrain's large scale light and shadow is kept on grass (0-1).")]
		public readonly float ShadeStrength = 0.7f;

		[Desc("Mean luminance of the classic ground (grass) colour; grass brighter or darker than this is shaded.")]
		public readonly float GroundLum = 0.205f;

		[Desc("Classic terrain colours that mean grass (ground), dirt (roads), rock (cliffs) and water.",
			"When none are given, pixels are classified with the temperate rules (green = grass, bright = rock).",
			"Otherwise each pixel takes the class of its nearest reference colours (at most 8 in total).")]
		public readonly Color[] GroundColors = System.Array.Empty<Color>();
		public readonly Color[] DirtColors = System.Array.Empty<Color>();
		public readonly Color[] RockColors = System.Array.Empty<Color>();
		public readonly Color[] WaterColors = System.Array.Empty<Color>();

		[Desc("Colour distance over which two reference colours blend (0-1 RGB units).")]
		public readonly float Softness = 0.05f;

		[Desc("How much the grass texture is recoloured to the mean of the GroundColors (0 = texture colour).")]
		public readonly float GroundTint = 0f;

		[Desc("World pixels by which the border between ground and dirt is wobbled, so blocky classic road and sand",
			"tile layouts get organic edges instead of square cell outlines (0 = follow the classic cells).")]
		public readonly float EdgeWarp = 0f;

		public readonly string VertexShader = "terrain_detail.vert";
		public readonly string FragmentShader = "terrain_detail.frag";

		public override object Create(ActorInitializer init) { return new TerrainDetailTextures(init.World, this); }
	}

	public sealed class TerrainDetailTextures : IRenderPostProcessPass, INotifyActorDisposing
	{
		const int MaxReferences = 8;

		readonly TerrainDetailTexturesInfo info;
		readonly IShader shader;
		readonly IVertexBuffer<RenderPostProcessPassVertex> buffer;

		// grass, dirt, rock, rough, beach, water, river
		readonly ITexture[] textures = new ITexture[7];
		readonly float[] meanLum = new float[7];
		readonly float3[] meanColor = new float3[7];
		readonly float[][] references = new float[MaxReferences][];
		readonly Map map;
		bool cellMapDirty = true;

		// The world actor is still being built in the constructor, so the shroud renderer is found on first draw
		PxShroudRenderer shroudRenderer;
		bool shroudResolved;

		/// <summary>Per-cell (rough, beach, water, river) texture, read as .bgra; null until the first draw. Used by PxWeatherGround.</summary>
		public bool Active { get; }
		public ITexture CellMap { get; private set; }
		public Size CellMapSize { get; private set; }

		public TerrainDetailTextures(World world, TerrainDetailTexturesInfo info)
		{
			this.info = info;

			// RAPX_NO_TERRAIN_DETAIL disables the effect for before/after comparisons
			Active = info.Tilesets.Contains(world.Map.Tileset) &&
				string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("RAPX_NO_TERRAIN_DETAIL"));
			if (!Active)
				return;

			var fileSystem = Game.ModData.DefaultFileSystem;

			// Missing optional textures fall back: rough -> grass, beach -> dirt, river -> water
			var paths = new[]
			{
				info.Grass, info.Dirt, info.Rock, info.Rough ?? info.Grass, info.Beach ?? info.Dirt,
				info.Water ?? info.Grass, info.River ?? info.Water ?? info.Grass
			};
			for (var i = 0; i < paths.Length; i++)
				textures[i] = LoadTexture(fileSystem, paths[i], out meanLum[i], out meanColor[i]);

			map = world.Map;
			map.Tiles.CellEntryChanged += _ => cellMapDirty = true;

			// Reference colours as (r, g, b, class); class -1 marks an unused slot
			var classes = new[] { info.GroundColors, info.DirtColors, info.RockColors, info.WaterColors };
			var n = 0;
			for (var c = 0; c < classes.Length; c++)
			{
				foreach (var color in classes[c])
				{
					if (n == MaxReferences)
						throw new YamlException($"TerrainDetailTextures supports at most {MaxReferences} reference colours.");

					references[n++] = new[] { color.R / 255f, color.G / 255f, color.B / 255f, c };
				}
			}

			for (; n < MaxReferences; n++)
				references[n] = new[] { 0f, 0f, 0f, -1f };

			shader = Game.Renderer.CreateShader(new ModShaderBindings(fileSystem, info.VertexShader, info.FragmentShader,
				new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 2, 0)));

			var vertices = new RenderPostProcessPassVertex[]
			{
				new(-1, -1), new(1, -1), new(1, 1),
				new(1, 1), new(-1, 1), new(-1, -1)
			};

			buffer = Game.Renderer.CreateVertexBuffer<RenderPostProcessPassVertex>(6);
			buffer.SetData(ref vertices, 6);
		}

		static ITexture LoadTexture(IReadOnlyFileSystem fileSystem, string path, out float meanLuminance, out float3 meanRgb)
		{
			Png png;
			using (var stream = fileSystem.Open(path))
				png = new Png(stream);

			if (png.Type != SpriteFrameType.Rgba32 && png.Type != SpriteFrameType.Rgb24)
				throw new InvalidDataException($"{path} must be an RGB or RGBA png.");

			// Convert to the BGRA layout expected by the texture upload
			var stride = png.PixelStride;
			var data = new byte[4 * png.Width * png.Height];
			double sum = 0, sumR = 0, sumG = 0, sumB = 0;
			for (int i = 0, j = 0; i < data.Length; i += 4, j += stride)
			{
				data[i] = png.Data[j + 2];
				data[i + 1] = png.Data[j + 1];
				data[i + 2] = png.Data[j];
				data[i + 3] = 255;
				sum += 0.299 * png.Data[j] + 0.587 * png.Data[j + 1] + 0.114 * png.Data[j + 2];
				sumR += png.Data[j];
				sumG += png.Data[j + 1];
				sumB += png.Data[j + 2];
			}

			var count = png.Width * png.Height * 255.0;
			meanLuminance = (float)(sum / count);
			meanRgb = new float3((float)(sumR / count), (float)(sumG / count), (float)(sumB / count));

			var texture = Game.Renderer.CreateTexture();
			texture.ScaleFilter = TextureScaleFilter.Trilinear;
			texture.SetData(data, png.Width, png.Height);
			return texture;
		}

		// One texel per map cell: (rough, beach, water, river) membership of its terrain type, sampled with linear
		// filtering so the materials blend across cell borders. Power-of-two sized; the shader scales by CellMapSize.
		void UpdateCellMap()
		{
			cellMapDirty = false;
			var w = Exts.NextPowerOf2(map.MapSize.X);
			var h = Exts.NextPowerOf2(map.MapSize.Y);
			CellMapSize = new Size(w, h);
			var data = new byte[4 * w * h];
			var terrain = map.Rules.TerrainInfo;
			var sets = new[]
			{
				info.Rough != null ? info.RoughTypes : null, info.Beach != null ? info.BeachTypes : null,
				info.Water != null ? info.WaterTypes : null, info.Water != null ? info.RiverTypes : null
			};

			// BGRA byte order: blue = rough, green = beach, red = water, alpha = river (read as .bgra in the shader)
			for (var y = 0; y < map.MapSize.Y; y++)
			{
				for (var x = 0; x < map.MapSize.X; x++)
				{
					var cell = new CPos(x, y);
					if (!terrain.TryGetTerrainInfo(map.Tiles[cell], out var tile))
						continue;

					var type = terrain.TerrainTypes[tile.TerrainType].Type;
					for (var k = 0; k < sets.Length; k++)
						if (sets[k] != null && sets[k].Contains(type))
							data[4 * (y * w + x) + k] = 255;
				}
			}

			CellMap ??= Game.Renderer.CreateTexture();
			CellMap.ScaleFilter = TextureScaleFilter.Linear;
			CellMap.SetData(data, w, h);
		}

		PostProcessPassType IRenderPostProcessPass.Type => PostProcessPassType.AfterTerrain;
		bool IRenderPostProcessPass.Enabled => Active;

		void IRenderPostProcessPass.Draw(WorldRenderer wr)
		{
			if (cellMapDirty)
				UpdateCellMap();

			if (!shroudResolved)
			{
				shroudResolved = true;
				shroudRenderer = wr.World.WorldActor.TraitOrDefault<PxShroudRenderer>();
			}

			var scroll = wr.Viewport.TopLeft;
			var snapshot = Game.Renderer.WorldBufferSnapshot();
			shader.SetTexture("WorldTexture", snapshot);
			PxShroudRenderer.BindHiddenCells(shroudRenderer, shader, wr, snapshot);
			shader.SetTexture("GrassTexture", textures[0]);
			shader.SetTexture("DirtTexture", textures[1]);
			shader.SetTexture("RockTexture", textures[2]);
			shader.SetTexture("RoughTexture", textures[3]);
			shader.SetTexture("BeachTexture", textures[4]);
			shader.SetTexture("WaterTexture", textures[5]);
			shader.SetTexture("RiverTexture", textures[6]);
			shader.SetTexture("CellMap", CellMap);
			shader.SetVec("CellMapSize", CellMapSize.Width, CellMapSize.Height);
			shader.SetVec("TileSize", wr.TileSize.Width);
			shader.SetVec("Time", Game.RunTime / 1000f % 3600f);
			shader.SetVec("WaterFlow", info.WaterFlow);
			shader.SetVec("WaterDetail", info.Water != null ? info.WaterDetail : -1f);
			shader.SetVec("WaterGlints", info.WaterGlints);
			shader.SetVec("Scroll", scroll.X, scroll.Y);
			shader.SetVec("Downscale", Game.Renderer.WorldDownscaleFactor);
			shader.SetVec("Repeat", info.GrassRepeat, info.DirtRepeat, info.RockRepeat);
			shader.SetVec("Repeat2", new[] { info.RoughRepeat, info.BeachRepeat, info.WaterRepeat, info.RiverRepeat }, 4);
			var rough = TintGain(3);
			shader.SetVec("RoughGain", rough.X, rough.Y, rough.Z);
			var water = Gain(meanColor[5], info.WaterTint, new[] { info.WaterTintColor });
			shader.SetVec("WaterGain", water.X, water.Y, water.Z);
			var river = Gain(meanColor[6], info.WaterTint, new[] { info.WaterTintColor });
			shader.SetVec("RiverGain", river.X, river.Y, river.Z);
			shader.SetVec("MeanLum", meanLum[0], meanLum[1], meanLum[2]);
			shader.SetVec("RockDetail", info.RockDetail);
			shader.SetVec("RockLum", ClassicRockLum());
			shader.SetVec("ShadeStrength", info.ShadeStrength);
			shader.SetVec("GroundLum", info.GroundLum);
			shader.SetVec("EdgeWarp", info.EdgeWarp);
			shader.SetVec("Mode", references[0][3] < 0 ? 0f : 1f);
			shader.SetVec("Softness", info.Softness);
			for (var i = 0; i < MaxReferences; i++)
				shader.SetVec("Ref" + i, references[i], 4);

			// Grass tint: per-channel gain that moves the texture's mean colour onto the classic ground colour
			var tint = TintGain(0);
			shader.SetVec("GroundGain", tint.X, tint.Y, tint.Z);
			shader.PrepareRender();
			Game.Renderer.DrawBatch(buffer, shader, 0, 6, PrimitiveType.TriangleList);
		}

		float ClassicRockLum()
		{
			if (info.RockColors.Length == 0)
				return info.RockLum;

			var sum = 0f;
			foreach (var c in info.RockColors)
				sum += (0.299f * c.R + 0.587f * c.G + 0.114f * c.B) / 255f;

			return sum / info.RockColors.Length;
		}

		float3 TintGain(int texture)
		{
			return Gain(meanColor[texture], info.GroundTint, info.GroundColors);
		}

		// Per-channel gain that moves a texture's mean colour `amount` of the way onto the mean of `targets`
		static float3 Gain(float3 m, float amount, Color[] targets)
		{
			if (amount <= 0 || targets.Length == 0)
				return new float3(1, 1, 1);

			float r = 0, g = 0, b = 0;
			foreach (var c in targets)
			{
				r += c.R / 255f;
				g += c.G / 255f;
				b += c.B / 255f;
			}

			var k = targets.Length;
			var t = amount;
			return new float3(
				1 + t * (r / k / System.Math.Max(m.X, 1e-3f) - 1),
				1 + t * (g / k / System.Math.Max(m.Y, 1e-3f) - 1),
				1 + t * (b / k / System.Math.Max(m.Z, 1e-3f) - 1));
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			buffer?.Dispose();
			foreach (var t in textures)
				t?.Dispose();

			CellMap?.Dispose();
		}
	}
}
