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
using System.Reflection;
using System.Text.RegularExpressions;
using OpenRA.Effects;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Effects;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Replaces the engine's small \"+$75\" money text (oil rigs, refineries, bounties, selling...) with an HD popup:",
		"beveled gold digits (red when spending) next to a spinning coin, popping in, rising with sparkles and a shine sweep.",
		"Art from artsrc/fx/make_cash.py (image `pxcash`).")]
	public class PxCashPopupsInfo : TraitInfo
	{
		public readonly string Image = "pxcash";

		[Desc("Transparent outline/glow margin around each glyph sprite, in sprite pixels (make_cash.py PAD).")]
		public readonly int GlyphPadding = 12;

		[Desc("Extra space between glyphs, in sprite pixels.")]
		public readonly int Tracking = 3;

		[Desc("Ticks the popup is shown.")]
		public readonly int Duration = 55;

		[Desc("Overall size multiplier.")]
		public readonly float Scale = 0.8f;

		[Desc("How far it rises, in screen pixels.")]
		public readonly int Rise = 26;

		public override object Create(ActorInitializer init) { return new PxCashPopups(this); }
	}

	public class PxCashPopups : ITickRender
	{
		static readonly Regex CashText = new(@"^[+-]\$\d+$", RegexOptions.Compiled);
		static readonly FieldInfo TextField = typeof(FloatingText).GetField("text", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo PosField = typeof(FloatingText).GetField("pos", BindingFlags.NonPublic | BindingFlags.Instance);

		readonly PxCashPopupsInfo info;
		readonly List<FloatingText> found = new();

		public PxCashPopups(PxCashPopupsInfo info)
		{
			this.info = info;
		}

		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			// Runs right after each world tick, before anything is drawn, so the stock text never shows
			if (TextField == null || PosField == null)
				return;

			found.Clear();
			foreach (var e in self.World.Effects)
				if (e is FloatingText ft && CashText.IsMatch((string)TextField.GetValue(ft)))
					found.Add(ft);

			foreach (var ft in found)
			{
				self.World.Remove(ft);
				self.World.Add(new PxCashPopup(self.World, (WPos)PosField.GetValue(ft), (string)TextField.GetValue(ft), info));
			}
		}
	}

	public class PxCashPopup : IEffect
	{
		// World units per screen pixel (1024 per 24 pixel cell)
		const float WorldPerPixel = 1024f / 24f;

		// Draw above everything else in the world
		const int ZOffset = 1 << 20;

		readonly World world;
		readonly WPos pos;
		readonly PxCashPopupsInfo info;
		readonly (ISpriteSequence Seq, float X)[] glyphs;
		readonly ISpriteSequence coin;
		readonly ISpriteSequence sparkle;
		readonly ISpriteSequence glow;
		readonly ISpriteSequence backing;
		readonly float width;
		readonly float height;
		readonly bool spending;
		readonly (float X, float Y, float Delay, float Size)[] sparkles;
		float age;
		long lastTime = -1;

		public PxCashPopup(World world, WPos pos, string text, PxCashPopupsInfo info)
		{
			this.world = world;
			this.pos = pos;
			this.info = info;
			spending = text.StartsWith('-');

			var sequences = world.Map.Sequences;
			var style = spending ? "red" : "gold";
			coin = sequences.GetSequence(info.Image, "coin");
			sparkle = sequences.GetSequence(info.Image, "sparkle");
			glow = sequences.GetSequence("pxfx", "glow");
			backing = sequences.GetSequence(info.Image, "backing");

			// Lay the glyphs out left to right in screen pixels, using each sprite's own width
			glyphs = new (ISpriteSequence, float)[text.Length];
			var x = 0f;
			for (var i = 0; i < text.Length; i++)
			{
				var name = text[i] switch { '+' => "plus", '-' => "minus", '$' => "dollar", _ => text[i].ToString() };
				var seq = sequences.GetSequence(info.Image, $"{style}-{name}");
				var sprite = seq.GetSprite(0);
				var advance = (sprite.Size.X - 2 * info.GlyphPadding + info.Tracking) * seq.Scale;
				glyphs[i] = (seq, x + advance / 2);
				x += advance;
				height = Math.Max(height, (sprite.Size.Y - 2 * info.GlyphPadding) * seq.Scale);
			}

			width = x;

			var random = new MersenneTwister(Game.CosmeticRandom.Next());
			sparkles = new (float, float, float, float)[4];
			for (var i = 0; i < sparkles.Length; i++)
				sparkles[i] = (random.NextFloat() * (width + height) - height / 2, (random.NextFloat() - 0.5f) * height * 1.4f,
					0.1f + random.NextFloat() * 0.45f, 0.5f + random.NextFloat() * 0.5f);
		}

		public void Tick(World world)
		{
			if (age >= info.Duration)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		static float EaseOutCubic(float t) { return 1 - (1 - t) * (1 - t) * (1 - t); }

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			// Animate with real frame time (smooth at any frame rate), at game speed, frozen while paused
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)world.Timestep;
			lastTime = now;
			if (!world.Paused)
				age += dt;

			if (world.FogObscures(pos) || world.ShroudObscures(pos))
				return SpriteRenderable.None;

			return RenderInner();
		}

		IEnumerable<IRenderable> RenderInner()
		{
			var t = Math.Clamp(age / info.Duration, 0, 1);

			// Pop in with an overshoot, rise and ease out, fade at the end
			var pop = t < 0.1f ? 0.4f + 0.8f * (t / 0.1f) : t < 0.2f ? 1.2f - 0.2f * ((t - 0.1f) / 0.1f) : 1f;
			var scale = pop * info.Scale;
			var alpha = Math.Min(t / 0.06f, 1) * (t > 0.7f ? 1 - (t - 0.7f) / 0.3f : 1);
			var rise = 8 + info.Rise * EaseOutCubic(t);

			// Coin on the left, text to its right; the whole group is centred on the source
			var coinSize = height * 1.25f;
			var gap = height * 0.2f;
			var total = coinSize + gap + width;
			var left = -total / 2;

			// Soft dark backing so the text reads on any terrain
			var plate = backing.GetSprite(0);
			var plateHeight = Math.Max(height * 2f, (total + height) * plate.Size.Y / plate.Size.X);
			yield return Sprite(backing, 0, 0, rise, scale, plateHeight, alpha, new float3(1, 1, 1), -2);

			var frame = (int)(age * 0.6f) % coin.Length;
			yield return Sprite(coin, frame, left + coinSize / 2, rise, scale, coinSize, alpha, new float3(1, 1, 1), 1);

			var textLeft = left + coinSize + gap;
			foreach (var (seq, x) in glyphs)
			{
				var s = seq.GetSprite(0);
				yield return Sprite(seq, 0, textLeft + x, rise, scale, s.Size.Y * seq.Scale, alpha, new float3(1, 1, 1), 1);
			}

			// A shine sweeping across the digits shortly after they appear
			if (t > 0.15f && t < 0.5f)
			{
				var st = (t - 0.15f) / 0.35f;
				var sx = textLeft + width * st;
				var shine = MathF.Sin(st * MathF.PI) * 0.6f * alpha;
				var tint = spending ? new float3(1, 0.6f, 0.5f) : new float3(1, 0.9f, 0.6f);
				yield return Sprite(glow, 0, sx, rise, scale, height * 1.6f, shine, tint, 2);
			}

			// Twinkling sparkles around the popup, drifting up a little faster than it
			foreach (var (x, y, delay, size) in sparkles)
			{
				var st = (t - delay) / 0.3f;
				if (st <= 0 || st >= 1)
					continue;

				var a = MathF.Sin(st * MathF.PI) * alpha;
				var tint = spending ? new float3(1, 0.7f, 0.6f) : new float3(1, 0.95f, 0.7f);
				yield return Sprite(sparkle, 0, left + coinSize + x, rise + y - 6 * st, scale, height * 0.9f * size, a, tint, 3);
			}
		}

		// x, up: screen pixels from the source (up = above it); size: desired height in screen pixels
		SpriteRenderable Sprite(ISpriteSequence seq, int frame, float x, float up, float scale, float size, float alpha, in float3 tint, int z)
		{
			var sprite = seq.GetSprite(frame);
			var offset = new WVec((int)(x * scale * WorldPerPixel), 0, (int)(up * WorldPerPixel));
			return new SpriteRenderable(sprite, pos + offset, WVec.Zero, ZOffset + z - offset.Z, null,
				scale * size / sprite.Size.Y, alpha, tint, TintModifiers.IgnoreWorldTint, true);
		}
	}
}
