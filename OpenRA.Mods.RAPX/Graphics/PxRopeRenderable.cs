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
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Graphics
{
	/// <summary>
	/// A fast rope (IDEA-47): a polyline through world points drawn as a dark outline, a coloured core and a thin
	/// highlight on its lit (left) side, so the braided nylon reads as round at the HD zoom. Sorted at Pos + ZOffset
	/// like any world renderable.
	/// </summary>
	public sealed class PxRopeRenderable : IRenderable, IFinalizedRenderable
	{
		readonly WPos[] points;
		readonly float width;
		readonly Color core, edge, light;
		readonly float alpha;

		public PxRopeRenderable(WPos[] points, WPos pos, int zOffset, float width, Color core, Color edge, Color light, float alpha = 1f)
		{
			this.points = points;
			Pos = pos;
			ZOffset = zOffset;
			this.width = width;
			this.core = core;
			this.edge = edge;
			this.light = light;
			this.alpha = alpha;
		}

		public WPos Pos { get; }
		public int ZOffset { get; }
		public bool IsDecoration => false;

		public IRenderable WithZOffset(int newOffset) { return new PxRopeRenderable(points, Pos, newOffset, width, core, edge, light, alpha); }

		public IRenderable OffsetBy(in WVec vec)
		{
			var moved = new WPos[points.Length];
			for (var i = 0; i < points.Length; i++)
				moved[i] = points[i] + vec;

			return new PxRopeRenderable(moved, Pos + vec, ZOffset, width, core, edge, light, alpha);
		}

		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		Color Fade(Color c) { return alpha >= 1f ? c : Color.FromArgb((int)(c.A * alpha), c.R, c.G, c.B); }

		public void Render(WorldRenderer wr)
		{
			if (points.Length < 2)
				return;

			var r = Game.Renderer.WorldRgbaColorRenderer;

			// Unjoined segments (joints spike on sharp bends) and distinct points: a zero-length segment (hands at the top) makes
			// the joint maths blow up into a spike across the screen
			var list = new List<float3>(points.Length);
			foreach (var p in points)
			{
				var sp = wr.Screen3DPosition(p);
				if (list.Count > 0)
				{
					var d = sp - list[^1];
					if (d.X * d.X + d.Y * d.Y < 0.25f)
						continue;
				}

				list.Add(sp);
			}

			if (list.Count < 2)
				return;

			var screen = list.ToArray();

			// One world pixel is 1024 / 24 world units; widths are given in world pixels
			var px = wr.ScreenVector(new WVec(1024, 0, 0))[0] / 24f;
			var w = width * px;
			r.DrawLine(screen, w * 1.6f, Fade(edge));
			r.DrawLine(screen, w, Fade(core));

			var shift = new float3(-w * 0.18f, 0, 0);
			for (var i = 0; i < screen.Length; i++)
				screen[i] += shift;

			r.DrawLine(screen, w * 0.35f, Fade(light));
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
