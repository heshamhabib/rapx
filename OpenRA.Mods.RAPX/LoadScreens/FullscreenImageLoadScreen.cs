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
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.LoadScreens;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Mods.RAPX.Widgets;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.LoadScreens
{
	/// <summary>
	/// Full-window art with an animated progress bar. The first launch shows Background; every later map
	/// load (starting a skirmish, leaving one) shows a random image from LoadingImages.
	/// Loading is synchronous, so progress is estimated from how many times the engine pinged the load
	/// screen compared to the last load of the same kind (remembered in the support dir).
	/// BackgroundFx (optional) is a PxMenuFx manifest of animated light drawn over Background.
	/// </summary>
	public sealed class FullscreenImageLoadScreen : BlankLoadScreen
	{
		[FluentReference]
		const string Loading = "loadscreen-loading";

		[FluentReference]
		const string TitleBoot = "loadscreen-title-boot";

		[FluentReference]
		const string TitleGame = "loadscreen-title-game";

		[FluentReference]
		const string TitleExit = "loadscreen-title-exit";

		[FluentReference]
		const string Disclaimer = "loadscreen-disclaimer";

		const double FrameInterval = 1 / 15.0;
		const double MessageInterval = 2.4;
		const string StatsFile = "rapx-loadscreen.txt";

		/// <summary>World type of the most recently created world, set by <see cref="Traits.LoadScreenTracker"/>.</summary>
		public static WorldType? LastWorldType;

		static FullscreenImageLoadScreen current;

		Dictionary<string, string> info;
		string[] images = Array.Empty<string>();
		string[] messages = Array.Empty<string>();
		readonly Dictionary<string, double> expected = new();

		Sprite sprite;
		Sheet sheet;
		PxMenuFxWidget fx;
		float dpiScale;
		string imagePath;
		int lastImage = -1;

		bool active;
		string kind;
		string title = "";
		int pings;
		readonly Stopwatch clock = new();
		double lastRender = double.MinValue;
		double lastMessage = double.MinValue;
		string message = "";
		float shown;

		// Developer tool: when RAPX_LOADSHOTS is set, save frames of each load to the screenshots directory
		readonly bool devShots = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_LOADSHOTS"));
		static int devShotCount;
		float nextDevShot;

		public override void Init(ModData modData, Dictionary<string, string> info)
		{
			base.Init(modData, info);
			this.info = info;
			current = this;

			if (info.TryGetValue("LoadingImages", out var list))
				images = list.Split(',').Select(x => x.Trim()).Where(x => x.Length > 0).ToArray();

			messages = FluentProvider.GetMessage(Loading).Split(',').Select(x => x.Trim()).ToArray();
			ReadStats();

			Game.BeforeGameStart += OnBeforeGameStart;
			Game.AfterGameStart += OnAfterGameStart;

			// The mod itself is loading right now: covers everything up to the first shellmap
			Begin("boot", info.GetValueOrDefault("Background"));
		}

		void OnBeforeGameStart()
		{
			// Mod boot and the first shellmap load are one continuous load
			if (active && kind == "boot")
				return;

			var isExit = LastWorldType == WorldType.Regular;
			Begin(isExit ? "exit" : "game", PickImage() ?? info.GetValueOrDefault("Background"));
		}

		void OnAfterGameStart() => Finish();

		/// <summary>Called once the new world has finished loading.</summary>
		public static void WorldLoaded() => current?.Finish();

		string PickImage()
		{
			if (images.Length == 0)
				return null;

			var i = Game.CosmeticRandom.Next(images.Length);
			if (images.Length > 1 && i == lastImage)
				i = (i + 1 + Game.CosmeticRandom.Next(images.Length - 1)) % images.Length;

			lastImage = i;
			return images[i];
		}

		void Begin(string kind, string image)
		{
			active = true;
			this.kind = kind;
			pings = 0;
			shown = 0;
			lastRender = double.MinValue;
			lastMessage = double.MinValue;
			nextDevShot = 0.3f;
			clock.Restart();

			if (image != imagePath)
			{
				ReleaseImage();
				imagePath = image;
			}

			var key = kind == "boot" ? TitleBoot : kind == "exit" ? TitleExit : TitleGame;
			title = FluentProvider.GetMessage(key);
		}

		void Finish()
		{
			if (!active)
				return;

			// Remember how long this kind of load took, smoothing between maps of different sizes
			Log.Write("debug", $"Load screen: {kind} load took {clock.Elapsed.TotalSeconds:F1}s, {pings} pings");
			expected[kind] = expected.TryGetValue(kind, out var old) ? 0.5 * old + 0.5 * pings : pings;
			WriteStats();

			// Show the bar full for the frame before the game takes over
			shown = 1;
			Render(clock.Elapsed.TotalSeconds);

			active = false;
			ReleaseImage();
			imagePath = null;
		}

		public override void Display()
		{
			if (!active || Game.Renderer == null)
				return;

			pings++;

			var now = clock.Elapsed.TotalSeconds;
			if (now - lastRender < FrameInterval)
				return;

			var dt = lastRender == double.MinValue ? 0 : now - lastRender;
			shown = Math.Max(shown, shown + (float)((Target(now) - shown) * Math.Min(1, dt * 5)));
			Render(now);
		}

		/// <summary>Estimated fraction of the load that is done.</summary>
		float Target(double now)
		{
			// Never seen this kind of load: ease in over time instead
			if (!expected.TryGetValue(kind, out var total) || total < 1)
				return (float)(0.95 * (1 - Math.Exp(-now / 5)));

			return (float)Math.Min(0.985, pings / total);
		}

		void Render(double now)
		{
			var r = Game.Renderer;
			if (dpiScale != r.WindowScale)
			{
				dpiScale = r.WindowScale;
				ReleaseImage();
			}

			if (sprite == null && imagePath != null)
				sprite = FullscreenImageWidget.LoadImage(ModData, imagePath, out sheet);

			r.BeginUI();
			var size = new float2(r.Resolution.Width, r.Resolution.Height);

			if (sprite != null)
			{
				// Slow push-in on the art
				var zoom = 1 + 0.06f * (float)(1 - Math.Exp(-now / 10));
				var (pos, drawSize) = FullscreenImageWidget.CoverRect(sprite.Size.XY, new Rectangle(0, 0, (int)size.X, (int)size.Y));
				var anchor = new float2(size.X / 2, size.Y * 0.42f);
				var origin = anchor + zoom * (pos - anchor);
				WidgetUtils.DrawSprite(sprite, origin, zoom * drawSize);

				// Glowing logo, flickering fires and embers on the boot art
				if (imagePath == info.GetValueOrDefault("Background") && info.TryGetValue("BackgroundFx", out var manifest))
				{
					fx ??= new PxMenuFxWidget(ModData) { Manifest = manifest, Embers = 120 };
					fx.DrawOver(origin, zoom * drawSize);
				}
			}

			DrawHud(r, size, now);
			r.EndFrame(new NullInputHandler());
			lastRender = now;

			if (devShots && shown >= nextDevShot)
			{
				nextDevShot = shown >= 1 ? float.MaxValue : nextDevShot + 0.35f;
				var dir = Path.Combine(Platform.SupportDir, "Screenshots", ModData.Manifest.Id, "loadscreen");
				Directory.CreateDirectory(dir);
				r.SaveScreenshot(Path.Combine(dir, $"{++devShotCount:D2}-{kind}-{(int)(shown * 100)}.png"));
			}
		}

		void DrawHud(Renderer r, float2 size, double now)
		{
			var cr = r.RgbaColorRenderer;
			var w = size.X;
			var h = size.Y;
			var t = (float)now;

			// Shade the bottom of the art so the HUD reads, and a light vignette on top
			Gradient(cr, 0, 0, w, h * 0.12f, Color.FromArgb(130, 0, 0, 0), Color.FromArgb(0, 0, 0, 0));

			var barW = (float)Math.Round(Math.Min(w * 0.62f, 1100));
			const float BarH = 12;
			var x0 = (float)Math.Round((w - barW) / 2);
			var y0 = (float)Math.Round(h - 96);
			var x1 = x0 + barW;
			var y1 = y0 + BarH;
			var p = Math.Clamp(shown, 0, 1);
			var fx = x0 + barW * p;
			var pulse = 0.5f + 0.5f * (float)Math.Sin(t * 4.2);

			var red = Color.FromArgb(255, 226, 38, 28);
			var dim = Color.FromArgb(70, 255, 255, 255);

			// HUD band: fade the art into a dark strip behind the bar, edged with a red hairline that fades out sideways
			var bandTop = y0 - 70;
			Gradient(cr, 0, bandTop - h * 0.22f, w, bandTop, Color.FromArgb(0, 0, 0, 0), Color.FromArgb(150, 2, 2, 4));
			Gradient(cr, 0, bandTop, w, h, Color.FromArgb(150, 2, 2, 4), Color.FromArgb(235, 2, 2, 4));
			var clear = Color.FromArgb(0, 226, 38, 28);
			var line = Color.FromArgb(150, 226, 38, 28);
			var mid = w / 2;
			HGradient(cr, 0, mid, bandTop, bandTop + 1, clear, line);
			HGradient(cr, mid, w, bandTop, bandTop + 1, line, clear);

			// Track
			cr.FillRect(new float3(x0 - 3, y0 - 3, 0), new float3(x1 + 3, y1 + 3, 0), Color.FromArgb(190, 0, 0, 0));
			cr.DrawRect(new float3(x0 - 3, y0 - 3, 0), new float3(x1 + 3, y1 + 3, 0), 1, Color.FromArgb(55, 255, 255, 255));

			// Empty gauge segments
			for (var sx = x0; sx < x1 - 6; sx += 9)
				cr.FillRect(new float3(sx, y0 + 3, 0), new float3(sx + 7, y1 - 3, 0), Color.FromArgb(22, 255, 255, 255));

			// Quarter markers below the track
			for (var i = 1; i < 4; i++)
			{
				var mx = (float)Math.Round(x0 + barW * i / 4);
				var c = p >= i / 4f ? Color.FromArgb(200, 255, 90, 60) : dim;
				cr.FillRect(new float3(mx, y1 + 6, 0), new float3(mx + 1, y1 + 11, 0), c);
			}

			// Corner brackets
			Bracket(cr, x0 - 8, y0 - 8, 1, 1, red);
			Bracket(cr, x1 + 8, y0 - 8, -1, 1, red);
			Bracket(cr, x0 - 8, y1 + 8, 1, -1, red);
			Bracket(cr, x1 + 8, y1 + 8, -1, -1, red);

			if (fx > x0 + 1)
			{
				// Fill: deep red into hot orange towards the leading edge
				var tl = new float3(x0, y0, 0);
				var tr = new float3(fx, y0, 0);
				var br = new float3(fx, y1, 0);
				var bl = new float3(x0, y1, 0);
				var cold = Color.FromArgb(255, 105, 8, 10);
				var hot = Color.FromArgb(255, 255, 84, 32);
				cr.FillRect(tl, tr, br, bl, cold, hot, hot, cold);

				// Glassy highlight on the upper half
				cr.FillRect(new float3(x0, y0, 0), new float3(fx, y0 + BarH * 0.45f, 0), Color.FromArgb(46, 255, 230, 200), BlendMode.Additive);
				cr.FillRect(new float3(x0, y0, 0), new float3(fx, y0 + 1, 0), Color.FromArgb(90, 255, 220, 190), BlendMode.Additive);

				// Segment cuts
				for (var sx = x0 + 9; sx < fx - 2; sx += 9)
					cr.FillRect(new float3(sx, y0, 0), new float3(sx + 2, y1, 0), Color.FromArgb(120, 20, 0, 0));

				// Light sweep travelling along the filled part
				const float SweepW = 140f;
				var span = fx - x0 + SweepW;
				var sweepX = x0 - SweepW + (float)(now * 520 % Math.Max(span, 1));
				SweepBand(cr, sweepX, SweepW, x0, fx, y0, y1);

				// Leading edge: hot core plus a soft bloom
				for (var i = 4; i >= 1; i--)
				{
					var g = 6 * i;
					var a = (int)((16 + 14 * pulse) * (5 - i) / 4f);
					cr.FillRect(new float3(fx - g, y0 - i * 3, 0), new float3(fx + g * 0.6f, y1 + i * 3, 0), Color.FromArgb(a, 255, 110, 50), BlendMode.Additive);
				}

				// Horizontal flare streaking from the edge
				var flare = Color.FromArgb((int)(60 + 40 * pulse), 255, 140, 80);
				var none = Color.FromArgb(0, 255, 140, 80);
				var cy = (y0 + y1) / 2;
				cr.FillRect(new float3(fx - 90, cy - 1, 0), new float3(fx, cy - 1, 0), new float3(fx, cy + 1, 0), new float3(fx - 90, cy + 1, 0),
					none, flare, flare, none, BlendMode.Additive);
				cr.FillRect(new float3(fx, cy - 1, 0), new float3(fx + 40, cy - 1, 0), new float3(fx + 40, cy + 1, 0), new float3(fx, cy + 1, 0),
					flare, none, none, flare, BlendMode.Additive);
				cr.FillRect(new float3(fx - 2, y0 - 4, 0), new float3(fx + 1, y1 + 4, 0), Color.FromArgb(255, 255, 236, 210));
			}

			if (r.Fonts == null)
				return;

			var titleFont = Font(r, "PXTitle", "BigBold");
			var bodyFont = Font(r, "PXBody", "Regular");
			var smallFont = Font(r, "PXHeader", "TinyBold");
			var shadow = Color.FromArgb(200, 0, 0, 0);

			// Title, top-left of the bar, with a pulsing status light
			var titleSize = titleFont.Measure(title);
			var ty = y0 - 14 - titleSize.Y;
			var dot = Color.FromArgb((int)(120 + 135 * pulse), 255, 40, 30);
			cr.FillEllipse(new float3(x0, ty + titleSize.Y / 2 - 5, 0), new float3(x0 + 10, ty + titleSize.Y / 2 + 5, 0), dot);
			cr.FillEllipse(new float3(x0 - 6, ty + titleSize.Y / 2 - 11, 0), new float3(x0 + 16, ty + titleSize.Y / 2 + 11, 0),
				Color.FromArgb((int)(50 * pulse), 255, 60, 40), BlendMode.Additive);
			titleFont.DrawTextWithShadow(title, new float2(x0 + 20, ty), Color.White, shadow, 2);

			// Percentage, top-right
			var percent = ((int)Math.Floor(p * 100)).ToString(CultureInfo.InvariantCulture) + "%";
			var percentSize = titleFont.Measure(percent);
			titleFont.DrawTextWithShadow(percent, new float2(x1 - percentSize.X, ty), Color.FromArgb(255, 255, 96, 60), shadow, 2);

			// Rotating flavour line under the bar
			if (messages.Length > 0 && now - lastMessage >= MessageInterval)
			{
				var next = messages.Random(Game.CosmeticRandom);
				if (messages.Length > 1)
					while (next == message)
						next = messages.Random(Game.CosmeticRandom);

				message = next;
				lastMessage = now;
			}

			bodyFont.DrawTextWithShadow(message, new float2(x0, y1 + 18), Color.FromArgb(255, 200, 200, 205), shadow, 1);

			var tag = "RAPX // " + TimeSpan.FromSeconds(now).ToString(@"mm\:ss", CultureInfo.InvariantCulture);
			var tagSize = smallFont.Measure(tag);
			smallFont.DrawTextWithShadow(tag, new float2(x1 - tagSize.X, y1 + 20), Color.FromArgb(160, 255, 255, 255), shadow, 1);

			// Trademark notice, centred along the bottom of the boot screen
			if (kind == "boot")
			{
				var noteFont = Font(r, "PXSmall", "Small");
				var note = FluentProvider.GetMessage(Disclaimer);
				var noteSize = noteFont.Measure(note);
				noteFont.DrawTextWithShadow(note, new float2((float)Math.Round((w - noteSize.X) / 2), h - 22 - noteSize.Y),
					Color.FromArgb(140, 255, 255, 255), shadow, 1);
			}
		}

		static SpriteFont Font(Renderer r, string name, string fallback)
		{
			return r.Fonts.TryGetValue(name, out var font) ? font : r.Fonts[fallback];
		}

		static void Gradient(RgbaColorRenderer cr, float x0, float y0, float x1, float y1, Color top, Color bottom)
		{
			cr.FillRect(new float3(x0, y0, 0), new float3(x1, y0, 0), new float3(x1, y1, 0), new float3(x0, y1, 0), top, top, bottom, bottom);
		}

		static void HGradient(RgbaColorRenderer cr, float x0, float x1, float y0, float y1, Color left, Color right)
		{
			cr.FillRect(new float3(x0, y0, 0), new float3(x1, y0, 0), new float3(x1, y1, 0), new float3(x0, y1, 0), left, right, right, left);
		}

		static void Bracket(RgbaColorRenderer cr, float x, float y, int dx, int dy, Color c)
		{
			const float L = 12;
			const float T = 2;
			cr.FillRect(new float3(Math.Min(x, x + dx * L), Math.Min(y, y + dy * T), 0), new float3(Math.Max(x, x + dx * L), Math.Max(y, y + dy * T), 0), c);
			cr.FillRect(new float3(Math.Min(x, x + dx * T), Math.Min(y, y + dy * L), 0), new float3(Math.Max(x, x + dx * T), Math.Max(y, y + dy * L), 0), c);
		}

		static void SweepBand(RgbaColorRenderer cr, float x, float width, float clipL, float clipR, float y0, float y1)
		{
			// Two halves: fade in to the band's centre, then fade out, clipped to the filled part
			var mid = x + width / 2;
			var clear = Color.FromArgb(0, 0, 0, 0);
			var bright = Color.FromArgb(110, 255, 200, 150);
			SweepHalf(cr, x, mid, clipL, clipR, y0, y1, clear, bright);
			SweepHalf(cr, mid, x + width, clipL, clipR, y0, y1, bright, clear);
		}

		static void SweepHalf(RgbaColorRenderer cr, float a, float b, float clipL, float clipR, float y0, float y1, Color ca, Color cb)
		{
			var l = Math.Max(a, clipL);
			var r = Math.Min(b, clipR);
			if (r <= l)
				return;

			var left = Lerp(ca, cb, (l - a) / (b - a));
			var right = Lerp(ca, cb, (r - a) / (b - a));
			cr.FillRect(new float3(l, y0, 0), new float3(r, y0, 0), new float3(r, y1, 0), new float3(l, y1, 0), left, right, right, left, BlendMode.Additive);
		}

		static Color Lerp(Color a, Color b, float t)
		{
			return Color.FromArgb(
				(int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
		}

		void ReadStats()
		{
			try
			{
				var path = Path.Combine(Platform.SupportDir, StatsFile);
				if (!File.Exists(path))
					return;

				foreach (var line in File.ReadAllLines(path))
				{
					var parts = line.Split('=');
					if (parts.Length == 2 && double.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var v))
						expected[parts[0].Trim()] = v;
				}
			}
			catch (Exception e)
			{
				Log.Write("debug", $"Could not read load screen stats: {e.Message}");
			}
		}

		void WriteStats()
		{
			try
			{
				var lines = expected.Select(kv => kv.Key + "=" + kv.Value.ToString(CultureInfo.InvariantCulture));
				File.WriteAllLines(Path.Combine(Platform.SupportDir, StatsFile), lines);
			}
			catch (Exception e)
			{
				Log.Write("debug", $"Could not write load screen stats: {e.Message}");
			}
		}

		void ReleaseImage()
		{
			fx?.Removed();
			fx = null;
			sheet?.Dispose();
			sheet = null;
			sprite = null;
		}

		protected override void Dispose(bool disposing)
		{
			if (disposing)
			{
				Game.BeforeGameStart -= OnBeforeGameStart;
				Game.AfterGameStart -= OnAfterGameStart;
				if (current == this)
					current = null;

				ReleaseImage();
			}

			base.Dispose(disposing);
		}
	}
}
