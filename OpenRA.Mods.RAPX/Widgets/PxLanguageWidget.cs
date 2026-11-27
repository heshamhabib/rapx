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
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Main menu Language page: one card per FluentLanguages entry with its waving flag (collection lang-flags),
	/// native name, translated name, how much of the interface text it covers and its active/selected state.
	/// PxLanguageLogic applies the selection.
	/// </summary>
	public class PxLanguageWidget : Widget
	{
		public readonly string FlagCollection = "lang-flags";
		public readonly string ClickSound = ChromeMetrics.Get<string>("ClickSound");
		public readonly int HeaderHeight = 84;
		public readonly int FooterHeight = 76;
		public readonly int Columns = 3;

		const int Pad = 26;
		const int Gap = 16;

		static readonly Color Accent = Color.FromArgb(255, 92, 70);
		static readonly Color AccentDeep = Color.FromArgb(226, 38, 38);
		static readonly Color Gold = Color.FromArgb(255, 209, 102);
		static readonly Color Ink = Color.FromArgb(242, 236, 234);
		static readonly Color Dim = Color.FromArgb(150, 152, 162);
		static readonly Color Faint = Color.FromArgb(96, 98, 108);
		static readonly Color Live = Color.FromArgb(132, 214, 104);

		public readonly IReadOnlyList<FluentLanguage> Languages;
		public string Selected { get; private set; }
		public Action<string> OnActivate = _ => { };

		readonly Dictionary<string, float> coverage;
		readonly SpriteFont header, title, display, label, small;
		readonly Dictionary<string, float> hoverFade = new();
		long selectTime;

		[ObjectCreator.UseCtor]
		public PxLanguageWidget(ModData modData)
		{
			var languages = FluentLanguages.For(modData.Manifest);
			Languages = languages?.Languages ?? Array.Empty<FluentLanguage>();
			Selected = FluentLanguages.SelectedId;
			coverage = Languages.ToDictionary(l => l.Id, l => Coverage(modData, l));

			var fonts = Game.Renderer.Fonts;
			header = fonts["PXHeader"];
			title = fonts["PXTitle"];
			display = fonts["PXDisplayLarge"];
			label = fonts["PXLabel"];
			small = fonts["PXSmall"];
		}

		static readonly Regex MessageKey = new(@"^[a-zA-Z][\w-]*\s*=", RegexOptions.Multiline);

		static int CountMessages(ModData modData, IEnumerable<string> files)
		{
			var count = 0;
			foreach (var f in files)
				using (var reader = new StreamReader(modData.DefaultFileSystem.Open(f)))
					count += MessageKey.Matches(reader.ReadToEnd()).Count;

			return count;
		}

		/// <summary>Share of the mod's interface messages the language translates (the default language is complete).</summary>
		static float Coverage(ModData modData, FluentLanguage language)
		{
			if (language.Id == FluentLanguages.DefaultLanguage)
				return 1f;

			try
			{
				var total = CountMessages(modData, modData.Manifest.FluentMessages);
				return total == 0 ? 0 : Math.Min(1f, CountMessages(modData, language.Messages) / (float)total);
			}
			catch (Exception e)
			{
				Log.Write("debug", $"Language coverage for {language.Id} failed: {e.Message}");
				return 0;
			}
		}

		static string Message(string key, string fallback) =>
			FluentProvider.TryGetMessage(key, out var message) ? message : fallback;

		void Select(string id)
		{
			if (id == Selected)
				return;

			Selected = id;
			selectTime = Game.RunTime;
			Game.Sound.PlayNotification(Game.ModData.DefaultRules, null, "Sounds", ClickSound, null);
		}

		Rectangle Grid
		{
			get
			{
				var r = RenderBounds;
				var top = r.Y + HeaderHeight + 56;
				return new Rectangle(r.X + Pad, top, r.Width - 2 * Pad, r.Bottom - FooterHeight - 12 - top);
			}
		}

		Rectangle CardRect(int i)
		{
			var g = Grid;
			var rows = Math.Max(1, (Languages.Count + Columns - 1) / Columns);
			var w = (g.Width - (Columns - 1) * Gap) / Columns;
			var h = (g.Height - (rows - 1) * Gap) / rows;
			return new Rectangle(g.X + i % Columns * (w + Gap), g.Y + i / Columns * (h + Gap), w, h);
		}

		public override bool HandleMouseInput(MouseInput mi)
		{
			if (mi.Event == MouseInputEvent.Down && mi.Button == MouseButton.Left)
			{
				for (var i = 0; i < Languages.Count; i++)
				{
					if (!CardRect(i).Contains(mi.Location))
						continue;

					var id = Languages[i].Id;
					if (mi.MultiTapCount > 1 && id == Selected)
						OnActivate(id);
					else
						Select(id);

					return true;
				}
			}

			return EventBounds.Contains(mi.Location);
		}

		public override bool HandleKeyPress(KeyInput e)
		{
			if (e.Event != KeyInputEvent.Down || Languages.Count == 0)
				return false;

			var i = Math.Max(0, Languages.ToList().FindIndex(l => l.Id == Selected));
			switch (e.Key)
			{
				case Keycode.LEFT: i--; break;
				case Keycode.RIGHT: i++; break;
				case Keycode.UP: i -= Columns; break;
				case Keycode.DOWN: i += Columns; break;
				default: return false;
			}

			Select(Languages[Math.Clamp(i, 0, Languages.Count - 1)].Id);
			return true;
		}

		static void Fill(Rectangle r, Color c) => WidgetUtils.FillRectWithColor(r, c);

		static void Gradient(Rectangle r, Color top, Color bottom)
		{
			Game.Renderer.RgbaColorRenderer.FillRect(new float3(r.X, r.Y, 0), new float3(r.Right, r.Y, 0),
				new float3(r.Right, r.Bottom, 0), new float3(r.X, r.Bottom, 0), top, top, bottom, bottom);
		}

		static void HGradient(Rectangle r, Color left, Color right)
		{
			Game.Renderer.RgbaColorRenderer.FillRect(new float3(r.X, r.Y, 0), new float3(r.Right, r.Y, 0),
				new float3(r.Right, r.Bottom, 0), new float3(r.X, r.Bottom, 0), left, right, right, left);
		}

		static void Brackets(Rectangle r, int len, Color c, int w = 2)
		{
			Fill(new Rectangle(r.X, r.Y, len, w), c);
			Fill(new Rectangle(r.X, r.Y, w, len), c);
			Fill(new Rectangle(r.Right - len, r.Y, len, w), c);
			Fill(new Rectangle(r.Right - w, r.Y, w, len), c);
			Fill(new Rectangle(r.X, r.Bottom - w, len, w), c);
			Fill(new Rectangle(r.X, r.Bottom - len, w, len), c);
			Fill(new Rectangle(r.Right - len, r.Bottom - w, len, w), c);
			Fill(new Rectangle(r.Right - w, r.Bottom - len, w, len), c);
		}

		static Color Alpha(Color c, float a) => Color.FromArgb((int)Math.Clamp(c.A * a, 0, 255), c.R, c.G, c.B);

		static void Text(SpriteFont font, string text, float x, float y, Color color) =>
			font.DrawTextWithShadow(text, new float2(x, y), color, Color.FromArgb(color.A * 3 / 4, 0, 0, 0), 1);

		public override void Draw()
		{
			DrawBackdrop();
			DrawHeader();

			var mouse = Viewport.LastMousePos;
			for (var i = 0; i < Languages.Count; i++)
				DrawCard(CardRect(i), Languages[i], mouse);

			DrawFooter();
		}

		void DrawBackdrop()
		{
			var r = RenderBounds;
			Fill(new Rectangle(0, 0, Game.Renderer.Resolution.Width, Game.Renderer.Resolution.Height), Color.FromArgb(150, 0, 0, 0));
			Fill(new Rectangle(r.X + 4, r.Y + 6, r.Width, r.Height), Color.FromArgb(120, 0, 0, 0));
			Gradient(r, Color.FromArgb(246, 17, 18, 22), Color.FromArgb(250, 8, 9, 11));

			for (var x = r.X + 16; x < r.Right; x += 32)
				Fill(new Rectangle(x, r.Y, 1, r.Height), Color.FromArgb(7, 255, 255, 255));
			for (var y = r.Y + 16; y < r.Bottom; y += 32)
				Fill(new Rectangle(r.X, y, r.Width, 1), Color.FromArgb(7, 255, 255, 255));

			// Slow radar sweep across the panel
			var sweep = (Game.RunTime % 7000) / 7000f;
			var sx = r.X + (int)(sweep * (r.Width + 300)) - 300;
			Game.Renderer.EnableScissor(r);
			HGradient(new Rectangle(sx, r.Y, 300, r.Height), Color.FromArgb(0, AccentDeep), Color.FromArgb(14, AccentDeep));
			Game.Renderer.DisableScissor();

			PxWarChrome.DrawBorder(r, Color.FromArgb(255, 44, 45, 52), 1);
			Brackets(r.InflateBy(-1, -1, -1, -1), 26, Alpha(Accent, 0.9f));
		}

		void DrawHeader()
		{
			var r = RenderBounds;
			var h = new Rectangle(r.X, r.Y, r.Width, HeaderHeight);
			Gradient(h, Color.FromArgb(255, 28, 20, 20), Color.FromArgb(255, 15, 15, 18));
			HGradient(new Rectangle(h.X, h.Bottom - 2, h.Width, 2), AccentDeep, Color.FromArgb(0, AccentDeep));
			Fill(new Rectangle(h.X + 22, h.Y + 20, 4, HeaderHeight - 40), Accent);

			PxWarChrome.DrawSpaced(header, Message("label-px-language-kicker", "PROJECT X  //  COMMS PROTOCOL"), h.X + 38, h.Y + 16, 2, Accent);
			Text(title, Message("label-px-language-title", "Language"), h.X + 36, h.Y + 32, Ink);

			// Active language readout on the right
			var active = Languages.FirstOrDefault(l => l.Id == FluentLanguages.SelectedId);
			if (active != null)
			{
				var caption = Message("label-px-language-active", "ACTIVE");
				var name = active.NativeName ?? active.Name;
				var nw = label.Measure(name).X;
				var cw = PxWarChrome.SpacedWidth(header, caption, 2);
				var flag = ChromeProvider.TryGetImage(FlagCollection, active.Id);
				var right = h.Right - 30;
				var y = h.Y + (HeaderHeight - 30) / 2;
				Text(label, name, right - nw, y + 6, Ink);
				var x = right - nw - 12;
				if (flag != null)
				{
					x -= 39;
					Fill(new Rectangle(x - 1, y - 1, 41, 28), Color.FromArgb(255, 60, 61, 70));
					WidgetUtils.DrawSprite(flag, new float2(x, y), new float2(39, 26));
				}

				var dotPulse = PxWarChrome.Pulse(1400);
				var cx = x - 14 - cw;
				WidgetUtils.FillEllipseWithColor(new Rectangle(cx - 14, y + 9, 8, 8), Alpha(Live, 0.5f + 0.5f * dotPulse));
				PxWarChrome.DrawSpaced(header, caption, cx, y + 7, 2, Live);
			}

			var sub = Message("label-px-language-subtitle", "Choose the language for menus, orders and briefings.");
			Text(label, sub, r.X + Pad, h.Bottom + 18, Dim);
		}

		void DrawCard(Rectangle r, FluentLanguage language, int2 mouse)
		{
			var id = language.Id;
			var selected = id == Selected;
			var active = id == FluentLanguages.SelectedId;
			var hover = r.Contains(mouse);

			// Ease hover in and out
			var fade = hoverFade.GetValueOrDefault(id);
			fade = Math.Clamp(fade + (hover ? 0.12f : -0.08f), 0, 1);
			hoverFade[id] = fade;

			var lift = (int)(fade * 3);
			r = new Rectangle(r.X, r.Y - lift, r.Width, r.Height);

			Fill(new Rectangle(r.X + 5, r.Y + 7 + lift, r.Width, r.Height), Color.FromArgb(110, 0, 0, 0));
			Gradient(r, PxWarChrome.Lerp(Color.FromArgb(255, 25, 26, 31), Color.FromArgb(255, 36, 37, 44), fade),
				Color.FromArgb(255, 13, 14, 17));

			if (selected)
			{
				var t = Math.Clamp((Game.RunTime - selectTime) / 300f, 0, 1);
				Gradient(r, Color.FromArgb((int)(70 * t), AccentDeep), Color.FromArgb(0, AccentDeep));
			}

			// Watermark language code
			var code = id.ToUpperInvariant();
			var cw = display.Measure(code).X;
			Text(display, code, r.Right - cw - 18, r.Y + 14, Color.FromArgb(selected ? 70 : 34, 255, 255, 255));

			// Flag on a pole, waving harder under the cursor
			var flag = ChromeProvider.TryGetImage(FlagCollection, id);
			var fh = Math.Min(102, r.Height - 110);
			var fw = fh * 3 / 2;
			var fr = new Rectangle(r.X + 40, r.Y + 26, fw, fh);
			Fill(new Rectangle(fr.X - 8, r.Y + 18, 3, fh + 26), Color.FromArgb(255, 130, 132, 140));
			Fill(new Rectangle(fr.X - 6, r.Y + 18, 1, fh + 26), Color.FromArgb(120, 255, 255, 255));
			WidgetUtils.FillEllipseWithColor(new Rectangle(fr.X - 10, r.Y + 13, 7, 7), Gold);
			if (flag != null)
			{
				var time = Game.RunTime / 1000f + id.GetHashCode() % 7;
				PxFlagDraw.Waving(flag, new Rectangle(fr.X + 3, fr.Y + 5, fr.Width, fr.Height), time, 3f + 3f * fade, 0.45f, true);
				PxFlagDraw.Waving(flag, fr, time, 3f + 3f * fade, selected || hover ? 1f : 0.86f);
			}

			// Status chips stacked under the language code, right-aligned
			var chipRight = r.Right - 18;
			var chipY = r.Y + 56;
			if (active)
				chipY = Chip(chipRight, chipY, Message("label-px-language-active", "ACTIVE"), Live, Color.FromArgb(14, 30, 10)) + 6;
			else if (selected)
				chipY = Chip(chipRight, chipY, Message("label-px-language-selected", "SELECTED"), Accent, Color.White) + 6;

			if (language.Messages.Length > 0 && IsRightToLeft(language))
				Chip(chipRight, chipY, Message("label-px-language-rtl", "RIGHT-TO-LEFT"), Color.FromArgb(255, 48, 49, 56), Dim);

			// Names
			var y = r.Bottom - 84;
			Text(display, language.NativeName ?? language.Name, r.X + 24, y, selected || hover ? Color.White : Ink);
			var local = Message("label-px-language-name-" + id, language.Name).ToUpperInvariant();
			PxWarChrome.DrawSpaced(header, local, r.X + 26, y + 40, 2, selected ? Accent : Dim);

			// Interface coverage
			var pct = coverage.GetValueOrDefault(id);
			var bar = new Rectangle(r.Right - 24 - 130, r.Bottom - 30, 130, 6);
			var pctText = ((int)Math.Round(pct * 100)).ToString(CultureInfo.InvariantCulture) + "%";
			var pw = label.Measure(pctText).X;
			Text(label, pctText, bar.Right - pw, bar.Y - 24, pct >= 0.99f ? Live : Gold);
			var cap = WidgetUtils.TruncateText(Message("label-px-language-coverage", "INTERFACE"), bar.Width - pw - 8, header);
			PxWarChrome.DrawSpaced(header, cap, bar.X, bar.Y - 19, 1, Faint);
			Fill(bar, Color.FromArgb(255, 30, 31, 36));
			PxWarChrome.DrawSegments(bar, pct, pct >= 0.99f ? Live : Gold, 6);

			// Scanline sweep while hovered
			if (fade > 0)
			{
				var sy = r.Y + (int)((Game.RunTime % 1600) / 1600f * r.Height);
				HGradient(new Rectangle(r.X, sy, r.Width / 2, 1), Color.FromArgb(0, Accent), Color.FromArgb((int)(90 * fade), Accent));
				HGradient(new Rectangle(r.X + r.Width / 2, sy, r.Width - r.Width / 2, 1), Color.FromArgb((int)(90 * fade), Accent), Color.FromArgb(0, Accent));
			}

			if (selected)
			{
				var pulse = PxWarChrome.Pulse(1600);
				PxWarChrome.DrawBorder(r.InflateBy(1, 1, 1, 1), Accent, 2);
				PxWarChrome.DrawBorder(r.InflateBy(4, 4, 4, 4), Color.FromArgb((int)(40 + 70 * pulse), Accent), 2);
				Fill(new Rectangle(r.X, r.Y, 4, r.Height), Accent);
				Brackets(r.InflateBy(-6, -6, -6, -6), 14, Alpha(Ink, 0.7f), 1);
			}
			else
			{
				PxWarChrome.DrawBorder(r, PxWarChrome.Lerp(Color.FromArgb(255, 42, 43, 50), Color.FromArgb(255, 120, 122, 132), fade), 1);
				if (active)
					Fill(new Rectangle(r.X, r.Y, 4, r.Height), Live);
			}
		}

		static bool IsRightToLeft(FluentLanguage language) => (language.NativeName ?? "").Any(c => c >= 0x0590 && c <= 0x08FF);

		int Chip(int right, int y, string text, Color background, Color foreground)
		{
			var w = PxWarChrome.SpacedWidth(header, text, 1) + 16;
			var x = right - w;
			Fill(new Rectangle(x, y, w, 20), background);
			PxWarChrome.DrawSpaced(header, text, x + 8, y + 3, 1, foreground);
			return y + 20;
		}

		void DrawFooter()
		{
			var r = RenderBounds;
			var f = new Rectangle(r.X, r.Bottom - FooterHeight, r.Width, FooterHeight);
			Gradient(f, Color.FromArgb(255, 15, 15, 18), Color.FromArgb(255, 24, 18, 18));
			HGradient(new Rectangle(f.X, f.Y, f.Width, 1), Alpha(AccentDeep, 0.8f), Color.FromArgb(0, AccentDeep));

			var note = Selected == FluentLanguages.SelectedId
				? Message("label-px-language-note", "Double-click a language or press Apply. The interface reloads in the new language.")
				: Message("label-px-language-pending", "Press Apply to switch. The interface reloads in the new language.");
			Fill(new Rectangle(f.X + 26, f.Y + (FooterHeight - 14) / 2, 3, 14), Gold);
			Text(small, note, f.X + 38, f.Y + (FooterHeight - 18) / 2, Dim);
		}
	}
}
