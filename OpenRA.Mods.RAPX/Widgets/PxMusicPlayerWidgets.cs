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
using System.IO;
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Track covers for the music player. A track "ra|audio/sector4.mp3" uses ra|music-covers/sector4.png and,
	/// for the blurred backdrop, sector4-blur.png (both made by artsrc/music-covers/make_covers.sh).
	/// Loaded on first use and kept for the session; a track without a cover gets a drawn placeholder.
	/// </summary>
	public static class PxMusicCovers
	{
		const string CoverPath = "ra|music-covers/{0}.png";
		const string BlurPath = "ra|music-covers/{0}-blur.png";
		const string CardPath = "ra|music-covers/{0}-card.png";

		static readonly Dictionary<string, Sprite> Cache = new();
		static readonly List<Sheet> Sheets = new();
		static ModData cacheModData;

		public static string Key(MusicInfo song)
		{
			var file = song.Filename;
			var bar = file.LastIndexOf('|');
			return Path.GetFileNameWithoutExtension(bar >= 0 ? file[(bar + 1)..] : file);
		}

		public static Sprite Get(MusicInfo song, bool blur) => Load(song, blur ? BlurPath : CoverPath);

		/// <summary>Wide crop for the track cards (leaves out the title printed on the cover), else the cover.</summary>
		public static Sprite GetCard(MusicInfo song) => Load(song, CardPath) ?? Get(song, false);

		static Sprite Load(MusicInfo song, string format)
		{
			if (song == null)
				return null;

			var modData = Game.ModData;
			if (cacheModData != modData)
			{
				foreach (var s in Sheets)
					s.Dispose();

				Sheets.Clear();
				Cache.Clear();
				cacheModData = modData;
			}

			var path = string.Format(System.Globalization.CultureInfo.InvariantCulture, format, Key(song));
			if (Cache.TryGetValue(path, out var sprite))
				return sprite;

			sprite = null;
			if (modData.DefaultFileSystem.Exists(path))
			{
				sprite = FullscreenImageWidget.LoadImage(modData, path, out var sheet);
				Sheets.Add(sheet);
			}

			Cache[path] = sprite;
			return sprite;
		}

		/// <summary>Draw a cover cropped to fill bounds. zoom &gt; 1 pushes in; brightness tints it darker.</summary>
		public static void Draw(Sprite sprite, Rectangle bounds, float zoom = 1f, float brightness = 1f, float alpha = 1f, float panX = 0.5f,
			float2 offset = default)
		{
			if (sprite == null || alpha <= 0)
				return;

			var (pos, size) = FullscreenImageWidget.CoverRect(sprite.Size.XY, bounds, panX);
			var center = pos + 0.5f * size + offset;
			size *= zoom;
			pos = center - 0.5f * size;

			Game.Renderer.EnableScissor(bounds);
			var tint = new float3(brightness, brightness, brightness);
			Game.Renderer.RgbaSpriteRenderer.DrawSprite(sprite,
				new float3(pos.X, pos.Y, 0), new float3(pos.X + size.X, pos.Y, 0),
				new float3(pos.X + size.X, pos.Y + size.Y, 0), new float3(pos.X, pos.Y + size.Y, 0), tint, alpha);
			Game.Renderer.DisableScissor();
		}

		/// <summary>Stand-in art for a track without a cover: a dark red gradient with the track's initials.</summary>
		public static void DrawPlaceholder(MusicInfo song, Rectangle bounds, float alpha = 1f)
		{
			var a = (int)(255 * alpha);
			WidgetUtils.FillRectWithColor(bounds, Color.FromArgb(a, 70, 14, 12), Color.FromArgb(a, 24, 10, 10),
				Color.FromArgb(a, 8, 8, 10), Color.FromArgb(a, 30, 12, 12));

			if (song == null)
				return;

			var initials = "";
			foreach (var word in song.Title.Split(' ', StringSplitOptions.RemoveEmptyEntries))
				if (initials.Length < 2 && char.IsLetter(word[0]))
					initials += char.ToUpperInvariant(word[0]);

			var font = Game.Renderer.Fonts["PXDisplayLarge"];
			var size = font.Measure(initials);
			font.DrawText(initials, new float2(bounds.X + (bounds.Width - size.X) / 2, bounds.Y + (bounds.Height - size.Y) / 2),
				Color.FromArgb(a / 2, 255, 106, 85));
		}

		/// <summary>Cover, or the placeholder when the track has none.</summary>
		public static void DrawCover(MusicInfo song, Rectangle bounds, float zoom = 1f, float brightness = 1f, float alpha = 1f, bool card = false)
		{
			var sprite = card ? GetCard(song) : Get(song, false);
			if (sprite != null)
				Draw(sprite, bounds, zoom, brightness, alpha);
			else
				DrawPlaceholder(song, bounds, alpha);
		}

		/// <summary>
		/// The cover of the track that is playing, brought to life: a slow drifting push-in, a brightness kick on
		/// the beat, a light sweep, a scan line and embers rising off the art. energy (0..1) fades the effects out
		/// when the music pauses; the drift keeps going, slower.
		/// </summary>
		public static void DrawLive(MusicInfo song, Rectangle bounds, float energy, float alpha = 1f, float brightness = 1f, int embers = 18,
			bool card = false)
		{
			var sprite = card ? GetCard(song) : Get(song, false);
			if (sprite == null)
			{
				DrawPlaceholder(song, bounds, alpha);
				return;
			}

			if (alpha <= 0)
				return;

			var t = Game.RunTime / 1000.0;
			var beat = energy * (float)Math.Pow(PxWarChrome.Pulse(1000), 8);
			var zoom = 1.1f + 0.03f * (float)Math.Sin(t / 6.5) + 0.02f * beat;
			var drift = new float2(0.025f * bounds.Width * (float)Math.Sin(t / 9.0), 0.025f * bounds.Height * (float)Math.Cos(t / 11.0));
			Draw(sprite, bounds, zoom, brightness * (1 + 0.1f * beat), alpha, 0.5f, drift);

			var fx = energy * alpha;
			if (fx <= 0.01f)
				return;

			Game.Renderer.EnableScissor(bounds);
			var cr = Game.Renderer.RgbaColorRenderer;

			// Light sweep: a skewed bright band crosses the art in 1.5s, every 6s
			var sweep = (float)(t % 6.0 / 1.5);
			if (sweep < 1)
			{
				var cx = bounds.X + (sweep * 1.6f - 0.3f) * bounds.Width;
				var hw = 0.09f * bounds.Width;
				var skew = 0.3f * bounds.Height;
				float3 P(float x, float y) => new(x, y, 0);
				var clear = Color.FromArgb(0, 255, 240, 220);
				var glow = Color.FromArgb((int)(55 * fx), 255, 240, 220);
				cr.FillRect(P(cx - hw + skew, bounds.Y), P(cx + skew, bounds.Y), P(cx - skew, bounds.Bottom), P(cx - hw - skew, bounds.Bottom),
					clear, glow, glow, clear);
				cr.FillRect(P(cx + skew, bounds.Y), P(cx + hw + skew, bounds.Y), P(cx + hw - skew, bounds.Bottom), P(cx - skew, bounds.Bottom),
					glow, clear, clear, glow);
			}

			// Scan line drifting down
			var scanY = bounds.Y + (int)(t * 28 % bounds.Height);
			WidgetUtils.FillRectWithColor(new Rectangle(bounds.X, scanY - 6, bounds.Width, 6),
				Color.FromArgb(0, 255, 106, 85), Color.FromArgb(0, 255, 106, 85), Color.FromArgb((int)(22 * fx), 255, 106, 85), Color.FromArgb((int)(22 * fx), 255, 106, 85));
			WidgetUtils.FillRectWithColor(new Rectangle(bounds.X, scanY, bounds.Width, 1), Color.FromArgb((int)(60 * fx), 255, 140, 120));

			// Embers rising off the art; positions come from the clock, so there is no state to keep
			for (var i = 0; i < embers; i++)
			{
				var period = 2.5 + 3 * Hash(i, 1);
				var phase = (float)((t / period + Hash(i, 2)) % 1.0);
				var x = bounds.X + (int)(Hash(i, 3) * bounds.Width + 8 * Math.Sin(t * 1.3 + i));
				var y = bounds.Bottom - (int)(phase * bounds.Height * 0.9f);
				var size = Hash(i, 4) > 0.7f ? 3 : 2;
				var a = (int)(210 * fx * Math.Sin(Math.PI * phase));
				WidgetUtils.FillRectWithColor(new Rectangle(x, y, size, size), Color.FromArgb(a, 255, 120 + (int)(90 * Hash(i, 5)), 50));
			}

			Game.Renderer.DisableScissor();
		}

		static float Hash(int i, int k)
		{
			var v = Math.Sin(i * 12.9898 + k * 78.233) * 43758.5453;
			return (float)(v - Math.Floor(v));
		}

		/// <summary>
		/// Animated level-meter bars. There is no audio analysis in the engine, so the levels are layered sine
		/// waves with a beat pulse; level (0..1) scales them so they fall flat when the music pauses.
		/// </summary>
		public static void DrawEqualizer(Rectangle r, int bars, float level, Color low, Color high, int gap = 2)
		{
			var w = Math.Max(1, (r.Width - (bars - 1) * gap) / bars);
			var t = Game.RunTime / 1000f;
			var beat = (float)Math.Pow(Math.Max(0, Math.Sin(t * Math.PI * 2 * 2.05)), 6);
			for (var i = 0; i < bars; i++)
			{
				var shape = 0.35f + 0.65f * (float)Math.Sin(Math.PI * (i + 0.5f) / bars);
				var wave = 0.5f + 0.25f * (float)Math.Sin(t * (3.1f + i * 0.37f) + i * 1.7f)
					+ 0.15f * (float)Math.Sin(t * (7.3f + i * 0.91f) + i * 0.6f) + 0.25f * beat * shape;
				var v = Math.Clamp(0.06f + level * shape * wave, 0.04f, 1f);
				var h = Math.Max(2, (int)(r.Height * v));
				var bar = new Rectangle(r.X + i * (w + gap), r.Bottom - h, w, h);
				var top = PxWarChrome.Lerp(low, high, v);
				WidgetUtils.FillRectWithColor(bar, top, top, low, low);
			}
		}

		public static string Clock(float seconds)
		{
			var s = Math.Max(0, (int)seconds);
			return $"{s / 60}:{s % 60:D2}";
		}
	}

	public enum PxMusicGlyph { Play, Pause, Stop, Next, Prev, Shuffle, Loop, Speaker }

	/// <summary>Music transport button drawn as a vector glyph; Primary draws the big round red play button.</summary>
	public class PxMusicButtonWidget : ButtonWidget
	{
		public PxMusicGlyph Glyph = PxMusicGlyph.Play;
		public Func<PxMusicGlyph> GetGlyph;
		public bool Primary = false;

		[ObjectCreator.UseCtor]
		public PxMusicButtonWidget(ModData modData)
			: base(modData)
		{
			GetGlyph = () => Glyph;
		}

		protected PxMusicButtonWidget(PxMusicButtonWidget other)
			: base(other)
		{
			Glyph = other.Glyph;
			GetGlyph = other.GetGlyph;
			Primary = other.Primary;
		}

		public override Widget Clone() { return new PxMusicButtonWidget(this); }

		public override void Draw()
		{
			var rb = RenderBounds;
			var disabled = IsDisabled();
			var hover = Ui.MouseOverWidget == this && !disabled;
			var on = IsHighlighted();
			var press = Depressed && !disabled ? 1 : 0;
			var c = new float2(rb.X + rb.Width / 2f + press, rb.Y + rb.Height / 2f + press);

			Color glyph;
			if (Primary)
			{
				var face = disabled ? Color.FromArgb(70, 30, 30) : hover ? PxDraw.AccentBright : PxDraw.Accent;
				if (!disabled)
				{
					var glow = 30 + (int)(40 * (hover ? 1 : PxWarChrome.Pulse(2400)));
					WidgetUtils.FillEllipseWithColor(rb.InflateBy(5, 5, 5, 5), Color.FromArgb(glow, PxDraw.Accent));
				}

				WidgetUtils.FillEllipseWithColor(rb, Color.FromArgb(255, 12, 12, 14));
				WidgetUtils.FillEllipseWithColor(rb.InflateBy(-2, -2, -2, -2), face);
				glyph = disabled ? Color.FromArgb(140, 255, 255, 255) : Color.White;
			}
			else
			{
				if (hover)
					WidgetUtils.FillEllipseWithColor(rb, Color.FromArgb(34, 255, 255, 255));

				glyph = disabled ? Color.FromArgb(70, 72, 80) : on ? PxDraw.AccentBright : hover ? Color.White : Color.FromArgb(200, 202, 210);
				if (on && !disabled)
					WidgetUtils.FillEllipseWithColor(new Rectangle((int)c.X - 2, rb.Bottom - 5, 4, 4), PxDraw.AccentBright);
			}

			DrawGlyph(GetGlyph(), c, Math.Min(rb.Width, rb.Height) * (Primary ? 0.36f : 0.42f), glyph);
		}

		static void Tri(float2 a, float2 b, float2 c, Color color)
		{
			var c3 = new float3(c, 0);
			Game.Renderer.RgbaColorRenderer.FillRect(new float3(a, 0), new float3(b, 0), c3, c3, color);
		}

		static void Box(float x1, float y1, float x2, float y2, Color color)
		{
			Game.Renderer.RgbaColorRenderer.FillRect(new float3(x1, y1, 0), new float3(x2, y2, 0), color);
		}

		static void Line(float2 a, float2 b, float width, Color color)
		{
			Game.Renderer.RgbaColorRenderer.DrawLine(new float3(a, 0), new float3(b, 0), width, color);
		}

		/// <summary>Draw a glyph centred on c, s = half its size.</summary>
		public static void DrawGlyph(PxMusicGlyph g, float2 c, float s, Color color)
		{
			var x = c.X;
			var y = c.Y;
			switch (g)
			{
				case PxMusicGlyph.Play:
					Tri(new float2(x - 0.55f * s, y - 0.8f * s), new float2(x + 0.85f * s, y), new float2(x - 0.55f * s, y + 0.8f * s), color);
					break;
				case PxMusicGlyph.Pause:
					Box(x - 0.6f * s, y - 0.75f * s, x - 0.15f * s, y + 0.75f * s, color);
					Box(x + 0.15f * s, y - 0.75f * s, x + 0.6f * s, y + 0.75f * s, color);
					break;
				case PxMusicGlyph.Stop:
					Box(x - 0.6f * s, y - 0.6f * s, x + 0.6f * s, y + 0.6f * s, color);
					break;
				case PxMusicGlyph.Next:
					Tri(new float2(x - 0.75f * s, y - 0.7f * s), new float2(x + 0.45f * s, y), new float2(x - 0.75f * s, y + 0.7f * s), color);
					Box(x + 0.45f * s, y - 0.7f * s, x + 0.72f * s, y + 0.7f * s, color);
					break;
				case PxMusicGlyph.Prev:
					Tri(new float2(x + 0.75f * s, y - 0.7f * s), new float2(x + 0.75f * s, y + 0.7f * s), new float2(x - 0.45f * s, y), color);
					Box(x - 0.72f * s, y - 0.7f * s, x - 0.45f * s, y + 0.7f * s, color);
					break;
				case PxMusicGlyph.Shuffle:
				{
					var l = x - 0.75f * s;
					var r = x + 0.45f * s;
					var t = y - 0.5f * s;
					var b = y + 0.5f * s;
					Line(new float2(l, b), new float2(r, t), 2, color);
					Line(new float2(l, t), new float2(r, b), 2, color);
					Tri(new float2(r - 0.05f * s, t - 0.35f * s), new float2(x + 0.85f * s, t), new float2(r - 0.05f * s, t + 0.35f * s), color);
					Tri(new float2(r - 0.05f * s, b - 0.35f * s), new float2(x + 0.85f * s, b), new float2(r - 0.05f * s, b + 0.35f * s), color);
					break;
				}

				case PxMusicGlyph.Loop:
				{
					var l = x - 0.75f * s;
					var r = x + 0.75f * s;
					var t = y - 0.45f * s;
					var b = y + 0.45f * s;
					Line(new float2(l, t), new float2(r - 0.4f * s, t), 2, color);
					Line(new float2(r, t - 1), new float2(r, b), 2, color);
					Line(new float2(r, b), new float2(l + 0.4f * s, b), 2, color);
					Line(new float2(l, b + 1), new float2(l, t), 2, color);
					Tri(new float2(r - 0.45f * s, t - 0.35f * s), new float2(r - 0.05f * s, t), new float2(r - 0.45f * s, t + 0.35f * s), color);
					Tri(new float2(l + 0.45f * s, b - 0.35f * s), new float2(l + 0.45f * s, b + 0.35f * s), new float2(l + 0.05f * s, b), color);
					break;
				}

				case PxMusicGlyph.Speaker:
					Box(x - 0.8f * s, y - 0.3f * s, x - 0.4f * s, y + 0.3f * s, color);
					Game.Renderer.RgbaColorRenderer.FillRect(new float3(x - 0.4f * s, y - 0.3f * s, 0), new float3(x + 0.05f * s, y - 0.75f * s, 0),
						new float3(x + 0.05f * s, y + 0.75f * s, 0), new float3(x - 0.4f * s, y + 0.3f * s, 0), color);
					Line(new float2(x + 0.35f * s, y - 0.35f * s), new float2(x + 0.35f * s, y + 0.35f * s), 2, color);
					Line(new float2(x + 0.7f * s, y - 0.65f * s), new float2(x + 0.7f * s, y + 0.65f * s), 2, color);
					break;
			}
		}
	}

	/// <summary>Volume slider drawn as a thin track with a red fill and a round thumb.</summary>
	public class PxVolumeSliderWidget : ExponentialSliderWidget
	{
		public PxVolumeSliderWidget() { }

		protected PxVolumeSliderWidget(PxVolumeSliderWidget other)
			: base(other) { }

		public override Widget Clone() { return new PxVolumeSliderWidget(this); }

		public override void Draw()
		{
			UpdateValue(GetValue());

			var rb = RenderBounds;
			var hover = Ui.MouseOverWidget == this || isMoving;
			var thumbX = rb.X + PxFromValue(Value);
			var cy = rb.Y + rb.Height / 2;
			var track = new Rectangle(rb.X + rb.Height / 2, cy - 2, rb.Width - rb.Height, 4);

			WidgetUtils.FillRectWithColor(track, Color.FromArgb(255, 46, 47, 54));
			var fill = new Rectangle(track.X, track.Y, Math.Max(0, thumbX - track.X), track.Height);
			var dark = PxWarChrome.Darken(PxDraw.Accent, 0.35f);
			WidgetUtils.FillRectWithColor(fill, dark, PxDraw.AccentBright, PxDraw.AccentBright, dark);

			var r = hover ? 8 : 7;
			if (hover)
				WidgetUtils.FillEllipseWithColor(new Rectangle(thumbX - r - 4, cy - r - 4, 2 * r + 8, 2 * r + 8), Color.FromArgb(50, PxDraw.Accent));

			WidgetUtils.FillEllipseWithColor(new Rectangle(thumbX - r, cy - r, 2 * r, 2 * r), PxDraw.AccentBright);
			WidgetUtils.FillEllipseWithColor(new Rectangle(thumbX - r + 3, cy - r + 3, 2 * r - 6, 2 * r - 6), Color.White);
		}
	}

	/// <summary>
	/// "Now playing" header: blurred cover backdrop, the animated cover (PxMusicCovers.DrawLive), track title,
	/// level meter and progress bar. The transport buttons and volume slider are child widgets on top.
	/// Covers crossfade when the track changes. Click or drag the progress bar to jump within the track.
	/// </summary>
	public class PxMusicHeroWidget : Widget
	{
		public readonly int CoverX = 20;
		public readonly int CoverY = 20;
		public readonly int CoverWidth = 356;
		public readonly int CoverHeight = 200;
		public readonly int TextX = 404;

		public Func<MusicInfo> GetSong = () => null;
		public Func<string> GetStatus = () => "";
		public Func<string> GetSubtitle = () => "";
		public Func<bool> IsPlaying = () => false;
		public Func<float> GetSeek = () => 0;
		public Func<string> GetNote = () => "";
		public Func<bool> CanSeek = () => false;
		public Action<float> OnSeek = _ => { };

		const int FadeTime = 450;
		const int BarY = 118;
		const int BarHitPad = 9;

		bool dragging;
		float dragFraction;

		MusicInfo shown;
		MusicInfo previous;
		long changedAt;
		float level;

		public PxMusicHeroWidget() { }

		protected PxMusicHeroWidget(PxMusicHeroWidget other)
			: base(other)
		{
			CoverX = other.CoverX;
			CoverY = other.CoverY;
			CoverWidth = other.CoverWidth;
			CoverHeight = other.CoverHeight;
			TextX = other.TextX;
			GetSong = other.GetSong;
			GetStatus = other.GetStatus;
			GetSubtitle = other.GetSubtitle;
			IsPlaying = other.IsPlaying;
			GetSeek = other.GetSeek;
			GetNote = other.GetNote;
			CanSeek = other.CanSeek;
			OnSeek = other.OnSeek;
		}

		public override Widget Clone() { return new PxMusicHeroWidget(this); }

		Rectangle BarRect()
		{
			var rb = RenderBounds;
			return new Rectangle(rb.X + TextX, rb.Y + BarY, rb.Right - 24 - (rb.X + TextX), 4);
		}

		float FractionAt(int x)
		{
			var bar = BarRect();
			return Math.Clamp((x - bar.X) / (float)Math.Max(1, bar.Width), 0, 1);
		}

		bool OverBar(int2 pos) => BarRect().InflateBy(0, BarHitPad, 0, BarHitPad).Contains(pos);

		public override string GetCursor(int2 pos) => CanSeek() && (dragging || OverBar(pos)) ? "default" : null;

		public override bool HandleMouseInput(MouseInput mi)
		{
			if (!dragging && (mi.Button != MouseButton.Left || mi.Event != MouseInputEvent.Down))
				return false;

			switch (mi.Event)
			{
				case MouseInputEvent.Down:
					if (!CanSeek() || !OverBar(mi.Location) || !TakeMouseFocus(mi))
						return false;

					dragging = true;
					dragFraction = FractionAt(mi.Location.X);
					return true;

				case MouseInputEvent.Move:
					dragFraction = FractionAt(mi.Location.X);
					return true;

				case MouseInputEvent.Up:
					dragging = false;
					YieldMouseFocus(mi);
					if (CanSeek())
						OnSeek(dragFraction);

					return true;
			}

			return false;
		}

		public override void Draw()
		{
			var rb = RenderBounds;
			var song = GetSong();
			if (song != shown)
			{
				previous = shown;
				shown = song;
				changedAt = Game.RunTime;
			}

			var fade = Math.Clamp((Game.RunTime - changedAt) / (float)FadeTime, 0, 1);
			fade = fade * fade * (3 - 2 * fade);
			var playing = IsPlaying() && song != null;

			// Ease the meter in and out instead of snapping when pausing
			level += ((playing ? 1f : 0f) - level) * 0.08f;

			// Backdrop: the blurred cover, darkened, then shaded so the text stays readable
			WidgetUtils.FillRectWithColor(rb, Color.FromArgb(255, 8, 8, 10));
			if (fade < 1)
				PxMusicCovers.Draw(PxMusicCovers.Get(previous, true), rb, 1.1f, 0.6f, 1 - fade);

			PxMusicCovers.Draw(PxMusicCovers.Get(song, true), rb, 1.1f, song == null ? 0.25f : 0.6f, fade);
			var shade = new Rectangle(rb.X + TextX - 60, rb.Y, rb.Right - (rb.X + TextX - 60), rb.Height);
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Y, shade.X - rb.X, rb.Height), Color.FromArgb(70, 0, 0, 0));
			WidgetUtils.FillRectWithColor(shade, Color.FromArgb(70, 0, 0, 0), Color.FromArgb(200, 6, 6, 8),
				Color.FromArgb(220, 6, 6, 8), Color.FromArgb(70, 0, 0, 0));
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X, rb.Bottom - 50, rb.Width, 50), Color.FromArgb(0, 0, 0, 0), Color.FromArgb(0, 0, 0, 0),
				Color.FromArgb(150, 0, 0, 0), Color.FromArgb(150, 0, 0, 0));

			// Cover with a red frame that breathes while music plays
			var cover = new Rectangle(rb.X + CoverX, rb.Y + CoverY, CoverWidth, CoverHeight);
			var breathe = playing ? PxWarChrome.Pulse(1900) : 0;
			WidgetUtils.FillRectWithColor(cover.InflateBy(8, 8, 8, 8), Color.FromArgb(40, 0, 0, 0));
			WidgetUtils.FillRectWithColor(cover.InflateBy(4, 4, 4, 4), Color.FromArgb((int)(25 + 45 * breathe * level), PxDraw.Accent));
			PxWarChrome.DrawBorder(cover.InflateBy(1, 1, 1, 1), PxWarChrome.Lerp(Color.FromArgb(255, 60, 30, 30), PxDraw.Accent, 0.4f + 0.6f * level), 1);
			if (fade < 1 && previous != null)
				PxMusicCovers.DrawCover(previous, cover, 1.1f, 1f, 1 - fade);

			if (song != null)
				PxMusicCovers.DrawLive(song, cover, level, fade);
			else
				PxMusicCovers.DrawPlaceholder(null, cover, fade);

			// Corner brackets on the cover
			var bc = Color.FromArgb(220, 255, 106, 85);
			var corners = new[]
			{
				(cover.X - 5, cover.Y - 5, 1, 1), (cover.Right + 4, cover.Y - 5, -1, 1),
				(cover.X - 5, cover.Bottom + 4, 1, -1), (cover.Right + 4, cover.Bottom + 4, -1, -1)
			};

			foreach (var (cx, cy, dx, dy) in corners)
			{
				WidgetUtils.FillRectWithColor(new Rectangle(Math.Min(cx, cx + 14 * dx), cy, 14, 2), bc);
				WidgetUtils.FillRectWithColor(new Rectangle(cx, Math.Min(cy, cy + 14 * dy), 2, 14), bc);
			}

			// Text column
			var x = rb.X + TextX;
			var right = rb.Right - 24;
			var small = Game.Renderer.Fonts["PXSidebarSmall"];
			var title = Game.Renderer.Fonts["PXDisplayLarge"];
			var digits = Game.Renderer.Fonts["PXDigitsSmall"];

			var status = GetStatus();
			var dot = playing ? PxWarChrome.Lerp(PxDraw.Accent, PxDraw.AccentBright, PxWarChrome.Pulse(900)) : PxDraw.Dim;
			WidgetUtils.FillEllipseWithColor(new Rectangle(x, rb.Y + 26, 8, 8), dot);
			PxWarChrome.DrawSpaced(small, status, x + 16, rb.Y + 24, 2, playing ? PxDraw.AccentBright : PxDraw.Muted);

			// Level meter in the top right corner
			PxMusicCovers.DrawEqualizer(new Rectangle(right - 150, rb.Y + 18, 150, 40), 26, level, Color.FromArgb(200, PxDraw.Accent), PxDraw.AccentBright);

			var name = song?.Title ?? "No track playing";
			name = WidgetUtils.TruncateText(name, right - x - 160, title);
			title.DrawTextWithShadow(name, new float2(x, rb.Y + 44), Color.White, Color.FromArgb(160, 0, 0, 0), 2);
			PxWarChrome.DrawSpaced(small, GetSubtitle(), x + 1, rb.Y + 84, 1, PxDraw.Muted);

			// Progress bar: thickens under the mouse, previews the time to jump to, and follows a drag
			var length = song?.Length ?? 0;
			var canSeek = CanSeek() && length > 0;
			if (!canSeek)
				dragging = false;

			var mouse = Viewport.LastMousePos;
			var hover = canSeek && (dragging || (Ui.MouseOverWidget == this && OverBar(mouse)));
			var seek = song != null ? GetSeek() : 0;
			if (dragging)
				seek = dragFraction * length;

			var bar = BarRect();
			if (hover)
				bar = bar.InflateBy(0, 1, 0, 1);

			WidgetUtils.FillRectWithColor(bar, Color.FromArgb(255, 40, 41, 47));
			var progress = length > 0 ? Math.Clamp(seek / length, 0, 1) : 0;
			var done = (int)(bar.Width * progress);
			if (hover && !dragging)
			{
				var to = (int)(bar.Width * FractionAt(mouse.X));
				WidgetUtils.FillRectWithColor(new Rectangle(bar.X, bar.Y, to, bar.Height), Color.FromArgb(70, 255, 255, 255));
			}

			if (done > 0)
			{
				WidgetUtils.FillRectWithColor(new Rectangle(bar.X, bar.Y - 2, done, bar.Height + 4), Color.FromArgb(45, PxDraw.Accent));
				var dark = PxWarChrome.Darken(PxDraw.Accent, 0.3f);
				WidgetUtils.FillRectWithColor(new Rectangle(bar.X, bar.Y, done, bar.Height), dark, PxDraw.AccentBright, PxDraw.AccentBright, dark);
			}

			if (done > 0 || hover)
			{
				var k = hover ? 7 : 5;
				var cy = bar.Y + bar.Height / 2;
				if (hover)
					WidgetUtils.FillEllipseWithColor(new Rectangle(bar.X + done - k - 4, cy - k - 4, 2 * k + 8, 2 * k + 8), Color.FromArgb(60, PxDraw.Accent));

				WidgetUtils.FillEllipseWithColor(new Rectangle(bar.X + done - k, cy - k, 2 * k, 2 * k), Color.White);
			}

			// Time bubble above the bar
			if (hover)
			{
				var at = dragging ? bar.X + done : Math.Clamp(mouse.X, bar.X, bar.Right);
				var label = PxMusicCovers.Clock(FractionAt(at) * length);
				var size = digits.Measure(label);
				var bubble = new Rectangle(at - size.X / 2 - 7, bar.Y - size.Y - 18, size.X + 14, size.Y + 8);
				WidgetUtils.FillRectWithColor(bubble, PxDraw.Accent);
				Game.Renderer.RgbaColorRenderer.FillRect(new float3(at - 5, bubble.Bottom, 0), new float3(at + 5, bubble.Bottom, 0),
					new float3(at, bubble.Bottom + 5, 0), new float3(at, bubble.Bottom + 5, 0), PxDraw.Accent);
				digits.DrawText(label, new float2(bubble.X + 7, bubble.Y + 4), Color.White);
			}

			var elapsed = PxMusicCovers.Clock(seek);
			var total = length > 0 ? PxMusicCovers.Clock(length) : "-:--";
			digits.DrawText(elapsed, new float2(x, bar.Bottom + 8), Color.FromArgb(220, 222, 228));
			digits.DrawText(total, new float2(right - digits.Measure(total).X, bar.Bottom + 8), PxDraw.Muted);

			var note = GetNote();
			if (!string.IsNullOrEmpty(note))
				small.DrawText(note, new float2(right - small.Measure(note).X, rb.Bottom - 22), PxDraw.AccentBright);

			PxWarChrome.DrawBorder(rb, Color.FromArgb(255, 42, 43, 49), 1);
		}
	}

	/// <summary>A track tile in the soundtrack grid: cover art, number, title and length. Click to play.</summary>
	public class PxMusicCardWidget : ButtonWidget
	{
		public MusicInfo Song;
		public int Number;
		public Func<bool> IsCurrent = () => false;
		public Func<bool> IsPlaying = () => false;

		float hoverLevel;
		float liveLevel;

		[ObjectCreator.UseCtor]
		public PxMusicCardWidget(ModData modData)
			: base(modData) { }

		protected PxMusicCardWidget(PxMusicCardWidget other)
			: base(other)
		{
			Song = other.Song;
			Number = other.Number;
			IsCurrent = other.IsCurrent;
			IsPlaying = other.IsPlaying;
		}

		public override Widget Clone() { return new PxMusicCardWidget(this); }

		public override void Draw()
		{
			var rb = RenderBounds;
			var hover = Ui.MouseOverWidget == this && !IsDisabled();
			var current = IsCurrent();
			var playing = current && IsPlaying();
			hoverLevel += ((hover ? 1f : 0f) - hoverLevel) * 0.2f;
			liveLevel += ((playing ? 1f : 0f) - liveLevel) * 0.08f;

			// Art: dim at rest, brighter and pushed in on hover
			var art = rb.InflateBy(-1, -1, -1, -1);
			WidgetUtils.FillRectWithColor(rb, Color.FromArgb(255, 10, 10, 12));
			if (current)
				PxMusicCovers.DrawLive(Song, art, liveLevel, 1f, 0.95f, 10, true);
			else
				PxMusicCovers.DrawCover(Song, art, 1.02f + 0.05f * hoverLevel, 0.62f + 0.35f * hoverLevel, 1f, true);

			// Shade the left and bottom for the text
			WidgetUtils.FillRectWithColor(new Rectangle(art.X, art.Y, art.Width * 2 / 3, art.Height),
				Color.FromArgb(200, 6, 6, 8), Color.FromArgb(0, 6, 6, 8), Color.FromArgb(0, 6, 6, 8), Color.FromArgb(200, 6, 6, 8));
			WidgetUtils.FillRectWithColor(new Rectangle(art.X, art.Bottom - 46, art.Width, 46),
				Color.FromArgb(0, 0, 0, 0), Color.FromArgb(0, 0, 0, 0), Color.FromArgb(210, 0, 0, 0), Color.FromArgb(210, 0, 0, 0));

			var small = Game.Renderer.Fonts["PXSidebarSmall"];
			var titleFont = Game.Renderer.Fonts["PXSidebarTitle"];
			var digits = Game.Renderer.Fonts["PXDigitsSmall"];

			// Track number, or a level meter when this is the one playing
			if (current)
				PxMusicCovers.DrawEqualizer(new Rectangle(art.X + 14, art.Y + 12, 26, 18), 5, playing ? 1f : 0.05f, PxDraw.Accent, PxDraw.AccentBright, 2);
			else
				Game.Renderer.Fonts["PXDigitsTile"].DrawTextWithShadow($"{Number:D2}", new float2(art.X + 14, art.Y + 10),
					Color.FromArgb(hover ? 255 : 200, 255, 255, 255), Color.FromArgb(160, 0, 0, 0), 1);

			if (current)
			{
				var tag = playing ? "NOW PLAYING" : "PAUSED";
				var tw = PxWarChrome.SpacedWidth(small, tag, 1);
				var chip = new Rectangle(art.Right - tw - 22, art.Y + 10, tw + 14, 18);
				WidgetUtils.FillRectWithColor(chip, playing ? PxDraw.Accent : Color.FromArgb(220, 40, 40, 46));
				PxWarChrome.DrawSpaced(small, tag, chip.X + 7, chip.Y + 3, 1, Color.White);
			}

			var length = PxMusicCovers.Clock(Song.Length);
			var lw = digits.Measure(length).X;
			var title = WidgetUtils.TruncateText(Song.Title, art.Width - lw - 44, titleFont);
			titleFont.DrawTextWithShadow(title, new float2(art.X + 14, art.Bottom - 32), Color.White, Color.FromArgb(180, 0, 0, 0), 1);
			digits.DrawText(length, new float2(art.Right - 12 - lw, art.Bottom - 26), Color.FromArgb(210, 212, 220));

			// Hover play badge
			if (hoverLevel > 0.02f && !playing)
			{
				var a = (int)(230 * hoverLevel);
				var c = new float2(art.Right - 34, art.Y + art.Height / 2 - 6);
				WidgetUtils.FillEllipseWithColor(new Rectangle((int)c.X - 18, (int)c.Y - 18, 36, 36), Color.FromArgb(a, PxDraw.Accent));
				PxMusicButtonWidget.DrawGlyph(PxMusicGlyph.Play, c + new float2(1, 0), 7, Color.FromArgb(a, 255, 255, 255));
			}

			// Frame
			var frame = current ? PxDraw.Accent : PxWarChrome.Lerp(Color.FromArgb(255, 42, 43, 49), Color.FromArgb(255, 150, 152, 160), hoverLevel);
			if (current)
				PxWarChrome.DrawBorder(rb.InflateBy(2, 2, 2, 2), Color.FromArgb(playing ? (int)(50 + 60 * PxWarChrome.Pulse(1900)) : 40, PxDraw.Accent), 2);

			PxWarChrome.DrawBorder(rb, frame, current ? 2 : 1);
		}
	}
}
