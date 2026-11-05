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
using OpenRA.Mods.RAPX.Traits.Render;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Graphics
{
	/// <summary>
	/// Hologram rally point: the route is a honeycomb road of small hex cells lying on the ground (snapped to a fixed
	/// world lattice so cells never swim when the route changes) with energy waves running from the building to the
	/// target, waypoints are medium hexes and the rally point itself is one big glowing hex cell with rotating inner
	/// rings and outgoing pulses. Hexes are squashed vertically by the camera tilt like PxHexGridRenderable.
	/// Drawn in world pixels with alpha blending only (additive glow vanishes on snow).
	/// </summary>
	public class PxHexRallyRenderable : IRenderable, IFinalizedRenderable
	{
		static readonly float Sqrt3 = MathF.Sqrt(3);
		static readonly Color Shadow = Color.FromArgb(90, 0, 0, 0);

		readonly WPos[] nodes;
		readonly PxRallyPointInfo info;
		readonly Color color;
		readonly bool showLine;

		public PxHexRallyRenderable(WPos[] nodes, PxRallyPointInfo info, Color color, bool showLine)
		{
			this.nodes = nodes;
			this.info = info;
			this.color = color;
			this.showLine = showLine;
		}

		public WPos Pos => nodes[^1];
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec)
		{
			var offset = vec;
			return new PxHexRallyRenderable(nodes.Select(n => n + offset).ToArray(), info, color, showLine);
		}

		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }

		float Tilt => MathF.Sin(info.CameraElevation * MathF.PI / 180);

		// Ground plane coordinates: world pixels with the vertical axis un-squashed, so the hex lattice is regular.
		float2 ToGround(in float3 p) { return new float2(p.X, p.Y / Tilt); }
		float3 ToView(in float2 g) { return new float3(g.X, g.Y * Tilt, g.Y * Tilt); }

		public void Render(WorldRenderer wr)
		{
			var points = nodes.Select(n => ToGround(wr.Screen3DPxPosition(n))).ToArray();
			var time = Game.RunTime / 1000f;
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			var hot = Lerp(color, Color.White, 0.6f);
			var outline = Lerp(color, Color.Black, 0.7f);
			var end = points[^1];

			if (showLine)
				DrawRoad(cr, points, time, hot, outline);

			for (var i = 1; i < points.Length - 1; i++)
				DrawWaypoint(cr, points[i], time, outline);

			DrawTarget(cr, end, time, hot, outline);
		}

		void DrawRoad(RgbaColorRenderer cr, float2[] points, float time, Color hot, Color outline)
		{
			var s = info.HexSize;
			var stop = info.TargetHexSize * 1.15f;
			var end = points[^1];

			// Lattice cells whose centre is close to the route, with their distance along it.
			var cells = new Dictionary<int2, (float Along, float Off)>();
			var travelled = 0f;
			for (var i = 0; i < points.Length - 1; i++)
			{
				var a = points[i];
				var b = points[i + 1];
				var seg = b - a;
				var len = seg.Length;
				if (len < 0.01f)
					continue;

				var minU = MathF.Min(a.X, b.X) - 2 * s;
				var maxU = MathF.Max(a.X, b.X) + 2 * s;
				var minV = MathF.Min(a.Y, b.Y) - 2 * s;
				var maxV = MathF.Max(a.Y, b.Y) + 2 * s;
				for (var q = (int)MathF.Floor(minU / (1.5f * s)); q <= (int)MathF.Ceiling(maxU / (1.5f * s)); q++)
				{
					var r0 = (int)MathF.Floor(minV / (Sqrt3 * s) - q / 2f) - 1;
					var r1 = (int)MathF.Ceiling(maxV / (Sqrt3 * s) - q / 2f) + 1;
					for (var r = r0; r <= r1; r++)
					{
						var c = HexCentre(q, r, s);
						var t = Math.Clamp(Dot(c - a, seg) / (len * len), 0, 1);
						var off = (c - (a + t * seg)).Length;
						if (off > 0.95f * s || (c - end).Length < stop)
							continue;

						var key = new int2(q, r);
						if (!cells.TryGetValue(key, out var old) || off < old.Off)
							cells[key] = (travelled + t * len, off);
					}
				}

				travelled += len;
			}

			var view = new float3[6];
			var shadowOffset = new float2(0.6f, 0.9f);
			foreach (var kv in cells)
			{
				var c = HexCentre(kv.Key.X, kv.Key.Y, s);
				var along = kv.Value.Along;
				var core = 1 - kv.Value.Off / (0.95f * s);

				// Energy waves run from the building towards the target; the road fades in at the building exit.
				var phase = Frac((along - time * info.PulseSpeed) / info.PulseSpacing);
				var wave = MathF.Pow(MathF.Max(0, 1 - MathF.Abs(phase - 0.5f) * 4), 2);
				var fadeIn = Math.Clamp(along / (3 * s), 0.2f, 1);
				var fadeOut = Math.Clamp((travelled - along - stop) / (2 * s) + 0.6f, 0.4f, 1);
				var k = fadeIn * fadeOut * (0.55f + 0.45f * core);

				Hex(view, c, 0.86f * s, 0);
				for (var e = 0; e < 6; e++)
					cr.DrawLine(Offset(view[e], shadowOffset), Offset(view[(e + 1) % 6], shadowOffset), 0.9f, WithAlpha(Shadow, Shadow.A * k));

				var fill = WithAlpha(Lerp(color, Color.White, 0.5f * wave), (70 + 150 * wave) * k);
				FillHex(cr, view, fill);
				for (var e = 0; e < 6; e++)
				{
					cr.DrawLine(view[e], view[(e + 1) % 6], 1f, WithAlpha(outline, 210 * k));
					cr.DrawLine(view[e], view[(e + 1) % 6], 0.45f, WithAlpha(Lerp(hot, Color.White, wave), (150 + 100 * wave) * k));
				}
			}
		}

		void DrawWaypoint(RgbaColorRenderer cr, float2 c, float time, Color outline)
		{
			var view = new float3[6];
			var glow = 0.5f + 0.5f * MathF.Sin(time * 4);
			var size = info.HexSize * 1.9f;
			Hex(view, c, size, 0);
			FillHex(cr, view, WithAlpha(color, 90 + 60 * glow));
			for (var e = 0; e < 6; e++)
			{
				cr.DrawLine(view[e], view[(e + 1) % 6], 1.4f, WithAlpha(outline, 200));
				cr.DrawLine(view[e], view[(e + 1) % 6], 0.6f, WithAlpha(Color.White, 200 + 55 * glow));
			}
		}

		void DrawTarget(RgbaColorRenderer cr, float2 c, float time, Color hot, Color outline)
		{
			var view = new float3[6];
			var inner = new float3[6];
			var size = info.TargetHexSize;
			var breathe = 0.5f + 0.5f * MathF.Sin(time * 3);

			// Soft glow halo around the cell.
			for (var k = 3; k >= 1; k--)
			{
				Hex(view, c, size * (1 + 0.16f * k + 0.04f * breathe), 0);
				FillHex(cr, view, WithAlpha(color, 22 - 5 * k));
			}

			// Outgoing hex pulses.
			for (var k = 0; k < 2; k++)
			{
				var p = Frac(time / 1.8f + k * 0.5f);
				Hex(view, c, size * (1 + 0.9f * p), 0);
				var fade = (1 - p) * (1 - p);
				for (var e = 0; e < 6; e++)
					cr.DrawLine(view[e], view[(e + 1) % 6], 1.6f * (1 - p) + 0.4f, WithAlpha(hot, 190 * fade));
			}

			// Ground shadow, then the cell itself: a gradient from a bright core to the coloured rim.
			Hex(view, c + new float2(0.8f, 1.4f), size, 0);
			for (var e = 0; e < 6; e++)
				cr.DrawLine(view[e], view[(e + 1) % 6], 2.2f, Shadow);

			Hex(view, c, size, 0);
			var centre = ToView(c);
			var rim = WithAlpha(color, 150 + 40 * breathe);
			var core = WithAlpha(Lerp(color, Color.White, 0.75f), 220);
			for (var e = 0; e < 6; e++)
				cr.FillRect(centre, view[e], view[(e + 1) % 6], centre, core, rim, rim, core);

			// Rotating inner rings: one hex turning each way.
			for (var k = 0; k < 2; k++)
			{
				var dir = k == 0 ? 1 : -1;
				Hex(inner, c, size * (0.68f - 0.24f * k), dir * time * (0.8f + 0.5f * k));
				for (var e = 0; e < 6; e++)
				{
					cr.DrawLine(inner[e], inner[(e + 1) % 6], 1.1f, WithAlpha(outline, 120));
					cr.DrawLine(inner[e], inner[(e + 1) % 6], 0.5f, WithAlpha(Color.White, 210));
				}
			}

			// Crisp border with a dark outline so it reads on snow, and bright corner studs.
			for (var e = 0; e < 6; e++)
			{
				cr.DrawLine(view[e], view[(e + 1) % 6], 3.2f, WithAlpha(color, 70));
				cr.DrawLine(view[e], view[(e + 1) % 6], 1.8f, WithAlpha(outline, 230));
				cr.DrawLine(view[e], view[(e + 1) % 6], 0.9f, WithAlpha(Color.White, 240));
			}

			for (var e = 0; e < 6; e++)
			{
				var v = view[e];
				var r = 0.9f + 0.5f * breathe;
				cr.FillRect(v + new float3(0, -r, 0), v + new float3(r, 0, 0), v + new float3(0, r, 0), v + new float3(-r, 0, 0), Color.White);
			}

			// Light column rising from the centre.
			var top = centre + new float3(0, -size * 1.6f, 0);
			cr.DrawLine(centre, top, 3.2f, WithAlpha(color, 110), WithAlpha(color, 0));
			cr.DrawLine(centre, top, 1.1f, WithAlpha(Color.White, 220), WithAlpha(Color.White, 0));
		}

		void Hex(float3[] view, float2 c, float size, float rotation)
		{
			for (var i = 0; i < 6; i++)
			{
				var angle = rotation + MathF.PI / 3 * i;
				view[i] = ToView(new float2(c.X + size * MathF.Cos(angle), c.Y + size * MathF.Sin(angle)));
			}
		}

		static void FillHex(RgbaColorRenderer cr, float3[] view, Color c)
		{
			cr.FillRect(view[0], view[1], view[2], view[3], c);
			cr.FillRect(view[3], view[4], view[5], view[0], c);
		}

		static float2 HexCentre(int q, int r, float size) { return new float2(size * 1.5f * q, size * Sqrt3 * (r + q / 2f)); }
		static float3 Offset(in float3 v, in float2 d) { return new float3(v.X + d.X, v.Y + d.Y, v.Z); }
		static float Dot(in float2 a, in float2 b) { return a.X * b.X + a.Y * b.Y; }
		static float Frac(float v) { return v - MathF.Floor(v); }
		static Color WithAlpha(Color c, float alpha) { return Color.FromArgb((int)Math.Clamp(alpha, 0, 255), c.R, c.G, c.B); }

		static Color Lerp(Color a, Color b, float t)
		{
			return Color.FromArgb(a.A, (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}
	}
}
