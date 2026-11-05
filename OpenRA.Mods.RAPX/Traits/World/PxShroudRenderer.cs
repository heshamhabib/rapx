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
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("High-end shroud and fog of war (IDEA-23), replacing ShroudRenderer in game worlds.",
		"One full-screen shader pass draws the unexplored area as a Tactical command-table surface (hex grid,",
		"procedural contours, map coordinates, radar sweep), a smooth glowing border, a reveal scan, a cold",
		"desaturated fog of war and a styled area outside the map. Last-seen buildings in the fog get a hologram tint.",
		"The patterns are procedural: nothing under the shroud is ever drawn.")]
	public class PxShroudRendererInfo : TraitInfo
	{
		[Desc("Border glow colour (UI accent).")]
		public readonly Color BorderColor = Color.FromArgb(232, 46, 40);

		[Desc("Hologram colour for last-seen buildings and the reveal scan.")]
		public readonly Color HologramColor = Color.FromArgb(90, 200, 255);

		[Desc("Seconds for newly explored ground to fade in.")]
		public readonly float ExploreFade = 0.55f;

		[Desc("Seconds for ground to become visible / fall back into the fog.")]
		public readonly float VisibleFadeIn = 0.25f;
		public readonly float VisibleFadeOut = 0.7f;

		[Desc("Seconds the reveal scan plays on newly explored ground.")]
		public readonly float RevealTime = 1.4f;

		[Desc("Seconds per radar sweep revolution over the unexplored area.")]
		public readonly float SweepPeriod = 9f;

		[Desc("Fog of war: brightness, saturation, cool tint.")]
		public readonly float FogBrightness = 0.55f;
		public readonly float FogSaturation = 0.4f;
		public readonly Color FogTint = Color.FromArgb(220, 238, 255);

		[Desc("Opacity of the hologram tint on last-seen buildings (0 disables the ghosts).")]
		public readonly float GhostAlpha = 0.34f;

		public readonly string VertexShader = "ra|shaders/cloud_shadows.vert";
		public readonly string FragmentShader = "ra|shaders/px_shroud.frag";

		public override object Create(ActorInitializer init) { return new PxShroudRenderer(init.World, this); }
	}

	public sealed class PxShroudRenderer : IRenderShroud, IWorldLoaded, INotifyActorDisposing
	{
		readonly PxShroudRendererInfo info;
		readonly World world;
		readonly Map map;
		readonly int texWidth, texHeight;

		// Smoothed per-cell state, indexed y * MapSize.X + x
		readonly float[] explored, visible, reveal;
		readonly bool[] active;
		readonly List<int> activeCells = new();
		readonly byte[] data;

		IShader shader;
		IVertexBuffer<RenderPostProcessPassVertex> buffer;

		/// <summary>Per-cell (explored, visible, reveal, inside map) texture, read as .bgra; shared with the minimap.</summary>
		public ITexture CellMap { get; private set; }
		public float2 CellMapSize => new(texWidth, texHeight);
		public bool HasShroud => world.RenderPlayer != null;
		bool dataDirty = true;

		// PERF: cells whose whole neighbourhood is unexplored. The shroud pass paints over them completely, so the
		// full-screen passes drawn before it (terrain detail, cloud shadows, ground weather) skip their work there.
		// The margin covers the shroud's own reach (soft border, edge warp and screen-space derivatives: 3 cells) plus
		// the pixels those passes read from their neighbours (ripple refraction, relief: up to 2 cells when zoomed out),
		// so the finished picture is identical.
		const int HiddenMargin = 6;
		ITexture hiddenMap;
		readonly byte[] hiddenData;
		readonly bool[] seen, seenRows;
		bool hiddenDirty = true;
		long lastTime;

		Shroud shroud;
		Func<PPos, Shroud.CellVisibility> cellVisibility;

		public PxShroudRenderer(World world, PxShroudRendererInfo info)
		{
			this.info = info;
			this.world = world;
			map = world.Map;

			var size = map.MapSize;
			texWidth = Exts.NextPowerOf2(size.X);
			texHeight = Exts.NextPowerOf2(size.Y);
			explored = new float[size.X * size.Y];
			visible = new float[size.X * size.Y];
			reveal = new float[size.X * size.Y];
			active = new bool[size.X * size.Y];
			data = new byte[4 * texWidth * texHeight];
			hiddenData = new byte[4 * texWidth * texHeight];
			seen = new bool[size.X * size.Y];
			seenRows = new bool[size.X * size.Y];

			world.RenderPlayerChanged += WorldOnRenderPlayerChanged;
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			shader = Game.Renderer.CreateShader(new ModShaderBindings(Game.ModData.DefaultFileSystem, info.VertexShader, info.FragmentShader,
				new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 2, 0)));

			var vertices = new RenderPostProcessPassVertex[]
			{
				new(-1, -1), new(1, -1), new(1, 1),
				new(1, 1), new(-1, 1), new(-1, -1)
			};

			buffer = Game.Renderer.CreateVertexBuffer<RenderPostProcessPassVertex>(6);
			buffer.SetData(ref vertices, 6);

			CellMap = Game.Renderer.CreateTexture();
			CellMap.ScaleFilter = TextureScaleFilter.Linear;
			hiddenMap = Game.Renderer.CreateTexture();

			WorldOnRenderPlayerChanged(world.RenderPlayer);
		}

		void WorldOnRenderPlayerChanged(Player player)
		{
			var newShroud = player?.Shroud;
			if (shroud != newShroud)
			{
				if (shroud != null)
					shroud.OnShroudChanged -= UpdateShroudCell;

				if (newShroud != null)
					newShroud.OnShroudChanged += UpdateShroudCell;

				shroud = newShroud;
			}

			// No render player (observers, replays with "all players"): everything inside the map is visible
			if (newShroud != null)
				cellVisibility = puv => newShroud.GetVisibility(puv);
			else
				cellVisibility = puv => map.Contains(puv) ? Shroud.CellVisibility.Visible | Shroud.CellVisibility.Explored : Shroud.CellVisibility.Hidden;

			// Snap to the new state without animating
			var size = map.MapSize;
			for (var y = 0; y < size.Y; y++)
			{
				for (var x = 0; x < size.X; x++)
				{
					var i = y * size.X + x;
					var cv = cellVisibility(new PPos(x, y));
					explored[i] = cv.HasFlag(Shroud.CellVisibility.Explored) ? 1 : 0;
					visible[i] = cv.HasFlag(Shroud.CellVisibility.Visible) ? 1 : 0;
					reveal[i] = 0;
					active[i] = false;
				}
			}

			activeCells.Clear();
			dataDirty = true;
			hiddenDirty = true;
		}

		void UpdateShroudCell(PPos puv)
		{
			var size = map.MapSize;
			if (puv.U < 0 || puv.V < 0 || puv.U >= size.X || puv.V >= size.Y)
				return;

			var i = puv.V * size.X + puv.U;
			if (!active[i])
			{
				active[i] = true;
				activeCells.Add(i);
				hiddenDirty = true;
			}
		}

		// Eases every changing cell toward its shroud state (local clock: purely cosmetic)
		void Animate()
		{
			var now = Game.RunTime;
			var dt = Math.Clamp((now - lastTime) / 1000f, 0f, 0.1f);
			lastTime = now;
			if (activeCells.Count == 0)
				return;

			var width = map.MapSize.X;
			for (var k = activeCells.Count - 1; k >= 0; k--)
			{
				var i = activeCells[k];
				var cv = cellVisibility(new PPos(i % width, i / width));
				var e = cv.HasFlag(Shroud.CellVisibility.Explored) ? 1f : 0f;
				var v = cv.HasFlag(Shroud.CellVisibility.Visible) ? 1f : 0f;

				if (explored[i] < 0.5f && e > 0.5f && reveal[i] <= 0)
					reveal[i] = 1;

				explored[i] = Step(explored[i], e, dt / info.ExploreFade);
				visible[i] = Step(visible[i], v, dt / (v > visible[i] ? info.VisibleFadeIn : info.VisibleFadeOut));
				reveal[i] = Math.Max(0, reveal[i] - dt / info.RevealTime);

				if (explored[i] == e && visible[i] == v && reveal[i] == 0)
				{
					active[i] = false;
					activeCells[k] = activeCells[^1];
					activeCells.RemoveAt(activeCells.Count - 1);
					hiddenDirty = true;
				}
			}

			dataDirty = true;
		}

		static float Step(float value, float target, float amount)
		{
			return value < target ? Math.Min(target, value + amount) : Math.Max(target, value - amount);
		}

		void UploadCellMap()
		{
			dataDirty = false;
			var size = map.MapSize;
			var bounds = map.Bounds;

			// BGRA byte order: read as .bgra in the shader = (explored, visible, reveal, inside map).
			// Cells outside the playable area copy the nearest inside cell, so the map edge never reads as a
			// shroud border (the shader draws the off-map area from Bounds instead).
			for (var y = 0; y < size.Y; y++)
			{
				var sy = Math.Clamp(y, bounds.Top, bounds.Bottom - 1);
				for (var x = 0; x < size.X; x++)
				{
					var sx = Math.Clamp(x, bounds.Left, bounds.Right - 1);
					var i = sy * size.X + sx;
					var o = 4 * (y * texWidth + x);
					data[o] = (byte)(explored[i] * 255);
					data[o + 1] = (byte)(visible[i] * 255);
					data[o + 2] = (byte)(reveal[i] * 255);
					data[o + 3] = (byte)(bounds.Contains(x, y) ? 255 : 0);
				}
			}

			CellMap.SetData(data, texWidth, texHeight);
		}

		/// <summary>
		/// Binds HiddenMap (one texel per cell, non-zero = fully covered by the shroud, read with texelFetch),
		/// HiddenMapSize (cells) and HiddenTileSize (world pixels per cell) for a pass drawn before the shroud.
		/// </summary>
		public void BindHiddenCells(IShader shader, WorldRenderer wr)
		{
			if (DisableHiddenSkip)
			{
				shader.SetTexture("HiddenMap", hiddenMap);
				shader.SetVec("HiddenMapSize", 0, 0);
				shader.SetVec("HiddenTileSize", 1, 1);
				return;
			}

			if (hiddenDirty)
				UpdateHiddenMap();

			shader.SetTexture("HiddenMap", hiddenMap);
			shader.SetVec("HiddenMapSize", map.MapSize.X, map.MapSize.Y);
			shader.SetVec("HiddenTileSize", wr.TileSize.Width, wr.TileSize.Height);
		}

		// RAPX_NO_HIDDEN_SKIP=1 draws every pass everywhere, for before/after comparisons
		static readonly bool DisableHiddenSkip = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_NO_HIDDEN_SKIP"));

		/// <summary>
		/// Binds the hidden-cell uniforms for a pass drawn before the shroud: the world's shroud renderer when there is one,
		/// otherwise a "nothing hidden" state (the placeholder texture, if any, is never read).
		/// </summary>
		public static void BindHiddenCells(PxShroudRenderer shroud, IShader shader, WorldRenderer wr, ITexture placeholder)
		{
			if (shroud != null)
			{
				shroud.BindHiddenCells(shader, wr);
				return;
			}

			if (placeholder != null)
				shader.SetTexture("HiddenMap", placeholder);

			shader.SetVec("HiddenMapSize", 0, 0);
			shader.SetVec("HiddenTileSize", 1, 1);
		}

		void UpdateHiddenMap()
		{
			hiddenDirty = false;
			var size = map.MapSize;
			var bounds = map.Bounds;

			// A cell counts as seen while it is explored or still changing (it may become explored this frame,
			// before the shroud pass animates it). Cells outside the playable area mirror the nearest inside cell,
			// as in the shroud's cell map.
			for (var y = 0; y < size.Y; y++)
			{
				var sy = Math.Clamp(y, bounds.Top, bounds.Bottom - 1);
				for (var x = 0; x < size.X; x++)
				{
					var i = sy * size.X + Math.Clamp(x, bounds.Left, bounds.Right - 1);
					seen[y * size.X + x] = explored[i] > 0 || active[i];
				}
			}

			// Dilate by the margin: horizontally, then vertically
			for (var y = 0; y < size.Y; y++)
			{
				var row = y * size.X;
				for (var x = 0; x < size.X; x++)
				{
					var any = false;
					for (var dx = Math.Max(0, x - HiddenMargin); dx <= Math.Min(size.X - 1, x + HiddenMargin) && !any; dx++)
						any = seen[row + dx];

					seenRows[row + x] = any;
				}
			}

			for (var y = 0; y < size.Y; y++)
			{
				for (var x = 0; x < size.X; x++)
				{
					var any = false;
					for (var dy = Math.Max(0, y - HiddenMargin); dy <= Math.Min(size.Y - 1, y + HiddenMargin) && !any; dy++)
						any = seenRows[dy * size.X + x];

					var o = 4 * (y * texWidth + x);
					var value = any ? (byte)0 : (byte)255;
					hiddenData[o] = hiddenData[o + 1] = hiddenData[o + 2] = hiddenData[o + 3] = value;
				}
			}

			hiddenMap.SetData(hiddenData, texWidth, texHeight);
		}

		void IRenderShroud.RenderShroud(WorldRenderer wr)
		{
			Animate();
			if (dataDirty)
				UploadCellMap();

			// The world pass is scissored to the map; the styled off-map area needs the whole view.
			// PERF: scissor to the view (plus a tile of margin) rather than none at all: the world buffer is a power of
			// two in size, so without a scissor this shader also ran on the unused part of it (~35% at 2940x1846).
			Game.Renderer.Flush();
			Game.Renderer.DisableScissor();
			var view = wr.Viewport.BottomRight - wr.Viewport.TopLeft;
			Game.Renderer.EnableScissor(new Rectangle(0, 0, view.X + wr.TileSize.Width, view.Y + wr.TileSize.Height));

			var scroll = wr.Viewport.TopLeft;
			var ts = wr.TileSize;
			var b = map.Bounds;
			shader.SetTexture("WorldTexture", Game.Renderer.WorldBufferSnapshot());
			shader.SetTexture("CellMap", CellMap);
			shader.SetVec("CellMapSize", texWidth, texHeight);
			shader.SetVec("TileSize", ts.Width, ts.Height);
			shader.SetVec("Scroll", scroll.X, scroll.Y);
			shader.SetVec("Downscale", Game.Renderer.WorldDownscaleFactor);
			shader.SetVec("Time", Game.RunTime / 1000f % 3600f);
			shader.SetVec("Bounds", new float[] { b.Left * ts.Width, b.Top * ts.Height, b.Right * ts.Width, b.Bottom * ts.Height }, 4);
			shader.SetVec("SweepPeriod", info.SweepPeriod);
			shader.SetVec("BorderColor", info.BorderColor.R / 255f, info.BorderColor.G / 255f, info.BorderColor.B / 255f);
			shader.SetVec("HoloColor", info.HologramColor.R / 255f, info.HologramColor.G / 255f, info.HologramColor.B / 255f);
			shader.SetVec("Fog", info.FogBrightness, info.FogSaturation);
			shader.SetVec("FogTint", info.FogTint.R / 255f, info.FogTint.G / 255f, info.FogTint.B / 255f);
			shader.PrepareRender();
			Game.Renderer.DrawBatch(buffer, shader, 0, 6, PrimitiveType.TriangleList);

			DrawGhosts(wr);

			// Restore the scissor that WorldRenderer.Draw pops right after the shroud
			Game.Renderer.DisableScissor();
			Game.Renderer.EnableScissor(wr.Viewport.GetScissorBounds(true));
		}

		// Last-seen buildings under the fog: a flickering hologram silhouette over the dimmed sprite
		void DrawGhosts(WorldRenderer wr)
		{
			var player = world.RenderPlayer;
			if (player == null || info.GhostAlpha <= 0)
				return;

			var t = Game.RunTime / 1000f;
			var alpha = info.GhostAlpha * (0.85f + 0.15f * MathF.Sin(t * 5.3f) * MathF.Sin(t * 1.7f));
			var tint = new float3(info.HologramColor.R / 255f, info.HologramColor.G / 255f, info.HologramColor.B / 255f);
			const TintModifiers Modifiers = TintModifiers.ReplaceColor | TintModifiers.IgnoreWorldTint;

			// Only the opaque body sprites: translucent particles (smoke, steam) would turn into bright blobs
			var bodies = world.ScreenMap.RenderableFrozenActorsInBox(player, wr.Viewport.TopLeft, wr.Viewport.BottomRight)
				.Where(f => f.Visible && f.HasRenderables)
				.SelectMany(f => f.Render())
				.OfType<IModifyableRenderable>()
				.Where(r => !r.IsDecoration && r.Alpha > 0.99f)
				.ToList();

			// Silhouette plus a faint copy that jitters sideways now and then (hologram glitch)
			var glitch = MathF.Sin(t * 0.9f) > 0.93f ? new WVec((int)(MathF.Sin(t * 47f) * 64), 0, 0) : new WVec(48, 0, 0);
			var ghosts = bodies.Select(r => r.WithTint(tint, Modifiers).WithAlpha(alpha).PrepareRender(wr))
				.Concat(bodies.Select(r => ((IModifyableRenderable)r.OffsetBy(glitch)).WithTint(tint, Modifiers).WithAlpha(alpha * 0.4f).PrepareRender(wr)))
				.ToList();

			foreach (var r in ghosts)
				r.Render(wr);

			Game.Renderer.Flush();
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			if (shroud != null)
				shroud.OnShroudChanged -= UpdateShroudCell;

			world.RenderPlayerChanged -= WorldOnRenderPlayerChanged;
			buffer?.Dispose();
			CellMap?.Dispose();
			hiddenMap?.Dispose();
		}
	}
}
