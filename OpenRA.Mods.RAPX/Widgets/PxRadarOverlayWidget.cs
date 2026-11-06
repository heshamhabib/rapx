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
using System.Linq;
using System.Reflection;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// High-end tactical minimap. Paints over the stock Radar widget (a sibling, which keeps input, pings and the
	/// open/close animation) with one shader pass: smooth shaded terrain, glowing unit blips, the Tactical shroud shared
	/// with PxShroudRenderer, a radar sweep with range rings, scanlines and the camera frame; then corner brackets.
	/// Without a radar it shows scanlines over the "no signal" panel. Never takes input.
	/// Radar scan (RadarScan): while the radar works it also shows the terrain of the whole map and every enemy building,
	/// except inside the shroud bubble of an active enemy Gap Generator (CreatesShroud). Units still need real vision.
	/// </summary>
	public class PxRadarOverlayWidget : Widget
	{
		const BindingFlags Private = BindingFlags.NonPublic | BindingFlags.Instance;

		// One shader and quad for the whole process (there is a single GL context)
		static IShader shader;
		static IVertexBuffer<RenderPostProcessPassVertex> quad;

		public readonly Color BracketColor = Color.FromArgb(226, 38, 38);
		public readonly Color SweepColor = Color.FromArgb(110, 255, 140);
		public readonly int BracketLength = 14;
		public readonly int BracketInset = 5;
		public readonly int ScanlinePeriod = 3;

		[Desc("Seconds per sweep revolution.")]
		public readonly float SweepPeriod = 4f;

		[Desc("Id of the Radar widget this draws over (a sibling).")]
		public readonly string Radar = "RADAR_MINIMAP";

		[Desc("Show the terrain of the whole map and the enemy buildings on the radar (not under enemy Gap Generators).")]
		public readonly bool RadarScan = true;

		[Desc("Milliseconds between radar scan updates.")]
		public readonly int ScanInterval = 500;

		public readonly string VertexShader = "ra|shaders/px_minimap.vert";
		public readonly string FragmentShader = "ra|shaders/px_minimap.frag";

		public Func<bool> IsActive = () => true;

		RadarWidget radar;
		ITexture scanMap;
		byte[] scanData;
		int scanWidth, scanHeight;
		long nextScan;
		World scanWorld;
		FieldInfo mapRectField, scaleField, heightField, sheetField, terrainField, actorField, worldRendererField;
		MethodInfo drawPings;

		public PxRadarOverlayWidget() { IgnoreMouseOver = true; }

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		RadarWidget FindRadar()
		{
			if (radar != null)
				return radar;

			radar = Parent?.GetOrNull<RadarWidget>(Radar);
			if (radar == null)
				return null;

			var type = typeof(RadarWidget);
			mapRectField = type.GetField("mapRect", Private);
			scaleField = type.GetField("previewScale", Private);
			heightField = type.GetField("radarMinimapHeight", Private);
			sheetField = type.GetField("radarSheet", Private);
			terrainField = type.GetField("terrainSprite", Private);
			actorField = type.GetField("actorSprite", Private);
			worldRendererField = type.GetField("worldRenderer", Private);
			drawPings = type.GetMethod("DrawRadarPings", Private);
			return radar;
		}

		// Returns false when the stock radar should be left as it is
		bool DrawMinimap()
		{
			if (FindRadar() == null || !radar.IsVisible() || mapRectField == null || scaleField == null || heightField == null ||
				sheetField == null || terrainField == null || actorField == null || worldRendererField == null)
				return false;

			var wr = (WorldRenderer)worldRendererField.GetValue(radar);
			var world = wr?.World;
			if (world == null || world.Map.Grid.Type != MapGridType.Rectangular)
				return false;

			var height = (float)heightField.GetValue(radar);
			var sheet = (Sheet)sheetField.GetValue(radar);
			var terrain = (Sprite)terrainField.GetValue(radar);
			var actors = (Sprite)actorField.GetValue(radar);
			if (height <= 0 || sheet == null || terrain == null || actors == null)
				return false;

			if (shader == null)
			{
				shader = Game.Renderer.CreateShader(new ModShaderBindings(Game.ModData.DefaultFileSystem, VertexShader, FragmentShader,
					new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 2, 0)));

				var vertices = new RenderPostProcessPassVertex[]
				{
					new(-1, -1), new(1, -1), new(1, 1),
					new(1, 1), new(-1, 1), new(-1, -1)
				};

				quad = Game.Renderer.CreateVertexBuffer<RenderPostProcessPassVertex>(6);
				quad.SetData(ref vertices, 6);
			}

			// Same placement as RadarWidget.Draw (the height animates while the radar opens and closes)
			var mapRect = (Rectangle)mapRectField.GetValue(radar);
			var scale = (float)scaleField.GetValue(radar);
			var bounds = world.Map.Bounds;
			var x = (float)mapRect.X;
			var y = mapRect.Y + bounds.Height * scale * (1 - height) / 2;
			var w = (float)mapRect.Width;
			var h = mapRect.Height * height;

			// Camera rectangle in map UVs
			var vp = wr.Viewport;
			var tl = wr.ProjectedPosition(vp.TopLeft);
			var br = wr.ProjectedPosition(vp.BottomRight);
			float U(int wx) => (wx / 1024f - bounds.Left) / bounds.Width;
			float V(int wy) => (wy / 1024f - bounds.Top) / bounds.Height;

			var shroud = world.WorldActor.TraitOrDefault<PxShroudRenderer>();

			// The UI is drawn into a power-of-two buffer (UI pixels, y = 0 at clip -1) that is flipped when presented
			// (surface pixels = UI size x window scale, as in Renderer.BeginFrame)
			var res = Game.Renderer.Resolution;
			var windowScale = Game.Renderer.WindowScale;
			var surface = new Size((int)Math.Round(res.Width * windowScale), (int)Math.Round(res.Height * windowScale)).NextPowerOf2();
			var bw = (int)(surface.Width / windowScale);
			var bh = (int)(surface.Height / windowScale);
			sheet.CommitBufferedData();
			Game.Renderer.Flush();

			// Scalar first: the array overload of SetVec does not bind the program itself
			shader.SetVec("Time", Game.RunTime / 1000f % 3600f);

			// The quad covers the whole radar panel; the map sits inside it
			var pb = radar.RenderBounds;
			shader.SetVec("Rect", new[] { 2f * pb.X / bw - 1, 2f * pb.Bottom / bh - 1, 2f * pb.Right / bw - 1, 2f * pb.Y / bh - 1 }, 4);
			shader.SetVec("MapRect", new[] { x - pb.X, y - pb.Y, w, h }, 4);
			shader.SetVec("PanelSize", pb.Width, pb.Height);
			shader.SetTexture("Radar", sheet.GetTexture());
			shader.SetVec("TerrainRect", new float[] { terrain.Bounds.X, terrain.Bounds.Y, terrain.Bounds.Width, terrain.Bounds.Height }, 4);
			shader.SetVec("ActorRect", new float[] { actors.Bounds.X, actors.Bounds.Y, actors.Bounds.Width, actors.Bounds.Height }, 4);
			if (shroud?.CellMap != null)
			{
				shader.SetTexture("CellMap", shroud.CellMap);
				shader.SetVec("CellMapSize", shroud.CellMapSize.X, shroud.CellMapSize.Y);
				shader.SetVec("HasShroud", shroud.HasShroud ? 1f : 0f);
			}
			else
			{
				shader.SetTexture("CellMap", sheet.GetTexture());
				shader.SetVec("CellMapSize", 1f, 1f);
				shader.SetVec("HasShroud", 0f);
			}

			var scanning = RadarScan && shroud?.CellMap != null && shroud.HasShroud && world.RenderPlayer != null;
			if (scanning)
				UpdateScan(world);

			shader.SetTexture("ScanMap", scanning && scanMap != null ? scanMap : sheet.GetTexture());
			shader.SetVec("HasScan", scanning && scanMap != null ? 1f : 0f);
			shader.SetVec("Bounds", new float[] { bounds.Left, bounds.Top, bounds.Width, bounds.Height }, 4);
			shader.SetVec("View", new[] { U(tl.X), V(tl.Y), U(br.X), V(br.Y) }, 4);
			shader.SetVec("SweepPeriod", SweepPeriod);
			shader.SetVec("BorderColor", BracketColor.R / 255f, BracketColor.G / 255f, BracketColor.B / 255f);
			shader.SetVec("SweepColor", SweepColor.R / 255f, SweepColor.G / 255f, SweepColor.B / 255f);
			shader.PrepareRender();
			Game.Renderer.DrawBatch(quad, shader, 0, 6, PrimitiveType.TriangleList);

			// The radar drew its pings under this layer: draw them again on top
			if (drawPings != null)
			{
				Game.Renderer.EnableScissor(mapRect);
				drawPings.Invoke(radar, null);
				Game.Renderer.DisableScissor();
			}

			return true;
		}

		/// <summary>
		/// Per-cell radar scan for the render player, same layout as PxShroudRenderer.CellMap (BGRA bytes, read as
		/// .rgba): alpha = the radar sees the terrain here, rgb = colour of an enemy building on this cell.
		/// </summary>
		void UpdateScan(World world)
		{
			if (scanWorld != world)
			{
				scanMap?.Dispose();
				scanMap = null;
				scanWorld = world;
				nextScan = 0;
			}

			if (Game.RunTime < nextScan && scanMap != null)
				return;

			nextScan = Game.RunTime + ScanInterval;
			var map = world.Map;
			var size = map.MapSize;
			if (scanMap == null)
			{
				scanWidth = Exts.NextPowerOf2(size.X);
				scanHeight = Exts.NextPowerOf2(size.Y);
				scanData = new byte[4 * scanWidth * scanHeight];
				scanMap = Game.Renderer.CreateTexture();
				scanMap.ScaleFilter = TextureScaleFilter.Linear;
			}

			var player = world.RenderPlayer;

			// Shroud bubbles of active enemy Gap Generators hide terrain and buildings from the radar
			var gaps = world.ActorsWithTrait<CreatesShroud>()
				.Where(p => !p.Trait.IsTraitDisabled && p.Actor.IsInWorld &&
					p.Trait.Info is CreatesShroudInfo ci && ci.ValidRelationships.HasRelationship(p.Actor.Owner.RelationshipWith(player)))
				.Select(p => (Center: p.Actor.CenterPosition, Range: p.Trait.Info.Range.Length))
				.ToArray();

			bool Hidden(int x, int y)
			{
				var center = map.CenterOfCell(new MPos(x, y).ToCPos(map));
				foreach (var g in gaps)
					if ((center - g.Center).HorizontalLengthSquared <= (long)g.Range * g.Range)
						return true;

				return false;
			}

			var bounds = map.Bounds;
			Array.Clear(scanData, 0, scanData.Length);
			for (var y = 0; y < size.Y; y++)
			{
				var sy = Math.Clamp(y, bounds.Top, bounds.Bottom - 1);
				for (var x = 0; x < size.X; x++)
				{
					var sx = Math.Clamp(x, bounds.Left, bounds.Right - 1);
					scanData[4 * (y * scanWidth + x) + 3] = (byte)(gaps.Length > 0 && Hidden(sx, sy) ? 0 : 255);
				}
			}

			// Enemy buildings: a blip in the owner's colour on every footprint cell
			foreach (var a in world.ActorsHavingTrait<Building>())
			{
				if (!a.IsInWorld || a.IsDead || a.Owner.NonCombatant || a.Owner.IsAlliedWith(player))
					continue;

				if (a.TraitsImplementing<Cloak>().Any(c => c.Cloaked))
					continue;

				var colour = a.Owner.Color;
				foreach (var cell in a.Trait<Building>().Info.OccupiedTiles(a.Location))
				{
					var uv = cell.ToMPos(map);
					if (!map.Contains(uv) || uv.U < 0 || uv.V < 0 || uv.U >= size.X || uv.V >= size.Y)
						continue;

					var o = 4 * (uv.V * scanWidth + uv.U);
					if (scanData[o + 3] == 0)
						continue;

					scanData[o] = colour.B;
					scanData[o + 1] = colour.G;
					scanData[o + 2] = colour.R;
				}
			}

			scanMap.SetData(scanData, scanWidth, scanHeight);
		}

		public override void Removed()
		{
			base.Removed();
			scanMap?.Dispose();
			scanMap = null;
		}

		public override void Draw()
		{
			var rb = RenderBounds;
			var cr = Game.Renderer.RgbaColorRenderer;

			if (!IsActive() || !DrawMinimap())
			{
				// No radar signal (or an unsupported map grid): scanlines over whatever is shown
				Game.Renderer.EnableScissor(rb);
				for (var y = rb.Y; y < rb.Bottom; y += ScanlinePeriod)
					cr.FillRect(new float3(rb.X, y, 0), new float3(rb.Right, y + 1, 0), Color.FromArgb(46, 0, 0, 0));

				Game.Renderer.DisableScissor();
			}

			// Corner brackets
			var l = BracketLength;
			var x0 = rb.X + BracketInset;
			var y0 = rb.Y + BracketInset;
			var x1 = rb.Right - BracketInset;
			var y1 = rb.Bottom - BracketInset;
			void Fill(int ax, int ay, int bx, int by) => cr.FillRect(new float3(ax, ay, 0), new float3(bx, by, 0), BracketColor);

			Fill(x0, y0, x0 + l, y0 + 2);
			Fill(x0, y0, x0 + 2, y0 + l);
			Fill(x1 - l, y0, x1, y0 + 2);
			Fill(x1 - 2, y0, x1, y0 + l);
			Fill(x0, y1 - 2, x0 + l, y1);
			Fill(x0, y1 - l, x0 + 2, y1);
			Fill(x1 - l, y1 - 2, x1, y1);
			Fill(x1 - 2, y1 - l, x1, y1);
		}
	}
}
