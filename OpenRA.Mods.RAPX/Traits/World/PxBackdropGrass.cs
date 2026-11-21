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
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World | SystemActors.EditorWorld)]
	[Desc("Makes the lawns painted into a map backdrop (PxMapBackdrop) move in the wind: soft gusts sweep across the",
		"grass, lightening it where the blades bend and catch the sun, and sway the painted blades a little. Needs a grass",
		"mask in the map package (.r = grass coverage, PixelsPerCell per cell from the top-left cell of the map bounds;",
		"see artsrc/maps/monument/make_grass_mask.py). List it right after PxMapBackdrop so it draws before smudges, ore",
		"and actors. Purely cosmetic (local clock).")]
	public class PxBackdropGrassInfo : TraitInfo, Requires<PxMapBackdropInfo>
	{
		[Desc("Grass mask file in the map package. Maps without it have no animated grass.")]
		public readonly string FlowMap = "grass-mask.png";

		[Desc("Mask pixels per map cell; its top-left pixel is the top-left cell of the map bounds.")]
		public readonly int PixelsPerCell = 16;

		[Desc("Wind direction in degrees (0 = towards the east, 90 = towards the south) and gust speed in world pixels per second.")]
		public readonly float WindAngle = 30f;
		public readonly float Speed = 70f;

		[Desc("Seconds after which the animation repeats (keeps the shader's time small).")]
		public readonly float Cycle = 600f;

		[Desc("How far the blades sway, world pixels.")]
		public readonly float Distortion = 1.6f;

		[Desc("How much the gusts lighten the grass.")]
		public readonly float Shading = 0.16f;

		[Desc("HD grass texture drawn at screen resolution over the lawns (seamless, power-of-two RGB png), so the grass",
			"stays sharp when the painted backdrop is magnified. Its light and dark detail is laid over the painted colour;",
			"DetailColor of its own colour (flowers, clover) shows through.")]
		public readonly string DetailTexture = "ra|bits/hd/terrain/grass-detail.png";

		[Desc("Map cells covered by one repeat of the detail texture.")]
		public readonly float DetailCells = 3.5f;

		[Desc("Strength of the detail's light and dark, and how much of its own colour shows.")]
		public readonly float DetailStrength = 0.9f;
		public readonly float DetailColor = 0.3f;

		[Desc("Colour grade of the lawns: saturation (1 = as painted), a tint the colour is pulled towards (RGB, relative to",
			"its brightness), how strongly, and a brightness lift. The default gives a pale, soft sage green.")]
		public readonly float GradeSaturation = 0.72f;
		public readonly float3 GradeTint = new(1.0f, 1.12f, 0.70f);
		public readonly float GradeAmount = 0.45f;
		public readonly float GradeLift = 0.04f;

		public readonly string VertexShader = "ra|shaders/weather.vert";
		public readonly string FragmentShader = "ra|shaders/backdrop_grass.frag";

		public override object Create(ActorInitializer init) { return new PxBackdropGrass(init.World, this); }
	}

	public sealed class PxBackdropGrass : IWorldLoaded, IRenderOverlay, INotifyActorDisposing
	{
		readonly PxBackdropGrassInfo info;
		readonly World world;
		IShader shader;
		IVertexBuffer<RenderPostProcessPassVertex> buffer;
		Sheet flowMap;
		ITexture detail;
		float3 detailMean;

		public PxBackdropGrass(World world, PxBackdropGrassInfo info)
		{
			this.world = world;
			this.info = info;
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			var map = w.Map;
			var backdrop = w.WorldActor.TraitOrDefault<PxMapBackdrop>();
			if (backdrop == null || !backdrop.Active || !map.Package.Contains(info.FlowMap) ||
				!string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("RAPX_NO_BACKDROP_GRASS")))
				return;

			using (var stream = map.Package.GetStream(info.FlowMap))
				flowMap = new Sheet(SheetType.BGRA, stream);

			flowMap.ScaleFilter = TextureScaleFilter.Linear;
			detail = LoadDetail(Game.ModData.DefaultFileSystem, info.DetailTexture, out detailMean);

			shader = Game.Renderer.CreateShader(new ModShaderBindings(Game.ModData.DefaultFileSystem, info.VertexShader, info.FragmentShader,
				new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 2, 0)));

			var vertices = new RenderPostProcessPassVertex[]
			{
				new(-1, -1), new(1, -1), new(1, 1),
				new(1, 1), new(-1, 1), new(-1, -1)
			};

			buffer = Game.Renderer.CreateVertexBuffer<RenderPostProcessPassVertex>(6);
			buffer.SetData(ref vertices, 6);
		}

		static ITexture LoadDetail(OpenRA.FileSystem.IReadOnlyFileSystem fileSystem, string path, out float3 mean)
		{
			OpenRA.FileFormats.Png png;
			using (var stream = fileSystem.Open(path))
				png = new OpenRA.FileFormats.Png(stream);

			var stride = png.PixelStride;
			var data = new byte[4 * png.Width * png.Height];
			double r = 0, g = 0, b = 0;
			for (int i = 0, j = 0; i < data.Length; i += 4, j += stride)
			{
				data[i] = png.Data[j + 2];
				data[i + 1] = png.Data[j + 1];
				data[i + 2] = png.Data[j];
				data[i + 3] = 255;
				r += png.Data[j];
				g += png.Data[j + 1];
				b += png.Data[j + 2];
			}

			var n = png.Width * png.Height * 255.0;
			mean = new float3((float)(r / n), (float)(g / n), (float)(b / n));
			var texture = Game.Renderer.CreateTexture();
			texture.ScaleFilter = TextureScaleFilter.Trilinear;
			texture.SetData(data, png.Width, png.Height);
			return texture;
		}

		void IRenderOverlay.Render(WorldRenderer wr)
		{
			if (shader == null)
				return;

			var time = Game.RunTime % (long)(info.Cycle * 1000) / 1000f;

			var bounds = world.Map.Bounds;
			var tile = world.Map.Grid.TileSize;
			var scroll = wr.Viewport.TopLeft;

			Game.Renderer.Flush();
			shader.SetTexture("WorldTexture", Game.Renderer.WorldBufferSnapshot());
			shader.SetTexture("FlowMap", flowMap.GetTexture());
			shader.SetVec("Time", time);
			shader.SetVec("Scroll", scroll.X, scroll.Y);
			shader.SetVec("Downscale", Game.Renderer.WorldDownscaleFactor);
			shader.SetVec("TileSize", tile.Width, tile.Height);
			shader.SetVec("FlowOrigin", bounds.X, bounds.Y);
			shader.SetVec("FlowScale", (float)info.PixelsPerCell / flowMap.Size.Width, (float)info.PixelsPerCell / flowMap.Size.Height);
			shader.SetVec("Speed", info.Speed);
			shader.SetTexture("Detail", detail);
			shader.SetVec("DetailMean", detailMean.X, detailMean.Y, detailMean.Z);
			shader.SetVec("DetailCells", info.DetailCells);
			shader.SetVec("DetailStrength", info.DetailStrength);
			shader.SetVec("DetailColor", info.DetailColor);
			shader.SetVec("GradeSaturation", info.GradeSaturation);
			shader.SetVec("GradeTint", info.GradeTint.X, info.GradeTint.Y, info.GradeTint.Z);
			shader.SetVec("GradeAmount", info.GradeAmount);
			shader.SetVec("GradeLift", info.GradeLift);
			var a = info.WindAngle * MathF.PI / 180f;
			shader.SetVec("Wind", MathF.Cos(a), MathF.Sin(a));
			shader.SetVec("Distortion", info.Distortion);
			shader.SetVec("Shading", info.Shading);
			shader.PrepareRender();
			Game.Renderer.DrawBatch(buffer, shader, 0, 6, PrimitiveType.TriangleList);
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			buffer?.Dispose();
			flowMap?.Dispose();
			detail?.Dispose();
		}
	}
}
