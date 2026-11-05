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
using OpenRA.Mods.RAPX.Traits.Render;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Graphics
{
	/// <summary>
	/// Draws slanted, framed health and status bars: metallic rim, recessed track, gradient fill with gloss,
	/// segment ticks, damage trail, an owner-coloured cap, a pulse at critical health and a shimmer on status bars.
	/// </summary>
	public class PxSelectionBarsRenderable : IRenderable, IFinalizedRenderable
	{
		const int CapWidth = 3;

		static readonly Color HealthFull = Color.FromArgb(255, 70, 230, 95);
		static readonly Color HealthHalf = Color.FromArgb(255, 250, 205, 45);
		static readonly Color HealthLow = Color.FromArgb(255, 235, 45, 35);
		static readonly Color DamageTrail = Color.FromArgb(255, 255, 120, 40);

		static readonly Color Shadow = Color.FromArgb(120, 0, 0, 0);
		static readonly Color RimTop = Color.FromArgb(240, 120, 128, 140);
		static readonly Color RimBottom = Color.FromArgb(240, 18, 20, 24);
		static readonly Color TrackTop = Color.FromArgb(235, 6, 8, 10);
		static readonly Color TrackBottom = Color.FromArgb(235, 34, 38, 44);
		static readonly Color Tick = Color.FromArgb(150, 0, 0, 0);
		static readonly Color Gloss = Color.FromArgb(110, 255, 255, 255);
		static readonly Color LeadingEdge = Color.FromArgb(190, 255, 255, 255);

		readonly Actor actor;
		readonly Rectangle decorationBounds;
		readonly PxSelectionDecorationsInfo info;

		// Slope of the slanted bar ends, in horizontal pixels per vertical pixel.
		readonly float slope;

		public PxSelectionBarsRenderable(WPos pos, Actor actor, Rectangle decorationBounds, PxSelectionDecorationsInfo info,
			bool displayHealth, bool displayExtra)
		{
			Pos = pos;
			this.actor = actor;
			this.decorationBounds = decorationBounds;
			this.info = info;
			DisplayHealth = displayHealth;
			DisplayExtra = displayExtra;
			slope = info.HealthBarHeight > 0 ? (float)info.Skew / info.HealthBarHeight : 0;
		}

		public WPos Pos { get; }
		public bool DisplayHealth { get; }
		public bool DisplayExtra { get; }

		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec)
		{
			return new PxSelectionBarsRenderable(Pos + vec, actor, decorationBounds, info, DisplayHealth, DisplayExtra);
		}

		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		public void Render(WorldRenderer wr)
		{
			if (!actor.IsInWorld || actor.IsDead)
				return;

			var tl = wr.Viewport.WorldToViewPx(new int2(decorationBounds.Left, decorationBounds.Top));
			var tr = wr.Viewport.WorldToViewPx(new int2(decorationBounds.Right, decorationBounds.Top));

			// Bar bottoms are measured in base (un-slanted) coordinates; the top edge is shifted right by Skew.
			var left = tl.X + 1;
			var right = tr.X - 1 - info.Skew;
			var y = tl.Y - 2;
			var slantBase = y;

			if (DisplayHealth)
			{
				var health = actor.TraitOrDefault<IHealth>();
				if (health != null && !health.IsDead)
				{
					DrawHealthBar(health, left, right, y - info.HealthBarHeight, y, slantBase);
					y++;
				}
			}

			if (DisplayExtra)
			{
				foreach (var bar in actor.TraitsImplementing<ISelectionBar>())
				{
					var value = bar.GetValue();
					if (value == 0 && !bar.DisplayWhenEmpty)
						continue;

					DrawExtraBar(value, bar.GetColor(), left + CapWidth + 1, right, y, y + info.ExtraBarHeight, slantBase);
					y += info.ExtraBarHeight + 1;
				}
			}
		}

		void DrawHealthBar(IHealth health, int x0, int x1, int top, int bottom, int slantBase)
		{
			var value = Math.Clamp((float)health.HP / health.MaxHP, 0, 1);
			var displayValue = Math.Clamp((float)health.DisplayHP / health.MaxHP, 0, 1);
			var color = HealthColor(value);

			// Owner-coloured cap on the left end.
			var owner = actor.OwnerColor();
			Quad(x0 + 1, x0 + CapWidth + 1, top + 1, bottom + 1, slantBase, Shadow, Shadow);
			Quad(x0, x0 + CapWidth, top, bottom, slantBase, Lighten(owner, 0.35f), Darken(owner, 0.5f));

			x0 += CapWidth + 1;
			DrawFrame(x0, x1, top, bottom, slantBase);

			var ix0 = x0 + 1;
			var ix1 = x1 - 1;
			var it = top + 1;
			var ib = bottom - 1;
			var width = ix1 - ix0;
			var fillEnd = ix0 + width * value;

			if (displayValue > value)
				Quad(fillEnd, ix0 + width * displayValue, it, ib, slantBase, Lighten(DamageTrail, 0.3f), Darken(DamageTrail, 0.55f));

			DrawFill(ix0, fillEnd, it, ib, slantBase, color);

			// Critical damage: the fill pulses red.
			if (value < 0.25f)
			{
				var pulse = (float)(0.5 + 0.5 * Math.Sin(Game.RunTime / 140.0));
				var glow = Color.FromArgb((int)(40 + 110 * pulse), 255, 70, 50);
				Quad(ix0, fillEnd, it, ib, slantBase, glow, glow);
			}

			if (info.SegmentWidth > 0 && width > info.SegmentWidth * 2)
			{
				var count = (int)Math.Round((float)width / info.SegmentWidth);
				var step = (float)width / count;
				for (var i = 1; i < count; i++)
				{
					var x = (float)Math.Round(ix0 + i * step);
					Quad(x, x + 1, it, ib, slantBase, Tick, Tick);
				}
			}

			if (value > 0 && value < 1)
				Quad(fillEnd - 1, fillEnd, it, ib, slantBase, LeadingEdge, LeadingEdge);
		}

		void DrawExtraBar(float value, Color color, int x0, int x1, int top, int bottom, int slantBase)
		{
			value = Math.Clamp(value, 0, 1);

			DrawFrame(x0, x1, top, bottom, slantBase);

			var ix0 = x0 + 1;
			var ix1 = x1 - 1;
			var it = top + 1;
			var ib = bottom - 1;
			var fillEnd = ix0 + (ix1 - ix0) * value;

			DrawFill(ix0, fillEnd, it, ib, slantBase, color);

			// A highlight band sweeps along the filled part.
			const float Band = 14;
			var travel = fillEnd - ix0 + Band;
			if (travel > Band)
			{
				var center = ix0 - Band / 2 + (float)(Game.RunTime * 0.05 % travel);
				ShimmerHalf(center - Band / 2, center, ix0, fillEnd, it, ib, slantBase, false);
				ShimmerHalf(center, center + Band / 2, ix0, fillEnd, it, ib, slantBase, true);
			}

			if (value > 0 && value < 1)
				Quad(fillEnd - 1, fillEnd, it, ib, slantBase, LeadingEdge, LeadingEdge);
		}

		void DrawFrame(int x0, int x1, int top, int bottom, int slantBase)
		{
			Quad(x0 + 1, x1 + 1, top + 1, bottom + 1, slantBase, Shadow, Shadow);
			Quad(x0, x1, top, bottom, slantBase, RimTop, RimBottom);
			Quad(x0 + 1, x1 - 1, top + 1, bottom - 1, slantBase, TrackTop, TrackBottom);
		}

		void DrawFill(float x0, float x1, int top, int bottom, int slantBase, Color color)
		{
			if (x1 <= x0)
				return;

			// Bright upper half, darker lower half, and a 1px gloss line along the top.
			var mid = top + (bottom - top) / 2f;
			Quad(x0, x1, top, mid, slantBase, Lighten(color, 0.45f), color);
			Quad(x0, x1, mid, bottom, slantBase, color, Darken(color, 0.45f));
			Quad(x0, x1, top, top + 1, slantBase, Gloss, Gloss);
		}

		void ShimmerHalf(float a, float b, float clip0, float clip1, int top, int bottom, int slantBase, bool fadeOut)
		{
			var c0 = Math.Max(a, clip0);
			var c1 = Math.Min(b, clip1);
			if (c1 <= c0)
				return;

			// Alpha rises linearly towards the band center, then falls again.
			int Alpha(float x)
			{
				var t = (x - a) / (b - a);
				return (int)(130 * (fadeOut ? 1 - t : t));
			}

			var left = Color.FromArgb(Alpha(c0), 255, 255, 255);
			var right = Color.FromArgb(Alpha(c1), 255, 255, 255);
			var cr = Game.Renderer.RgbaColorRenderer;
			cr.FillRect(
				Point(c0, top, slantBase), Point(c1, top, slantBase), Point(c1, bottom, slantBase), Point(c0, bottom, slantBase),
				left, right, right, left);
		}

		// Fills a slanted quad between base x positions x0..x1; each row is shifted right by slope * (slantBase - y).
		void Quad(float x0, float x1, float top, float bottom, int slantBase, Color topColor, Color bottomColor)
		{
			if (x1 <= x0 || bottom <= top)
				return;

			Game.Renderer.RgbaColorRenderer.FillRect(
				Point(x0, top, slantBase), Point(x1, top, slantBase), Point(x1, bottom, slantBase), Point(x0, bottom, slantBase),
				topColor, topColor, bottomColor, bottomColor);
		}

		float3 Point(float x, float y, int slantBase)
		{
			return new float3(x + slope * (slantBase - y), y, 0);
		}

		static Color HealthColor(float value)
		{
			return value >= 0.5f
				? Mix(HealthHalf, HealthFull, (value - 0.5f) * 2)
				: Mix(HealthLow, HealthHalf, value * 2);
		}

		static Color Mix(Color a, Color b, float t)
		{
			t = Math.Clamp(t, 0, 1);
			return Color.FromArgb(
				(int)(a.A + (b.A - a.A) * t),
				(int)(a.R + (b.R - a.R) * t),
				(int)(a.G + (b.G - a.G) * t),
				(int)(a.B + (b.B - a.B) * t));
		}

		static Color Lighten(Color c, float t) { return Mix(c, Color.FromArgb(c.A, 255, 255, 255), t); }
		static Color Darken(Color c, float t) { return Mix(c, Color.FromArgb(c.A, 0, 0, 0), t); }

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
