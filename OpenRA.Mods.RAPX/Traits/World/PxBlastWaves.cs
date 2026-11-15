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
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Pressure waves of the HD explosions (PxExplosion): a refracting shock front racing out over the ground and",
		"heat shimmer over the fireball, drawn as a full-screen pass that bends the picture of the world. Costs nothing",
		"while nothing is exploding. Turned off together with the Weather Effects setting (and by RAPX_NO_WEATHER or",
		"RAPX_NO_BLASTWAVES).")]
	public class PxBlastWavesInfo : TraitInfo
	{
		public readonly string VertexShader = "ra|shaders/weather.vert";
		public readonly string FragmentShader = "ra|shaders/blast_waves.frag";

		[Desc("How far the picture is bent at the shock front of a Size 1 blast, in world pixels.")]
		public readonly float Strength = 11f;

		[Desc("How far the heat over a Size 1 fireball bends the picture, in world pixels.")]
		public readonly float Shimmer = 2.2f;

		public override object Create(ActorInitializer init) { return new PxBlastWaves(this); }
	}

	public sealed class PxBlastWaves : IRenderPostProcessPass, INotifyActorDisposing
	{
		// Uniform slots in blast_waves.frag
		const int Slots = 8;

		// Screen pixels per cell
		const float PixelsPerCell = 24f;

		sealed class Wave
		{
			public WPos Pos;
			public float Size;
			public long Start;
			public float Life;
			public bool Heat;
		}

		readonly PxBlastWavesInfo info;
		readonly IShader shader;
		readonly IVertexBuffer<RenderPostProcessPassVertex> buffer;
		readonly List<Wave> waves = new();
		readonly float[] vec4 = new float[4];

		public PxBlastWaves(PxBlastWavesInfo info)
		{
			this.info = info;
			if (!Game.Settings.Graphics.WeatherEffects ||
				!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_NO_WEATHER")) ||
				!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_NO_BLASTWAVES")))
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

		public bool Available => shader != null;

		/// <summary>A blast at ground: a shock front over the ground (not for air bursts) and heat over the fireball.</summary>
		public void Add(WPos ground, float size, bool air)
		{
			if (shader == null || size < 0.5f)
				return;

			var now = Game.RunTime;
			if (!air)
				waves.Add(new Wave { Pos = ground, Size = size, Start = now, Life = 340 + 260 * size });

			waves.Add(new Wave { Pos = ground, Size = size, Start = now, Life = 900 + 500 * size, Heat = true });

			// The shader has eight slots: drop the oldest waves
			while (waves.Count > Slots)
				waves.RemoveAt(0);
		}

		PostProcessPassType IRenderPostProcessPass.Type => PostProcessPassType.AfterWorld;
		bool IRenderPostProcessPass.Enabled => shader != null && waves.Count > 0;

		void Set(string name, float x, float y, float z, float w)
		{
			vec4[0] = x;
			vec4[1] = y;
			vec4[2] = z;
			vec4[3] = w;
			shader.SetVec(name, vec4, 4);
		}

		void IRenderPostProcessPass.Draw(WorldRenderer wr)
		{
			var now = Game.RunTime;
			waves.RemoveAll(w => now - w.Start > w.Life);
			if (waves.Count == 0)
				return;

			var scroll = wr.Viewport.TopLeft;
			shader.SetTexture("WorldTexture", Game.Renderer.WorldBufferSnapshot());
			shader.SetVec("Scroll", scroll.X, scroll.Y);
			shader.SetVec("Downscale", Game.Renderer.WorldDownscaleFactor);
			shader.SetVec("Time", now / 1000f);

			for (var i = 0; i < Slots; i++)
			{
				if (i >= waves.Count)
				{
					Set("Wave" + i, 0, 0, 0, 1);
					Set("WaveParams" + i, 0, 0, 0, 0);
					continue;
				}

				var w = waves[i];
				var t = Math.Clamp((now - w.Start) / w.Life, 0f, 1f);
				var px = wr.ScreenPxPosition(w.Pos);
				if (!w.Heat)
				{
					// The front races out fast and slows down, bending the picture less as it spreads
					var radius = PixelsPerCell * (1.2f + 1.3f * w.Size) * (1 - (1 - t) * (1 - t));
					var width = PixelsPerCell * (0.3f + 0.28f * w.Size);
					var strength = info.Strength * w.Size * MathF.Pow(1 - t, 1.6f);
					Set("Wave" + i, px.X, px.Y, radius, width);
					Set("WaveParams" + i, strength, 0, t, 0);
				}
				else
				{
					// Hot air over the fireball, rising and thinning
					var radius = PixelsPerCell * (0.9f + 1.1f * w.Size) * (0.7f + 0.5f * t);
					var strength = info.Shimmer * Math.Min(w.Size, 2.5f) * (1 - t) * Math.Min(1, 0.3f + t * 4);
					Set("Wave" + i, px.X, px.Y - PixelsPerCell * (0.5f + 0.6f * w.Size) * (0.5f + t), radius, 1);
					Set("WaveParams" + i, strength, 1, t, 0);
				}
			}

			shader.PrepareRender();
			Game.Renderer.DrawBatch(buffer, shader, 0, 6, PrimitiveType.TriangleList);
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			buffer?.Dispose();
		}
	}
}
