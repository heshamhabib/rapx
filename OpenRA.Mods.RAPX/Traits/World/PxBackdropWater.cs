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

using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World | SystemActors.EditorWorld)]
	[Desc("Makes the river painted into a map backdrop (PxMapBackdrop) flow: ripples stream downstream, wobble the painted",
		"water, catch the sun and foam along the banks. Needs a flow map in the map package (see",
		"artsrc/maps/berlin/make_water_flow.py): .r water, .g flow angle (0.5 = west), .b distance from the bank.",
		"List it right after PxMapBackdrop so it draws before smudges, ore and actors. Purely cosmetic (local clock).")]
	public class PxBackdropWaterInfo : TraitInfo, Requires<PxMapBackdropInfo>
	{
		[Desc("Flow map file in the map package. Maps without it have no animated water.")]
		public readonly string FlowMap = "water-flow.png";

		[Desc("Flow map pixels per map cell; its top-left pixel is the top-left cell of the map bounds.")]
		public readonly int PixelsPerCell = 16;

		[Desc("Current speed in mid-stream, world pixels per second.")]
		public readonly float Speed = 9f;

		[Desc("Seconds per advection phase (longer = less visible cross-fading, more stretching).")]
		public readonly float Cycle = 2.5f;

		[Desc("How far the ripples shift the painted water, world pixels.")]
		public readonly float Distortion = 14f;

		public readonly float Shading = 0.22f;
		public readonly float Glint = 0.55f;
		public readonly float Foam = 0.22f;

		public readonly string VertexShader = "ra|shaders/weather.vert";
		public readonly string FragmentShader = "ra|shaders/backdrop_water.frag";

		public override object Create(ActorInitializer init) { return new PxBackdropWater(init.World, this); }
	}

	public sealed class PxBackdropWater : IWorldLoaded, IRenderOverlay, INotifyActorDisposing
	{
		readonly PxBackdropWaterInfo info;
		readonly World world;
		IShader shader;
		IVertexBuffer<RenderPostProcessPassVertex> buffer;
		Sheet flowMap;

		public PxBackdropWater(World world, PxBackdropWaterInfo info)
		{
			this.world = world;
			this.info = info;
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			var map = w.Map;
			var backdrop = w.WorldActor.TraitOrDefault<PxMapBackdrop>();
			if (backdrop == null || !backdrop.Active || !map.Package.Contains(info.FlowMap) ||
				!string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("RAPX_NO_BACKDROP_WATER")))
				return;

			using (var stream = map.Package.GetStream(info.FlowMap))
				flowMap = new Sheet(SheetType.BGRA, stream);

			flowMap.ScaleFilter = TextureScaleFilter.Linear;

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

		void IRenderOverlay.Render(WorldRenderer wr)
		{
			if (shader == null)
				return;

			// Seamless wrap: the shader only sees time through fract(Time / Cycle)
			var period = info.Cycle * 1000f;
			var time = Game.RunTime % (long)(period * 1000) / 1000f;

			var bounds = world.Map.Bounds;
			var tile = world.Map.Grid.TileSize;
			var scroll = wr.Viewport.TopLeft;

			Game.Renderer.Flush();
			shader.SetTexture("WorldTexture", Game.Renderer.WorldBufferSnapshot());
			shader.SetTexture("FlowMap", flowMap.GetTexture());
			shader.SetVec("Time", time);
			shader.SetVec("Cycle", info.Cycle);
			shader.SetVec("Scroll", scroll.X, scroll.Y);
			shader.SetVec("Downscale", Game.Renderer.WorldDownscaleFactor);
			shader.SetVec("TileSize", tile.Width, tile.Height);
			shader.SetVec("FlowOrigin", bounds.X, bounds.Y);
			shader.SetVec("FlowScale", (float)info.PixelsPerCell / flowMap.Size.Width, (float)info.PixelsPerCell / flowMap.Size.Height);
			shader.SetVec("Speed", info.Speed);
			shader.SetVec("Distortion", info.Distortion);
			shader.SetVec("Shading", info.Shading);
			shader.SetVec("Glint", info.Glint);
			shader.SetVec("Foam", info.Foam);
			shader.PrepareRender();
			Game.Renderer.DrawBatch(buffer, shader, 0, 6, PrimitiveType.TriangleList);
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			buffer?.Dispose();
			flowMap?.Dispose();
		}
	}
}
