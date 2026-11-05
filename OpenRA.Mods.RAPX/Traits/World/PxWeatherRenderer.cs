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

using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	/// <summary>One full-screen shader pass over the world buffer, fed by PxWeatherManager.</summary>
	public abstract class PxWeatherPass : IRenderPostProcessPass, IWorldLoaded, INotifyActorDisposing
	{
		protected readonly IShader Shader;
		readonly IVertexBuffer<RenderPostProcessPassVertex> buffer;
		readonly PostProcessPassType type;
		protected PxWeatherManager Manager { get; private set; }

		protected PxWeatherPass(string vertexShader, string fragmentShader, PostProcessPassType type)
		{
			this.type = type;
			if (!string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("RAPX_NO_WEATHER")))
				return;

			Shader = Game.Renderer.CreateShader(new ModShaderBindings(Game.ModData.DefaultFileSystem, vertexShader, fragmentShader,
				new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 2, 0)));

			var vertices = new RenderPostProcessPassVertex[]
			{
				new(-1, -1), new(1, -1), new(1, 1),
				new(1, 1), new(-1, 1), new(-1, -1)
			};

			buffer = Game.Renderer.CreateVertexBuffer<RenderPostProcessPassVertex>(6);
			buffer.SetData(ref vertices, 6);
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			var manager = w.WorldActor.TraitOrDefault<PxWeatherManager>();
			if (manager != null && manager.Enabled && Shader != null)
				Manager = manager;
		}

		PostProcessPassType IRenderPostProcessPass.Type => type;
		bool IRenderPostProcessPass.Enabled => Manager != null && Visible(Manager);

		/// <summary>The world image this pass draws from (valid while drawing).</summary>
		protected ITexture WorldSnapshot { get; private set; }

		protected abstract bool Visible(PxWeatherManager manager);
		protected abstract void SetUniforms(WorldRenderer wr, PxWeatherFrame f);

		void IRenderPostProcessPass.Draw(WorldRenderer wr)
		{
			var f = Manager.Frame();
			var scroll = wr.Viewport.TopLeft;
			WorldSnapshot = Game.Renderer.WorldBufferSnapshot();
			Shader.SetTexture("WorldTexture", WorldSnapshot);
			Shader.SetVec("Scroll", scroll.X, scroll.Y);
			Shader.SetVec("Downscale", Game.Renderer.WorldDownscaleFactor);
			Shader.SetVec("Time", f.Time);
			SetUniforms(wr, f);
			Shader.PrepareRender();
			Game.Renderer.DrawBatch(buffer, Shader, 0, 6, PrimitiveType.TriangleList);
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			buffer?.Dispose();
		}
	}

	[TraitLocation(SystemActors.World)]
	[Desc("Weather on the ground (IDEA-20): wet ground with glossy light and rippling puddles, snow cover and wind-blown",
		"sand drifts. Drawn after the HD terrain pass, so units and buildings stay dry. RAPX_NO_WEATHER=1 disables it.")]
	public class PxWeatherGroundInfo : TraitInfo, Requires<PxWeatherManagerInfo>, NotBefore<TerrainDetailTexturesInfo>
	{
		public readonly string VertexShader = "ra|shaders/weather.vert";
		public readonly string FragmentShader = "ra|shaders/weather_ground.frag";

		[Desc("Share of the open ground that collects puddles when fully wet (0-1).")]
		public readonly float Puddles = 0.32f;

		public override object Create(ActorInitializer init) { return new PxWeatherGround(this); }
	}

	public sealed class PxWeatherGround : PxWeatherPass
	{
		readonly PxWeatherGroundInfo info;
		TerrainDetailTextures terrain;
		PxShroudRenderer shroudRenderer;
		bool terrainResolved;

		public PxWeatherGround(PxWeatherGroundInfo info)
			: base(info.VertexShader, info.FragmentShader, PostProcessPassType.AfterTerrain)
		{
			this.info = info;
		}

		protected override bool Visible(PxWeatherManager m)
		{
			var f = m.Frame();
			return f.Wetness > 0.003f || f.SnowCover > 0.003f || f.SandCover > 0.003f || f.Rain > 0.003f;
		}

		protected override void SetUniforms(WorldRenderer wr, PxWeatherFrame f)
		{
			// The world actor is still being built in the constructor, so the HD terrain pass is found on first draw
			if (!terrainResolved)
			{
				terrainResolved = true;
				terrain = wr.World.WorldActor.TraitsImplementing<TerrainDetailTextures>().FirstOrDefault(t => t.Active);
				shroudRenderer = wr.World.WorldActor.TraitOrDefault<PxShroudRenderer>();
			}

			PxShroudRenderer.BindHiddenCells(shroudRenderer, Shader, wr, WorldSnapshot);

			var cellMap = terrain?.CellMap;
			Shader.SetVec("HasCellMap", cellMap != null ? 1f : 0f);
			if (cellMap != null)
			{
				Shader.SetTexture("CellMap", cellMap);
				Shader.SetVec("CellMapSize", terrain.CellMapSize.Width, terrain.CellMapSize.Height);
			}

			Shader.SetVec("TileSize", wr.TileSize.Width);
			Shader.SetVec("Wetness", f.Wetness);
			Shader.SetVec("Rain", f.Rain);
			Shader.SetVec("Puddles", info.Puddles);
			Shader.SetVec("SnowCover", f.SnowCover);
			Shader.SetVec("SandCover", f.SandCover);
			Shader.SetVec("Dark", f.Dark);
			Shader.SetVec("Flash", f.Flash);
			Shader.SetVec("WindDir", f.WindDir.X, f.WindDir.Y);
			Shader.SetVec("CloudOffset", f.CloudOffset.X, f.CloudOffset.Y);
			Shader.SetVec("DustOffset", f.DustOffset.X, f.DustOffset.Y);
			Shader.SetVec("SnowColor", f.SnowColor.X, f.SnowColor.Y, f.SnowColor.Z);
			Shader.SetVec("SandColor", f.SandColor.X, f.SandColor.Y, f.SandColor.Z);
		}
	}

	[TraitLocation(SystemActors.World)]
	[Desc("Weather in the air (IDEA-20): layered rain with splashes and gusting curtains, snow and blizzards, blowing",
		"sand, drifting fog banks, heat shimmer, lightning bolts with sky flashes, and the light of each weather.",
		"Drawn over the whole world view. RAPX_NO_WEATHER=1 disables it.")]
	public class PxWeatherSkyInfo : TraitInfo, Requires<PxWeatherManagerInfo>
	{
		public readonly string VertexShader = "ra|shaders/weather.vert";
		public readonly string FragmentShader = "ra|shaders/weather_sky.frag";

		public override object Create(ActorInitializer init) { return new PxWeatherSky(this); }
	}

	public sealed class PxWeatherSky : PxWeatherPass
	{
		public PxWeatherSky(PxWeatherSkyInfo info)
			: base(info.VertexShader, info.FragmentShader, PostProcessPassType.AfterShroud) { }

		protected override bool Visible(PxWeatherManager m)
		{
			var f = m.Frame();
			return f.Rain + f.Snow + f.Sand + f.Fog + f.Haze + f.Dust + f.Flash + System.Math.Abs(f.Dark) > 0.003f
				|| f.Bolts[0].Intensity > 0 || f.Bolts[1].Intensity > 0;
		}

		protected override void SetUniforms(WorldRenderer wr, PxWeatherFrame f)
		{
			Shader.SetVec("Rain", f.Rain);
			Shader.SetVec("Snow", f.Snow);
			Shader.SetVec("Sand", f.Sand);
			Shader.SetVec("Fog", f.Fog);
			Shader.SetVec("Storm", f.Storm);
			Shader.SetVec("Haze", f.Haze);
			Shader.SetVec("Wind", f.Wind);
			Shader.SetVec("Dark", f.Dark);
			Shader.SetVec("Dust", f.Dust);
			Shader.SetVec("Flash", f.Flash);
			Shader.SetVec("WindDir", f.WindDir.X, f.WindDir.Y);
			Shader.SetVec("FogOffset", f.FogOffset.X, f.FogOffset.Y);
			Shader.SetVec("DustOffset", f.DustOffset.X, f.DustOffset.Y);
			Shader.SetVec("FogColor", f.FogColor.X, f.FogColor.Y, f.FogColor.Z);
			Shader.SetVec("SandColor", f.SandColor.X, f.SandColor.Y, f.SandColor.Z);
			Shader.SetVec("DebrisColor", f.DebrisColor.X, f.DebrisColor.Y, f.DebrisColor.Z);

			var size = wr.Viewport.BottomRight - wr.Viewport.TopLeft;
			var downscale = Game.Renderer.WorldDownscaleFactor;
			Shader.SetVec("ViewSize", size.X / downscale, size.Y / downscale);

			for (var i = 0; i < 2; i++)
			{
				var b = f.Bolts[i];
				Shader.SetVec("Bolt" + i, new[] { b.Start.X, b.Start.Y, b.End.X, b.End.Y }, 4);
				Shader.SetVec("BoltParams" + i, b.Intensity, b.Seed, b.Branches);
			}
		}
	}
}
