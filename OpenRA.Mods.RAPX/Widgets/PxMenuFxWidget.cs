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
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	public enum PxMenuFxEffect { Flicker, Pulse, Twinkle, Shine }

	/// <summary>
	/// Animated light over the main menu art: flickering fire and pulsing glow layers, rising embers,
	/// blinking warning lights and distant explosion flashes. Positions come from a manifest written by
	/// artsrc/menu-bg/make_menu_fx.py and are mapped onto the art the same way the FullscreenImage under it is (set the same Fit and HorizontalAlign).
	/// </summary>
	public class PxMenuFxWidget : Widget
	{
		public string Manifest = null;

		public FullscreenImageFit Fit = FullscreenImageFit.Cover;

		public float HorizontalAlign = 0.5f;

		[Desc("Number of embers in flight at once.")]
		public int Embers = 200;

		[Desc("Seconds between distant explosion flashes (random within this range).")]
		public float2 FlashInterval = new(2.5f, 7f);

		sealed class LayerInfo
		{
			public readonly string Image = null;
			public readonly Rectangle Rect = default;
			public readonly PxMenuFxEffect Effect = PxMenuFxEffect.Pulse;
			public readonly float Speed = 1f;
			public readonly float Min = 0f;
			public readonly float Max = 1f;
		}

		sealed class BeaconInfo
		{
			public readonly float2 Position = float2.Zero;
			public readonly float Size = 20f;
			public readonly float Period = 1.5f;
			public readonly float Phase = 0f;
		}

		sealed class Layer
		{
			public LayerInfo Info;
			public Sheet Sheet;
			public Sprite Sprite;
			public Sprite[] Strips;
			public float Seed;
		}

		// Width of the vertical slices a Shine layer is cut into, in layer texture pixels
		const int ShineStrip = 6;

		struct Ember
		{
			public float2 Pos;
			public float2 Vel;
			public float Age;
			public float Life;
			public float Size;
			public float Brightness;
			public float Seed;
			public float3 Color;
		}

		struct Flash
		{
			public float2 Pos;
			public float Age;
			public float Size;
		}

		static readonly float3 EmberHot = new(1f, 0.62f, 0.22f);
		static readonly float3 EmberCool = new(1f, 0.22f, 0.05f);
		static readonly float3 BeaconColor = new(1f, 0.12f, 0.08f);
		static readonly float3 FlashColor = new(1f, 0.45f, 0.15f);

		readonly ModData modData;
		readonly MersenneTwister random = new();
		readonly List<Layer> layers = new();
		readonly List<BeaconInfo> beacons = new();
		readonly List<Rectangle> emberSources = new();
		readonly List<Flash> flashes = new();
		Ember[] embers;
		float2 imageSize;
		Rectangle flashArea;
		Sheet dotSheet;
		Sprite dot;

		long lastTime;
		float time;
		float nextFlash;

		[ObjectCreator.UseCtor]
		public PxMenuFxWidget(ModData modData)
		{
			this.modData = modData;
		}

		void Load()
		{
			var nodes = MiniYaml.FromStream(modData.DefaultFileSystem.Open(Manifest), Manifest).ToDictionary(n => n.Key, n => n.Value);
			imageSize = FieldLoader.GetValue<int2>("ImageSize", nodes["ImageSize"].Value);
			flashArea = FieldLoader.GetValue<Rectangle>("FlashArea", nodes["FlashArea"].Value);

			foreach (var node in nodes["Layers"].Nodes)
			{
				var info = FieldLoader.Load<LayerInfo>(node.Value);
				var sprite = FullscreenImageWidget.LoadImage(modData, info.Image, out var sheet, BlendMode.Additive);

				// Shine starts its first sweep as soon as the menu appears
				var seed = info.Effect == PxMenuFxEffect.Shine ? 0 : random.NextFloat() * 100;
				var layer = new Layer { Info = info, Sheet = sheet, Sprite = sprite, Seed = seed };

				// There is no masking shader, so a sweeping band is drawn as slices of the layer, each lit by its distance to the band
				if (info.Effect == PxMenuFxEffect.Shine)
				{
					var b = sprite.Bounds;
					layer.Strips = Enumerable.Range(0, (b.Width + ShineStrip - 1) / ShineStrip)
						.Select(i => new Sprite(sheet, new Rectangle(i * ShineStrip, 0, Math.Min(ShineStrip, b.Width - i * ShineStrip), b.Height),
							0, float3.Zero, TextureChannel.RGBA, BlendMode.Additive))
						.ToArray();
				}

				layers.Add(layer);
			}

			foreach (var node in nodes["Beacons"].Nodes)
				beacons.Add(FieldLoader.Load<BeaconInfo>(node.Value));

			foreach (var node in nodes["EmberSources"].Nodes)
				emberSources.Add(FieldLoader.GetValue<Rectangle>(node.Key, node.Value.Value));

			var dotPath = Manifest[..(Manifest.LastIndexOf('/') + 1)] + "dot.png";
			dot = FullscreenImageWidget.LoadImage(modData, dotPath, out dotSheet, BlendMode.Additive);

			// Start mid-flight so the embers don't all appear at once
			embers = new Ember[Embers];
			for (var i = 0; i < embers.Length; i++)
			{
				Spawn(ref embers[i]);
				embers[i].Age = random.NextFloat() * embers[i].Life;
				embers[i].Pos += embers[i].Vel * embers[i].Age;
			}

			nextFlash = Lerp(FlashInterval.X, FlashInterval.Y, random.NextFloat());
			lastTime = Game.RunTime;
		}

		void Spawn(ref Ember e)
		{
			// Pick a source weighted by area
			var total = emberSources.Sum(r => r.Width * r.Height);
			var pick = random.NextFloat() * total;
			var source = emberSources[^1];
			foreach (var r in emberSources)
			{
				pick -= r.Width * r.Height;
				if (pick <= 0)
				{
					source = r;
					break;
				}
			}

			// A few large, fast, blurry embers read as sparks drifting close to the camera
			var near = random.NextFloat() < 0.08f;
			e.Pos = new float2(source.X + random.NextFloat() * source.Width, source.Y + random.NextFloat() * source.Height);
			e.Vel = new float2(Lerp(-15, 35, random.NextFloat()), -Lerp(35, 120, random.NextFloat())) * (near ? 2.2f : 1f);
			e.Age = 0;
			e.Life = Lerp(3f, 8f, random.NextFloat());
			e.Size = near ? Lerp(36, 64, random.NextFloat()) : Lerp(12, 24, random.NextFloat());
			e.Brightness = near ? Lerp(0.35f, 0.6f, random.NextFloat()) : Lerp(0.7f, 1.3f, random.NextFloat());
			e.Seed = random.NextFloat() * 100;
			e.Color = float3.Lerp(EmberHot, EmberCool, random.NextFloat());
		}

		void Update(float dt)
		{
			for (var i = 0; i < embers.Length; i++)
			{
				ref var e = ref embers[i];
				e.Age += dt;
				if (e.Age >= e.Life)
				{
					Spawn(ref e);
					continue;
				}

				// Sway sideways and slow down as they cool
				var sway = 18f * MathF.Sin(time * 1.7f + e.Seed);
				e.Pos += (e.Vel + new float2(sway, 0)) * dt;
				e.Vel *= 1f - 0.08f * dt;
			}

			nextFlash -= dt;
			if (nextFlash <= 0)
			{
				flashes.Add(new Flash
				{
					Pos = new float2(flashArea.X + random.NextFloat() * flashArea.Width, flashArea.Y + random.NextFloat() * flashArea.Height),
					Size = Lerp(0.7f, 1.3f, random.NextFloat())
				});

				nextFlash = Lerp(FlashInterval.X, FlashInterval.Y, random.NextFloat());
			}

			for (var i = flashes.Count - 1; i >= 0; i--)
			{
				var f = flashes[i];
				f.Age += dt;
				if (f.Age > 2.5f)
					flashes.RemoveAt(i);
				else
					flashes[i] = f;
			}
		}

		public override void Draw()
		{
			if (embers == null)
				Load();

			var (origin, size) = Fit == FullscreenImageFit.Contain
				? FullscreenImageWidget.ContainRect(imageSize, RenderBounds)
				: FullscreenImageWidget.CoverRect(imageSize, RenderBounds, HorizontalAlign);
			DrawOver(origin, size);
		}

		/// <summary>Advance the effects and draw them over art shown at origin with the given size (used outside the widget tree, e.g. by the load screen).</summary>
		public void DrawOver(float2 origin, float2 size)
		{
			if (embers == null)
				Load();

			var now = Game.RunTime;
			var dt = Math.Clamp((now - lastTime) / 1000f, 0f, 0.1f);
			lastTime = now;
			time += dt;
			Update(dt);

			var scale = size.X / imageSize.X;
			float2 ToScreen(float2 p) => origin + p * scale;

			var renderer = Game.Renderer.RgbaSpriteRenderer;

			foreach (var layer in layers)
			{
				var info = layer.Info;
				if (layer.Strips != null)
				{
					DrawShine(layer, ToScreen);
					continue;
				}

				var intensity = Lerp(info.Min, info.Max, Animate(info.Effect, time * info.Speed, layer.Seed));
				var tl = ToScreen(new float2(info.Rect.Left, info.Rect.Top));
				var br = ToScreen(new float2(info.Rect.Right, info.Rect.Bottom));
				renderer.DrawSprite(layer.Sprite,
					new float3(tl.X, tl.Y, 0), new float3(br.X, tl.Y, 0), new float3(br.X, br.Y, 0), new float3(tl.X, br.Y, 0),
					new float3(intensity, intensity, intensity), intensity);
			}

			foreach (var f in flashes)
			{
				// Fast flare-up, slow fade, with a secondary flicker as the fireball burns out
				var t = f.Age;
				var envelope = t < 0.08f ? t / 0.08f : MathF.Exp(-(t - 0.08f) * 2.2f);
				envelope *= 0.75f + 0.25f * Noise(t * 14 + f.Pos.X);
				DrawDot(ToScreen(f.Pos), 900 * f.Size * scale, 0.3f * envelope * FlashColor);
				DrawDot(ToScreen(f.Pos), 260 * f.Size * scale, 0.8f * envelope * FlashColor);
				DrawDot(ToScreen(f.Pos), 90 * f.Size * scale, envelope * new float3(1f, 0.85f, 0.6f));
			}

			foreach (var b in beacons)
			{
				var p = Frac(time / b.Period + b.Phase);
				var on = p < 0.1f ? 1f : MathF.Exp(-(p - 0.1f) * 18f);
				DrawDot(ToScreen(b.Position), b.Size * 5 * scale, 0.35f * on * BeaconColor);
				DrawDot(ToScreen(b.Position), b.Size * scale, on * new float3(1f, 0.5f, 0.45f));
			}

			foreach (var e in embers)
			{
				var t = e.Age / e.Life;
				var fade = Math.Min(1f, t * 6f) * (1f - Smoothstep(0.55f, 1f, t));
				var flicker = 0.6f + 0.4f * Noise(time * 6f + e.Seed);
				var cooled = float3.Lerp(e.Color, 0.8f * EmberCool, t);
				var brightness = e.Brightness * fade * flicker;
				DrawDot(ToScreen(e.Pos), e.Size * scale, brightness * cooled);
				DrawDot(ToScreen(e.Pos), 0.3f * e.Size * scale, brightness * (1 - t) * new float3(1f, 0.9f, 0.7f));
			}
		}

		void DrawShine(Layer layer, Func<float2, float2> toScreen)
		{
			// One sweep across the layer (plus run-in and run-out for the band width), then rest until the next period
			var info = layer.Info;
			var rect = info.Rect;
			var band = 0.15f * rect.Width;
			var sweep = Frac(time * info.Speed + layer.Seed) * 3f;
			if (sweep > 1f)
				return;

			var centre = rect.Left - band + sweep * (rect.Width + 2 * band);
			var stripWidth = (float)rect.Width / layer.Strips.Length;
			for (var i = 0; i < layer.Strips.Length; i++)
			{
				var x0 = rect.Left + i * stripWidth;
				var d = (x0 + stripWidth / 2 - centre) / band;
				var intensity = info.Max * MathF.Exp(-d * d * 3f);
				if (intensity < 0.01f)
					continue;

				var tl = toScreen(new float2(x0, rect.Top));
				var br = toScreen(new float2(x0 + stripWidth * layer.Strips[i].Bounds.Width / ShineStrip, rect.Bottom));
				Game.Renderer.RgbaSpriteRenderer.DrawSprite(layer.Strips[i],
					new float3(tl.X, tl.Y, 0), new float3(br.X, tl.Y, 0), new float3(br.X, br.Y, 0), new float3(tl.X, br.Y, 0),
					new float3(intensity, intensity, intensity), intensity);
			}
		}

		void DrawDot(float2 center, float diameter, float3 color)
		{
			if (diameter <= 0.5f || color.X + color.Y + color.Z <= 0.003f)
				return;

			var h = diameter / 2;
			var tl = center - new float2(h, h);
			Game.Renderer.RgbaSpriteRenderer.DrawSprite(dot,
				new float3(tl.X, tl.Y, 0), new float3(tl.X + diameter, tl.Y, 0),
				new float3(tl.X + diameter, tl.Y + diameter, 0), new float3(tl.X, tl.Y + diameter, 0),
				color, 1f);
		}

		static float Animate(PxMenuFxEffect effect, float t, float seed)
		{
			switch (effect)
			{
				case PxMenuFxEffect.Flicker:
					// Layered noise: slow swells plus fast licks of flame
					return 0.55f * Noise(t * 2.5f + seed) + 0.3f * Noise(t * 6.3f + seed * 1.7f) + 0.15f * Noise(t * 15f + seed * 2.3f);
				case PxMenuFxEffect.Twinkle:
					var n = Noise(t * 2f + seed);
					return n * n * n * n;
				default:
					return 0.5f + 0.5f * MathF.Sin((t + seed) * MathF.PI * 2);
			}
		}

		/// <summary>Smooth 1D value noise in [0, 1].</summary>
		static float Noise(float x)
		{
			var i = MathF.Floor(x);
			var f = x - i;
			var u = f * f * (3 - 2 * f);
			return Lerp(Hash((int)i), Hash((int)i + 1), u);
		}

		static float Hash(int n)
		{
			var h = (uint)n * 374761393u;
			h = (h ^ (h >> 13)) * 1274126177u;
			return (h ^ (h >> 16)) / (float)uint.MaxValue;
		}

		static float Lerp(float a, float b, float t) => a + (b - a) * t;
		static float Frac(float x) => x - MathF.Floor(x);

		static float Smoothstep(float e0, float e1, float x)
		{
			var t = Math.Clamp((x - e0) / (e1 - e0), 0f, 1f);
			return t * t * (3 - 2 * t);
		}

		public override void Removed()
		{
			base.Removed();
			foreach (var layer in layers)
				layer.Sheet.Dispose();

			layers.Clear();
			dotSheet?.Dispose();
			dotSheet = null;
			embers = null;
		}
	}
}
