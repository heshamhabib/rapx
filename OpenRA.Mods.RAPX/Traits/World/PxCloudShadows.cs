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
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Soft cloud shadows drifting slowly over the whole battlefield (terrain, buildings and units).",
		"Procedural, no textures. Purely cosmetic (local clock).")]
	public class PxCloudShadowsInfo : TraitInfo
	{
		[Desc("Tilesets with an open sky (empty = all).")]
		public readonly HashSet<string> Tilesets = new() { "TEMPERAT", "SNOW", "DESERT" };

		[Desc("Wind in world pixels per second.")]
		public readonly float2 Wind = new(7, 3);

		[Desc("World pixels per unit of the largest cloud noise (bigger = bigger clouds).")]
		public readonly float CloudSize = 520;

		[Desc("Share of the sky covered by clouds (0-1).")]
		public readonly float Cover = 0.42f;

		[Desc("Darkness of a full cloud shadow (0-1).")]
		public readonly float Strength = 0.6f;

		[Desc("Colour inside the shadow (cooler than direct sun).")]
		public readonly Color ShadowTint = Color.FromArgb(150, 160, 185);

		public readonly string VertexShader = "cloud_shadows.vert";
		public readonly string FragmentShader = "cloud_shadows.frag";

		public override object Create(ActorInitializer init) { return new PxCloudShadows(init.World, this); }
	}

	public sealed class PxCloudShadows : IRenderPostProcessPass, IWorldLoaded, INotifyActorDisposing
	{
		readonly PxCloudShadowsInfo info;
		readonly bool enabled;
		readonly IShader shader;
		readonly IVertexBuffer<RenderPostProcessPassVertex> buffer;
		PxShroudRenderer shroudRenderer;
		PxWeatherManager weather;

		public PxCloudShadows(World world, PxCloudShadowsInfo info)
		{
			this.info = info;

			// RAPX_NO_CLOUDS disables the effect for before/after comparisons
			enabled = (info.Tilesets.Count == 0 || info.Tilesets.Contains(world.Map.Tileset)) &&
				string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("RAPX_NO_CLOUDS"));
			if (!enabled)
				return;

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

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			var manager = w.WorldActor.TraitOrDefault<PxWeatherManager>();
			if (manager != null && manager.Enabled)
				weather = manager;

			shroudRenderer = w.WorldActor.TraitOrDefault<PxShroudRenderer>();
		}

		PostProcessPassType IRenderPostProcessPass.Type => PostProcessPassType.AfterActors;
		bool IRenderPostProcessPass.Enabled => enabled;

		void IRenderPostProcessPass.Draw(WorldRenderer wr)
		{
			var scroll = wr.Viewport.TopLeft;
			PxShroudRenderer.BindHiddenCells(shroudRenderer, shader, wr, null);
			shader.SetVec("Scroll", scroll.X, scroll.Y);
			shader.SetVec("Downscale", Game.Renderer.WorldDownscaleFactor);
			shader.SetVec("CloudSize", info.CloudSize);

			// Weather: thicker, faster clouds in bad weather; a full overcast casts softer shadows
			if (weather != null)
			{
				var f = weather.Frame();
				var overcast = System.Math.Clamp((f.Cloud - 0.35f) / 0.65f, 0, 1);
				shader.SetVec("Offset", info.Wind.X * 20 + f.CloudOffset.X, info.Wind.Y * 20 + f.CloudOffset.Y);
				shader.SetVec("Cover", info.Cover + (0.8f - info.Cover) * overcast);
				shader.SetVec("Strength", info.Strength * (1 - 0.35f * overcast));
			}
			else
			{
				var time = Game.RunTime / 1000f % 3600f;
				shader.SetVec("Offset", info.Wind.X * time, info.Wind.Y * time);
				shader.SetVec("Cover", info.Cover);
				shader.SetVec("Strength", info.Strength);
			}

			shader.SetVec("ShadowTint", info.ShadowTint.R / 255f, info.ShadowTint.G / 255f, info.ShadowTint.B / 255f);
			shader.PrepareRender();

			// The shader returns the shadow multiplier: blending scales what is already drawn, without a world copy
			Game.Renderer.DrawBatch(buffer, shader, 0, 6, PrimitiveType.TriangleList, BlendMode.Multiplicative);
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			buffer?.Dispose();
		}
	}
}
