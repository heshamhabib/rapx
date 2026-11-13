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
using System.Linq;
using OpenRA.FileFormats;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;
using StbImageSharp;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// The Extras "Arsenal" catalogue: nation rail, nation dossier banner, category tabs, a card grid of painted
	/// cameos and a detail column with the real in-game model turning on a hologram stage, stats, damage grades,
	/// weapons, capabilities and the written dossier. All data comes from <see cref="PxCatalogueData"/>.
	/// </summary>
	public class PxCatalogueWidget : Widget
	{
		public readonly string SeedActor = "fact";
		public readonly string UnionOwner = "Allies";
		public readonly string VanguardOwner = "Soviets";
		public readonly string ClickSound = ChromeMetrics.Get<string>("ClickSound");
		public readonly int HeaderHeight = 72;

		const int Gap = 10;

		static readonly Color Accent = Color.FromArgb(255, 92, 70);
		static readonly Color AccentDeep = Color.FromArgb(226, 38, 38);
		static readonly Color Union = Color.FromArgb(58, 123, 255);
		static readonly Color UnionText = Color.FromArgb(143, 182, 255);
		static readonly Color Vanguard = Color.FromArgb(226, 38, 38);
		static readonly Color VanguardText = Color.FromArgb(255, 138, 122);
		static readonly Color Gold = Color.FromArgb(255, 209, 102);
		static readonly Color Ink = Color.FromArgb(242, 236, 234);
		static readonly Color Dim = Color.FromArgb(150, 152, 162);
		static readonly Color Faint = Color.FromArgb(96, 98, 108);
		static readonly Color Holo = Color.FromArgb(120, 220, 255);

		static readonly string[] CategoryLabels = { "STRUCTURES", "DEFENCES", "INFANTRY", "VEHICLES", "AIRCRAFT", "NAVAL" };

		readonly ModData modData;
		readonly World world;
		readonly WorldRenderer worldRenderer;
		readonly Dictionary<(string Actor, string Faction), (Sprite Sprite, PaletteReference Palette)> cameos = new();
		readonly Dictionary<string, string[]> wrapCache = new();

		PxCatalogueData data;
		SpriteFont title, display, displayLarge, header, body, small, tiny, label, button;

		PxCatalogueData.Nation nation;
		int category;
		PxCatalogueData.Entry selected;
		List<PxCatalogueData.Entry> visible = new();
		int gridScroll, infoScroll, infoHeight, gridHeight;
		long selectTime, nationTime;

		// Big copies of the sidebar cameos (artsrc/px-cameos/make_catalogue_art.py), a few kept loaded
		readonly Dictionary<string, (Sheet Sheet, Sprite Sprite)> pictures = new();
		readonly List<string> pictureOrder = new();

		// Layout, recomputed every frame from the render bounds
		Rectangle rail, banner, tabs, grid, stage, info;
		int cols, cardW, cardH;

		[ObjectCreator.UseCtor]
		public PxCatalogueWidget(ModData modData, World world, WorldRenderer worldRenderer)
		{
			this.modData = modData;
			this.world = world;
			this.worldRenderer = worldRenderer;
		}

		public override void Initialize(WidgetArgs args)
		{
			base.Initialize(args);
			var f = Game.Renderer.Fonts;
			title = f["PXTitle"];
			display = f["PXDisplay"];
			displayLarge = f["PXDisplayLarge"];
			header = f["PXHeader"];
			body = f["PXBody"];
			small = f["PXSmall"];
			tiny = f["PXSidebarSmall"];
			label = f["PXLabel"];
			button = f["PXButton"];

			data = new PxCatalogueData(modData.DefaultRules, SeedActor);
			SelectNation(data.Nations.FirstOrDefault(), false);
		}

		void Click() => Game.Sound.PlayNotification(modData.DefaultRules, null, "Sounds", ClickSound, null);

		void SelectNation(PxCatalogueData.Nation n, bool sound = true)
		{
			if (n == null)
				return;

			if (sound && n != nation)
				Click();

			nation = n;
			nationTime = Game.RunTime;
			if (Count(category) == 0)
				category = Enumerable.Range(0, PxCatalogueData.Categories.Length).FirstOrDefault(c => Count(c) > 0);

			SelectCategory(category, false);
		}

		int Count(int c) => nation == null ? 0 :
			data.Entries.Count(e => e.Category == PxCatalogueData.Categories[c] && e.Nations.Contains(nation.Id));

		void SelectCategory(int c, bool sound = true)
		{
			if (sound && c != category)
				Click();

			category = c;
			gridScroll = 0;
			visible = data.Entries.Where(e => e.Category == PxCatalogueData.Categories[c] && e.Nations.Contains(nation.Id)).ToList();
			var keep = selected != null && visible.Contains(selected) ? selected : visible.FirstOrDefault();
			Select(keep, false, true);
		}

		void Select(PxCatalogueData.Entry e, bool sound = true, bool force = false)
		{
			if (e == selected && !force)
				return;

			if (sound)
				Click();

			selected = e;
			infoScroll = 0;
			selectTime = Game.RunTime;
		}

		Player Owner()
		{
			var name = nation?.Side == "Union" ? UnionOwner : VanguardOwner;
			return world.Players.FirstOrDefault(p => p.InternalName == name) ?? world.WorldActor.Owner;
		}

		/// <summary>The catalogue picture for an entry: bits/hd/catalogue/&lt;image&gt;.jpg, the sidebar cameo at 4x.</summary>
		Sprite Picture(PxCatalogueData.Entry e)
		{
			var rs = e.Actor.TraitInfoOrDefault<RenderSpritesInfo>();
			var names = new[] { rs?.GetImage(e.Actor, nation.Id), rs?.Image, e.Actor.Name }.Where(n => n != null).Select(n => n.ToLowerInvariant()).Distinct();
			foreach (var name in names)
			{
				if (pictures.TryGetValue(name, out var cached))
					return cached.Sprite;

				if (!modData.DefaultFileSystem.TryOpen($"ra|bits/hd/catalogue/{name}.jpg", out var stream))
					continue;

				try
				{
					using (stream)
					{
						var jpeg = ImageResult.FromStream(stream, ColorComponents.RedGreenBlueAlpha);
						var png = new Png(jpeg.Data, SpriteFrameType.Rgba32, jpeg.Width, jpeg.Height);
						var sheet = new Sheet(SheetType.BGRA, new Size(png.Width, png.Height).NextPowerOf2());
						var sprite = new Sprite(sheet, new Rectangle(0, 0, png.Width, png.Height), TextureChannel.RGBA);
						OpenRA.Graphics.Util.FastCopyIntoSprite(sprite, png);
						sheet.ReleaseBuffer();
						sheet.GetTexture().ScaleFilter = TextureScaleFilter.Linear;

						pictures[name] = (sheet, sprite);
						pictureOrder.Add(name);
						if (pictureOrder.Count > 12)
						{
							pictures[pictureOrder[0]].Sheet.Dispose();
							pictures.Remove(pictureOrder[0]);
							pictureOrder.RemoveAt(0);
						}

						return sprite;
					}
				}
				catch (Exception ex)
				{
					Log.Write("debug", $"Catalogue picture {name} failed: {ex.Message}");
				}
			}

			return null;
		}

		public override void Removed()
		{
			base.Removed();
			foreach (var p in pictures.Values)
				p.Sheet.Dispose();
			pictures.Clear();
			pictureOrder.Clear();
		}

		(Sprite Sprite, PaletteReference Palette) Cameo(PxCatalogueData.Entry e)
		{
			var key = (e.Actor.Name, nation.Id);
			if (cameos.TryGetValue(key, out var cached))
				return cached;

			(Sprite, PaletteReference) result = (null, null);
			try
			{
				var bi = e.Actor.TraitInfo<BuildableInfo>();
				var image = e.Actor.TraitInfo<RenderSpritesInfo>().GetImage(e.Actor, nation.Id);
				var sequence = world.Map.Sequences.HasSequence(image, "px-" + bi.Icon) ? "px-" + bi.Icon : bi.Icon;
				var anim = new Animation(world, image);
				anim.Play(sequence);
				var palette = bi.IconPaletteIsPlayerPalette ? bi.IconPalette + Owner().InternalName : bi.IconPalette;
				result = (anim.Image, worldRenderer.Palette(palette));
			}
			catch (Exception ex)
			{
				Log.Write("debug", $"Catalogue cameo failed for {e.Actor.Name}: {ex.Message}");
			}

			return cameos[key] = result;
		}

		void Layout()
		{
			var r = RenderBounds;
			const int Pad = 22;
			var top = r.Y + HeaderHeight + 10;
			rail = new Rectangle(r.X + Pad, top, 228, r.Bottom - Pad - top);
			var x0 = rail.Right + 20;
			var w = r.Right - Pad - x0;
			banner = new Rectangle(x0, top, w, 112);
			tabs = new Rectangle(x0, banner.Bottom + 12, w, 44);
			var bodyTop = tabs.Bottom + 14;
			var bodyH = r.Bottom - Pad - bodyTop;

			var gridW = Math.Clamp(w * 43 / 100, 330, 560);
			cols = Math.Max(2, (gridW + Gap) / (156 + Gap));
			cardW = (gridW - 10 - (cols - 1) * Gap) / cols;
			cardH = cardW * 2 / 3 + 30;
			grid = new Rectangle(x0, bodyTop, gridW, bodyH);

			var dx = grid.Right + 20;
			var detail = new Rectangle(dx, bodyTop, r.Right - Pad - dx, bodyH);
			stage = new Rectangle(detail.X, detail.Y, detail.Width, Math.Clamp(Math.Min(detail.Width * 2 / 3, bodyH * 56 / 100), 220, 520));
			info = new Rectangle(detail.X, stage.Bottom + 12, detail.Width, detail.Bottom - stage.Bottom - 12);
		}

		public override bool HandleMouseInput(MouseInput mi)
		{
			var p = mi.Location;
			if (mi.Event == MouseInputEvent.Scroll)
			{
				var step = mi.Delta.Y * 48;
				if (grid.Contains(p))
					gridScroll = Math.Clamp(gridScroll - step, 0, Math.Max(0, gridHeight - grid.Height));
				else if (info.Contains(p))
					infoScroll = Math.Clamp(infoScroll - step, 0, Math.Max(0, infoHeight - info.Height));
				return true;
			}

			if (mi.Event != MouseInputEvent.Down || mi.Button != MouseButton.Left)
				return EventBounds.Contains(p);

			foreach (var (row, n) in RailRows())
			{
				if (row.Contains(p))
				{
					SelectNation(n);
					return true;
				}
			}

			for (var c = 0; c < CategoryLabels.Length; c++)
			{
				if (TabRect(c).Contains(p) && Count(c) > 0)
				{
					SelectCategory(c);
					return true;
				}
			}

			if (grid.Contains(p))
			{
				for (var i = 0; i < visible.Count; i++)
				{
					if (CardRect(i).Contains(p))
					{
						Select(visible[i]);
						return true;
					}
				}

				return true;
			}

			return EventBounds.Contains(p);
		}

		public override bool HandleKeyPress(KeyInput e)
		{
			if (e.Event != KeyInputEvent.Down || visible.Count == 0)
				return false;

			var i = Math.Max(0, visible.IndexOf(selected));
			switch (e.Key)
			{
				case Keycode.LEFT: i--; break;
				case Keycode.RIGHT: i++; break;
				case Keycode.UP: i -= cols; break;
				case Keycode.DOWN: i += cols; break;
				case Keycode.TAB:
					SelectCategory(Enumerable.Range(1, CategoryLabels.Length)
						.Select(d => (category + (e.Modifiers.HasModifier(Modifiers.Shift) ? -d : d) + CategoryLabels.Length) % CategoryLabels.Length)
						.First(c => Count(c) > 0));
					return true;
				default: return false;
			}

			i = Math.Clamp(i, 0, visible.Count - 1);
			Select(visible[i]);
			var card = CardRect(i);
			if (card.Y < grid.Y)
				gridScroll -= grid.Y - card.Y;
			else if (card.Bottom > grid.Bottom)
				gridScroll += card.Bottom - grid.Bottom;
			return true;
		}

		public override void Draw()
		{
			Layout();
			DrawBackdrop();
			DrawHeader();
			DrawRail();
			DrawBanner();
			DrawTabs();
			DrawGrid();
			DrawStage();
			DrawInfo();
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

		static Color SideColor(string side) => side == "Union" ? Union : side == "Vanguard" ? Vanguard : Faint;
		static Color SideText(string side) => side == "Union" ? UnionText : side == "Vanguard" ? VanguardText : Dim;

		static void Text(SpriteFont font, string text, float x, float y, Color color, bool shadow = true)
		{
			if (shadow)
				font.DrawTextWithShadow(text, new float2(x, y), color, Color.FromArgb(color.A * 3 / 4, 0, 0, 0), 1);
			else
				font.DrawText(text, new float2(x, y), color);
		}

		static void TextRight(SpriteFont font, string text, float right, float y, Color color) =>
			Text(font, text, right - font.Measure(text).X, y, color);

		string[] Wrap(string text, int width, SpriteFont font)
		{
			var key = $"{width}|{font.GetHashCode()}|{text}";
			if (!wrapCache.TryGetValue(key, out var lines))
				wrapCache[key] = lines = WidgetUtils.WrapText(text, width, font).Split('\n');
			return lines;
		}

		static Sprite Flag(string id) => ChromeProvider.TryGetImage("flags-large", id) ?? ChromeProvider.TryGetImage("flags", id);

		static string Money(int v) => "$" + v.ToString("N0", CultureInfo.InvariantCulture);

		static string Seconds(int ticks)
		{
			var s = (int)Math.Round(ticks / (float)PxCatalogueData.Ticks);
			return $"{s / 60}:{s % 60:D2}";
		}

		static string Num(float v) => v >= 10 ? v.ToString("0", CultureInfo.InvariantCulture) : v.ToString("0.#", CultureInfo.InvariantCulture);

		void DrawBackdrop()
		{
			var r = RenderBounds;
			Fill(new Rectangle(0, 0, Game.Renderer.Resolution.Width, Game.Renderer.Resolution.Height), Color.FromArgb(150, 0, 0, 0));
			Fill(new Rectangle(r.X + 4, r.Y + 6, r.Width, r.Height), Color.FromArgb(120, 0, 0, 0));
			Gradient(r, Color.FromArgb(246, 17, 18, 22), Color.FromArgb(250, 8, 9, 11));

			// Faint tactical grid
			for (var x = r.X + 16; x < r.Right; x += 32)
				Fill(new Rectangle(x, r.Y, 1, r.Height), Color.FromArgb(7, 255, 255, 255));
			for (var y = r.Y + 16; y < r.Bottom; y += 32)
				Fill(new Rectangle(r.X, y, r.Width, 1), Color.FromArgb(7, 255, 255, 255));

			// Side glow behind the selected nation's colour
			if (nation != null)
			{
				var glow = SideColor(nation.Side);
				HGradient(new Rectangle(r.X, r.Y, r.Width / 2, r.Height), Color.FromArgb(18, glow), Color.FromArgb(0, glow));
			}

			PxWarChrome.DrawBorder(r, Color.FromArgb(255, 44, 45, 52), 1);
			Brackets(r.InflateBy(-1, -1, -1, -1), 26, Alpha(Accent, 0.9f));
		}

		void DrawHeader()
		{
			var r = RenderBounds;
			var h = new Rectangle(r.X, r.Y, r.Width, HeaderHeight);
			Gradient(h, Color.FromArgb(255, 28, 20, 20), Color.FromArgb(255, 15, 15, 18));
			HGradient(new Rectangle(h.X, h.Bottom - 2, h.Width, 2), AccentDeep, Color.FromArgb(0, AccentDeep));
			Fill(new Rectangle(h.X + 22, h.Y + 18, 4, HeaderHeight - 36), Accent);

			PxWarChrome.DrawSpaced(header, "PROJECT X  //  CLASSIFIED WAR ARCHIVE", h.X + 38, h.Y + 14, 2, Accent);
			Text(title, "ARSENAL CATALOGUE", h.X + 36, h.Y + 26, Ink);

			var total = data.Entries.Count;
			var stats = $"{data.Nations.Count} NATIONS   ·   {total} ENTRIES   ·   ARROWS / TAB TO BROWSE";
			var sx = h.X + 36 + title.Measure("ARSENAL CATALOGUE").X + 28;
			PxWarChrome.DrawSpaced(tiny, stats, sx, h.Y + 40, 1, Faint);
		}

		IEnumerable<(Rectangle Row, PxCatalogueData.Nation Nation)> RailRows()
		{
			var groups = data.Nations.GroupBy(n => n.Side).ToList();
			var rows = data.Nations.Count;
			var rowH = Math.Clamp((rail.Height - 40 - groups.Count * 30) / Math.Max(1, rows), 22, 36);
			var y = rail.Y + 40;
			foreach (var g in groups)
			{
				y += 30;
				foreach (var n in g)
				{
					yield return (new Rectangle(rail.X, y, rail.Width, rowH - 3), n);
					y += rowH;
				}
			}
		}

		void DrawRail()
		{
			Gradient(rail, Color.FromArgb(200, 22, 23, 28), Color.FromArgb(200, 12, 13, 16));
			PxWarChrome.DrawBorder(rail, Color.FromArgb(255, 36, 37, 44), 1);
			PxWarChrome.DrawSpaced(header, "SELECT NATION", rail.X + 14, rail.Y + 14, 2, Dim);
			Fill(new Rectangle(rail.X + 14, rail.Y + 32, rail.Width - 28, 1), Color.FromArgb(60, 255, 106, 85));

			var mouse = Viewport.LastMousePos;
			string lastSide = null;
			foreach (var (row, n) in RailRows())
			{
				if (n.Side != lastSide)
				{
					lastSide = n.Side;
					var hy = row.Y - 26;
					Fill(new Rectangle(rail.X + 14, hy + 8, 3, 12), SideColor(n.Side));
					PxWarChrome.DrawSpaced(header, n.Side.ToUpperInvariant(), rail.X + 24, hy + 6, 3, SideText(n.Side));
					var count = data.Nations.Count(o => o.Side == n.Side);
					TextRight(tiny, $"{count} NATIONS", rail.Right - 14, hy + 8, Faint);
				}

				var sel = n == nation;
				var hover = row.Contains(mouse);
				if (sel)
				{
					HGradient(row, Alpha(SideColor(n.Side), 0.55f), Color.FromArgb(30, SideColor(n.Side)));
					Fill(new Rectangle(row.X, row.Y, 3, row.Height), Ink);
				}
				else if (hover)
					HGradient(row, Color.FromArgb(40, 255, 255, 255), Color.FromArgb(0, 255, 255, 255));

				var flag = Flag(n.Id);
				var fh = row.Height - 8;
				var fw = fh * 3 / 2;
				if (flag != null)
				{
					Fill(new Rectangle(row.X + 13, row.Y + 5, fw, fh), Color.FromArgb(140, 0, 0, 0));
					WidgetUtils.DrawSprite(flag, new float2(row.X + 12, row.Y + 4), new float2(fw, fh));
				}

				var font = row.Height >= 28 ? label : small;
				Text(font, n.Name.ToUpperInvariant(), row.X + 22 + fw, row.Y + (row.Height - font.Measure("A").Y) / 2 - 1, sel ? Color.White : hover ? Ink : Dim);
			}
		}

		void DrawBanner()
		{
			if (nation == null)
				return;

			var b = banner;
			var side = SideColor(nation.Side);
			Gradient(b, Color.FromArgb(220, 24, 25, 30), Color.FromArgb(220, 13, 14, 17));
			HGradient(b, Alpha(side, 0.22f), Color.FromArgb(0, side));
			PxWarChrome.DrawBorder(b, Color.FromArgb(255, 40, 41, 48), 1);
			Fill(new Rectangle(b.X, b.Y, 4, b.Height), side);

			// Waving flag on a pole
			var flag = Flag(nation.Id);
			var fr = new Rectangle(b.X + 30, b.Y + 18, 108, 72);
			Fill(new Rectangle(fr.X - 7, b.Y + 10, 3, b.Height - 20), Color.FromArgb(255, 130, 132, 140));
			WidgetUtils.FillEllipseWithColor(new Rectangle(fr.X - 9, b.Y + 6, 7, 7), Gold);
			if (flag != null)
				PxFlagDraw.Waving(flag, fr, Game.RunTime / 1000f, 4f);

			var x = fr.Right + 26;
			var fade = Math.Clamp((Game.RunTime - nationTime) / 250f, 0, 1);
			PxWarChrome.DrawSpaced(header, $"{nation.Side.ToUpperInvariant()} ALLIANCE  ·  NATIONAL DOSSIER", x, b.Y + 14, 2, Alpha(SideText(nation.Side), fade));
			Text(displayLarge, nation.Name.ToUpperInvariant(), x, b.Y + 30, Alpha(Color.White, fade));
			var nameW = displayLarge.Measure(nation.Name.ToUpperInvariant()).X;
			if (!string.IsNullOrEmpty(nation.Motto))
				Text(display, "“" + nation.Motto + "”", x + nameW + 16, b.Y + 36, Alpha(Gold, fade));

			// Summary tiles on the right
			const int TileW = 92;
			var tilesX = b.Right - 16 - 3 * TileW - 2 * 8;
			var mine = data.Entries.Where(e => e.Nations.Contains(nation.Id)).ToList();
			var exclusive = mine.Count(e => e.Nations.Count == 1);
			var national = mine.Count(e => e.Nations.Count > 1 && e.Nations.Count < data.Nations.Count(n => n.Side == nation.Side));
			DrawTile(new Rectangle(tilesX, b.Y + 18, TileW, 74), mine.Count.ToString(CultureInfo.InvariantCulture), "ENTRIES", Ink);
			DrawTile(new Rectangle(tilesX + TileW + 8, b.Y + 18, TileW, 74), exclusive.ToString(CultureInfo.InvariantCulture), "EXCLUSIVE", Gold);
			DrawTile(new Rectangle(tilesX + 2 * (TileW + 8), b.Y + 18, TileW, 74), national.ToString(CultureInfo.InvariantCulture), "LIMITED", SideText(nation.Side));

			// Doctrine: specials, else the written nation lore
			var textW = tilesX - x - 20;
			var lines = new List<(string Text, Color Color)>();
			var specials = nation.Specials.Where(s => !s.Contains("coming soon", StringComparison.OrdinalIgnoreCase) &&
				!s.StartsWith("Full ", StringComparison.Ordinal));
			foreach (var s in specials)
				lines.Add(("+ " + s.ToUpperInvariant(), Gold));
			if (!string.IsNullOrEmpty(nation.Lore))
				foreach (var l in Wrap(nation.Lore, textW, small))
					lines.Add((l, Dim));

			var y = b.Y + 66;
			foreach (var (t, c) in lines.Take(2))
			{
				Text(lines.Count > 0 && c == Gold ? tiny : small, WidgetUtils.TruncateText(t, textW, small), x, y, Alpha(c, fade));
				y += 19;
			}
		}

		void DrawTile(Rectangle r, string value, string caption, Color color)
		{
			Fill(r, Color.FromArgb(120, 0, 0, 0));
			PxWarChrome.DrawBorder(r, Color.FromArgb(255, 44, 45, 52), 1);
			Fill(new Rectangle(r.X, r.Y, r.Width, 2), Alpha(color, 0.8f));
			var vw = displayLarge.Measure(value).X;
			Text(displayLarge, value, r.X + (r.Width - vw) / 2, r.Y + 12, color);
			var cw = PxWarChrome.SpacedWidth(tiny, caption, 1);
			PxWarChrome.DrawSpaced(tiny, caption, r.X + (r.Width - cw) / 2f, r.Bottom - 22, 1, Dim);
		}

		Rectangle TabRect(int c)
		{
			var w = (tabs.Width - (CategoryLabels.Length - 1) * 6) / CategoryLabels.Length;
			return new Rectangle(tabs.X + c * (w + 6), tabs.Y, w, tabs.Height);
		}

		void DrawTabs()
		{
			var mouse = Viewport.LastMousePos;
			for (var c = 0; c < CategoryLabels.Length; c++)
			{
				var r = TabRect(c);
				var count = Count(c);
				var sel = c == category;
				var hover = r.Contains(mouse) && count > 0;
				if (sel)
				{
					Gradient(r, Color.FromArgb(255, 70, 26, 22), Color.FromArgb(255, 34, 16, 15));
					Fill(new Rectangle(r.X, r.Bottom - 3, r.Width, 3), Accent);
					var glow = PxWarChrome.Pulse(2400);
					Fill(new Rectangle(r.X, r.Bottom, r.Width, 4), Color.FromArgb((int)(40 + 40 * glow), Accent));
				}
				else
					Gradient(r, Color.FromArgb(hover ? 255 : 230, hover ? 38 : 26, hover ? 39 : 27, hover ? 46 : 32), Color.FromArgb(230, 15, 16, 19));

				PxWarChrome.DrawBorder(r, sel ? Alpha(Accent, 0.6f) : Color.FromArgb(255, 40, 41, 48), 1);
				var text = CategoryLabels[c];
				var color = count == 0 ? Faint : sel ? Color.White : hover ? Ink : Dim;
				var tw = PxWarChrome.SpacedWidth(button, text, 1);
				var countText = count.ToString(CultureInfo.InvariantCulture);
				var cw = tiny.Measure(countText).X + 12;
				var tx = r.X + (r.Width - tw - cw - 8) / 2f;
				PxWarChrome.DrawSpaced(button, text, tx, r.Y + (r.Height - 20) / 2f, 1, color);
				var chip = new Rectangle((int)(tx + tw + 8), r.Y + (r.Height - 16) / 2, cw, 16);
				Fill(chip, sel ? Accent : Color.FromArgb(255, 48, 49, 56));
				Text(tiny, countText, chip.X + 6, chip.Y + 1, sel ? Color.White : Dim, false);
			}
		}

		Rectangle CardRect(int i)
		{
			var x = grid.X + i % cols * (cardW + Gap);
			var y = grid.Y + i / cols * (cardH + Gap) - gridScroll;
			return new Rectangle(x, y, cardW, cardH);
		}

		void DrawGrid()
		{
			var rows = (visible.Count + cols - 1) / cols;
			gridHeight = rows * (cardH + Gap) - Gap;
			gridScroll = Math.Clamp(gridScroll, 0, Math.Max(0, gridHeight - grid.Height));
			var mouse = Viewport.LastMousePos;
			var sideCount = data.Nations.Count(n => n.Side == nation.Side);

			Game.Renderer.EnableScissor(grid);
			for (var i = 0; i < visible.Count; i++)
			{
				var r = CardRect(i);
				if (r.Bottom < grid.Y || r.Y > grid.Bottom)
					continue;

				var e = visible[i];
				var sel = e == selected;
				var hover = r.Contains(mouse) && grid.Contains(mouse);
				Fill(r, Color.FromArgb(255, 20, 21, 25));

				var art = new Rectangle(r.X + 1, r.Y + 1, r.Width - 2, r.Height - 31);
				var (sprite, palette) = Cameo(e);
				if (sprite != null)
				{
					var scale = Math.Max(art.Width / sprite.Size.X, art.Height / sprite.Size.Y) * (hover ? 1.06f : 1f);
					var center = new float2(art.X + art.Width / 2f, art.Y + art.Height / 2f);
					Game.Renderer.EnableScissor(art);
					Game.Renderer.EnableAntialiasingFilter();
					var tint = sel || hover ? new float3(1, 1, 1) : new float3(0.82f, 0.82f, 0.86f);
					Game.Renderer.SpriteRenderer.DrawSprite(sprite, palette, center - 0.5f * scale * sprite.Size.XY, scale, tint, 1f);
					Game.Renderer.DisableAntialiasingFilter();
					Game.Renderer.DisableScissor();
				}

				Gradient(new Rectangle(art.X, art.Bottom - 24, art.Width, 24), Color.FromArgb(0, 0, 0, 0), Color.FromArgb(200, 0, 0, 0));

				// Name plate
				var plate = new Rectangle(r.X, r.Bottom - 30, r.Width, 30);
				Gradient(plate, Color.FromArgb(255, 30, 31, 37), Color.FromArgb(255, 18, 19, 23));
				var name = WidgetUtils.TruncateText(e.Name.ToUpperInvariant(), r.Width - 14, small);
				Text(small, name, plate.X + 7, plate.Y + 6, sel ? Color.White : Ink);

				// Cost tag and national badges
				var cost = Money(e.Cost);
				var cw = tiny.Measure(cost).X + 10;
				Fill(new Rectangle(art.Right - cw - 4, art.Y + 4, cw, 16), Color.FromArgb(190, 0, 0, 0));
				Text(tiny, cost, art.Right - cw + 1, art.Y + 5, Gold, false);

				if (e.Nations.Count == 1 || e.Nations.Count < sideCount)
				{
					var badge = e.Nations.Count == 1 ? "EXCLUSIVE" : "NATIONAL";
					var bw = tiny.Measure(badge).X + 12;
					var bc = e.Nations.Count == 1 ? Gold : SideColor(nation.Side);
					Fill(new Rectangle(art.X + 4, art.Y + 4, bw, 16), bc);
					Text(tiny, badge, art.X + 10, art.Y + 5, e.Nations.Count == 1 ? Color.FromArgb(30, 22, 4) : Color.White, false);
				}

				if (sel)
				{
					var pulse = PxWarChrome.Pulse(1600);
					PxWarChrome.DrawBorder(r.InflateBy(1, 1, 1, 1), Accent, 2);
					PxWarChrome.DrawBorder(r.InflateBy(3, 3, 3, 3), Color.FromArgb((int)(50 + 70 * pulse), Accent), 2);
					Fill(new Rectangle(plate.X, plate.Y, 3, plate.Height), Accent);
				}
				else
					PxWarChrome.DrawBorder(r, hover ? Color.FromArgb(255, 120, 122, 132) : Color.FromArgb(255, 42, 43, 50), 1);
			}

			Game.Renderer.DisableScissor();

			if (visible.Count == 0)
				Text(label, "NO ENTRIES FOR THIS NATION", grid.X + 10, grid.Y + 10, Faint);

			// Scrollbar
			if (gridHeight > grid.Height)
			{
				var track = new Rectangle(grid.Right + 6, grid.Y, 3, grid.Height);
				Fill(track, Color.FromArgb(255, 30, 31, 36));
				var h = Math.Max(30, grid.Height * grid.Height / gridHeight);
				var y = track.Y + (track.Height - h) * gridScroll / Math.Max(1, gridHeight - grid.Height);
				Fill(new Rectangle(track.X, y, 3, h), Accent);
			}
		}

		void DrawStage()
		{
			var s = stage;
			var side = nation != null ? SideColor(nation.Side) : Holo;
			Gradient(s, Color.FromArgb(255, 12, 18, 24), Color.FromArgb(255, 6, 8, 10));

			// The cameo, large: same picture as the card, fitted to the full stage height
			Game.Renderer.EnableScissor(s);
			if (selected != null)
			{
				var big = Picture(selected);
				if (big != null)
				{
					var (pos, size) = FullscreenImageWidget.ContainRect(big.Size.XY, s);
					WidgetUtils.DrawSprite(big, pos, size);
				}
				else
				{
					var (sprite, palette) = Cameo(selected);
					if (sprite != null)
					{
						var scale = Math.Min(s.Width / sprite.Size.X, s.Height / sprite.Size.Y);
						Game.Renderer.EnableAntialiasingFilter();
						Game.Renderer.SpriteRenderer.DrawSprite(sprite, palette,
							new float2(s.X + s.Width / 2f, s.Y + s.Height / 2f) - 0.5f * scale * sprite.Size.XY, scale, new float3(1, 1, 1), 1f);
						Game.Renderer.DisableAntialiasingFilter();
					}
				}

				// Darken the top and bottom so the title and footer stay readable over the picture
				Gradient(new Rectangle(s.X, s.Y, s.Width, 84), Color.FromArgb(210, 6, 8, 10), Color.FromArgb(0, 6, 8, 10));
				Gradient(new Rectangle(s.X, s.Bottom - 40, s.Width, 40), Color.FromArgb(0, 6, 8, 10), Color.FromArgb(200, 6, 8, 10));
			}

			// Hologram scan on selection, then slow scanlines
			var age = Game.RunTime - selectTime;
			if (age < 700)
			{
				var t = age / 700f;
				var y = s.Y + (int)(s.Height * t);
				Gradient(new Rectangle(s.X, y - 40, s.Width, 40), Color.FromArgb(0, Holo), Color.FromArgb((int)(70 * (1 - t)), Holo));
				Fill(new Rectangle(s.X, y, s.Width, 2), Color.FromArgb((int)(220 * (1 - t)), Holo));
			}

			for (var y = s.Y + (int)(Game.RunTime / 40 % 4); y < s.Bottom; y += 4)
				Fill(new Rectangle(s.X, y, s.Width, 1), Color.FromArgb(10, 0, 0, 0));

			Game.Renderer.DisableScissor();

			PxWarChrome.DrawBorder(s, Color.FromArgb(255, 38, 52, 62), 1);
			Brackets(s.InflateBy(-6, -6, -6, -6), 18, Color.FromArgb(160, Holo), 2);

			if (selected == null)
				return;

			// Title block
			var fade = Math.Clamp(age / 300f, 0, 1);
			var role = (selected.Role ?? "").ToUpperInvariant();
			var roleRight = s.Right - 22;

			var sideCount = data.Nations.Count(n => n.Side == nation.Side);
			if (selected.Nations.Count == 1 || selected.Nations.Count < sideCount)
			{
				var badge = selected.Nations.Count == 1 ? $"{nation.Name.ToUpperInvariant()} EXCLUSIVE" : "NATIONAL UNIT";
				var bw = PxWarChrome.SpacedWidth(tiny, badge, 1) + 16;
				var by = s.Y + 18;
				var bx = s.Right - 22 - bw;
				roleRight = bx - 14;
				Fill(new Rectangle(bx, by, bw, 18), selected.Nations.Count == 1 ? Gold : side);
				PxWarChrome.DrawSpaced(tiny, badge, bx + 8, by + 2, 1, selected.Nations.Count == 1 ? Color.FromArgb(30, 22, 4) : Color.White);
			}

			// A long role line stops before the badge (or the frame) with "..." instead of running under it
			if (PxWarChrome.SpacedWidth(header, role, 2) > roleRight - (s.X + 22))
			{
				while (role.Length > 1 && PxWarChrome.SpacedWidth(header, role + "...", 2) > roleRight - (s.X + 22))
					role = role[..^1];

				role = role.TrimEnd(' ', ',') + "...";
			}

			PxWarChrome.DrawSpaced(header, role, s.X + 22, s.Y + 18, 2, Alpha(Accent, fade));
			Text(displayLarge, selected.Name.ToUpperInvariant(), s.X + 20, s.Y + 34, Alpha(Color.White, fade));

			var tier = $"{PxCatalogueData.Categories[category].ToUpperInvariant()}  ·  {selected.Actor.Name.ToUpperInvariant()}";
			PxWarChrome.DrawSpaced(tiny, tier, s.X + 22, s.Bottom - 24, 1, Faint);
		}

		void DrawInfo()
		{
			if (selected == null)
				return;

			var e = selected;
			var a = Math.Clamp((Game.RunTime - selectTime) / 260f, 0, 1);
			var r = info;
			Game.Renderer.EnableScissor(r);
			var y = r.Y - infoScroll;
			var w = r.Width - 14;

			// Spec tiles
			var specs = new List<(string Value, string Caption, Color Color)>
			{
				(Money(e.Cost), "COST", Gold),
				(Seconds(e.BuildTicks), "BUILD TIME", Ink),
			};

			if (e.Power != 0)
				specs.Add(((e.Power > 0 ? "+" : "") + e.Power.ToString(CultureInfo.InvariantCulture), "POWER", e.Power > 0 ? PxWarChrome.Friendly : PxWarChrome.Hostile));
			if (e.HP > 0)
				specs.Add((e.HP.ToString("N0", CultureInfo.InvariantCulture), "HIT POINTS", Ink));
			if (e.Armor != null)
				specs.Add((ArmorName(e.Armor), "ARMOUR", Holo));

			var tw = (w - (specs.Count - 1) * 6) / specs.Count;
			for (var i = 0; i < specs.Count; i++)
			{
				var t = new Rectangle(r.X + i * (tw + 6), y, tw, 54);
				Gradient(t, Color.FromArgb(255, 26, 27, 32), Color.FromArgb(255, 16, 17, 20));
				PxWarChrome.DrawBorder(t, Color.FromArgb(255, 42, 43, 50), 1);
				Fill(new Rectangle(t.X, t.Y, 2, t.Height), Alpha(specs[i].Color, 0.8f));
				Text(display, WidgetUtils.TruncateText(specs[i].Value, t.Width - 18, display), t.X + 12, t.Y + 7, Alpha(specs[i].Color, a));
				PxWarChrome.DrawSpaced(tiny, specs[i].Caption, t.X + 12, t.Bottom - 19, 1, Faint);
			}

			y += 54 + 20;

			// Performance bars
			y = Section("PERFORMANCE", r.X, y, w);
			var cat = e.Category;
			var bars = new List<(string Label, float Value, float Max, string Text)>
			{
				("DURABILITY", e.HP, data.CategoryMax["hp-" + cat], e.HP.ToString("N0", CultureInfo.InvariantCulture)),
			};

			if (e.Dps > 0)
				bars.Add(("FIREPOWER", e.Dps, data.CategoryMax["dps-" + cat], Num(e.Dps) + " DPS"));
			if (e.Range > 0)
				bars.Add(("RANGE", e.Range, data.CategoryMax["range-" + cat], Num(e.Range) + " CELLS"));
			if (e.Speed > 0)
				bars.Add(("SPEED", e.Speed, data.CategoryMax["speed-" + cat], Num(e.Speed) + " CELLS/S"));
			if (e.Sight > 0)
				bars.Add(("VISION", e.Sight, data.CategoryMax["sight-" + cat], Num(e.Sight) + " CELLS"));

			foreach (var (name, value, max, text) in bars)
			{
				PxWarChrome.DrawSpaced(tiny, name, r.X, y + 2, 1, Dim);
				var bar = new Rectangle(r.X + 96, y + 3, w - 96 - 92, 10);
				PxWarChrome.DrawSegments(bar, a * Math.Min(1, value / Math.Max(0.001f, max)), Accent, 6);
				TextRight(tiny, text, r.X + w, y + 1, Ink);
				y += 22;
			}

			y += 14;

			// Damage grades
			if (e.Weapons.Any(wp => !wp.Support))
			{
				y = Section("EFFECTIVE AGAINST", r.X, y, w);
				var n = PxCatalogueData.Classes.Length;
				var gw = (w - (n - 1) * 6) / n;
				for (var i = 0; i < n; i++)
				{
					var g = new Rectangle(r.X + i * (gw + 6), y, gw, 62);
					var f = e.Effect[i];
					var letter = PxCatalogueData.GradeLetter(f);
					var gc = GradeColor(letter);
					Gradient(g, Color.FromArgb(255, 24, 25, 30), Color.FromArgb(255, 15, 16, 19));
					PxWarChrome.DrawBorder(g, Color.FromArgb(255, 40, 41, 48), 1);
					Fill(new Rectangle(g.X, g.Bottom - 3, (int)(g.Width * f * a), 3), gc);
					var lw = displayLarge.Measure(letter).X;
					Text(displayLarge, letter, g.X + (g.Width - lw) / 2, g.Y + 6, Alpha(gc, a));
					var cl = PxCatalogueData.Classes[i].Label;
					var lab = WidgetUtils.TruncateText(cl, g.Width - 6, tiny);
					Text(tiny, lab, g.X + (g.Width - tiny.Measure(lab).X) / 2, g.Bottom - 20, Dim, false);
				}

				y += 62 + 20;
			}

			// Weapons
			if (e.Weapons.Count > 0)
			{
				y = Section("ARMAMENT", r.X, y, w);
				foreach (var wp in e.Weapons)
				{
					var row = new Rectangle(r.X, y, w, 50);
					Gradient(row, Color.FromArgb(255, 24, 25, 30), Color.FromArgb(255, 16, 17, 20));
					Fill(new Rectangle(row.X, row.Y, 3, row.Height), wp.Support ? PxWarChrome.Friendly : Accent);
					Text(label, wp.Name.ToUpperInvariant(), row.X + 14, row.Y + 5, Ink);
					var kind = wp.Kind.ToUpperInvariant();
					var kx = row.X + 14 + label.Measure(wp.Name.ToUpperInvariant()).X + 10;
					var kw = tiny.Measure(kind).X + 10;
					Fill(new Rectangle(kx, row.Y + 8, kw, 15), Color.FromArgb(255, 52, 40, 38));
					Text(tiny, kind, kx + 5, row.Y + 9, VanguardText, false);

					var targets = new List<string>();
					if (wp.Ground)
						targets.Add("GROUND");
					if (wp.Air)
						targets.Add("AIR");
					if (wp.Naval)
						targets.Add("NAVAL");
					TextRight(tiny, string.Join("  ·  ", targets), row.Right - 10, row.Y + 9, Holo);

					var dmg = wp.Support ? "SUPPORT" : $"DMG {wp.Damage}" + (wp.Burst > 1 ? $" x{wp.Burst}" : "");
					var line = $"{dmg}     RANGE {Num(wp.Range)}" + (wp.MinRange > 0 ? $" (MIN {Num(wp.MinRange)})" : "") +
						$"     CYCLE {wp.Reload.ToString("0.0", CultureInfo.InvariantCulture)}s" + (wp.Support ? "" : $"     {Num(wp.Dps)} DPS");
					PxWarChrome.DrawSpaced(tiny, line, row.X + 14, row.Y + 30, 1, Dim);
					y += 56;
				}

				y += 14;
			}

			// Capabilities as chips
			if (e.Features.Count > 0)
			{
				y = Section("CAPABILITIES", r.X, y, w);
				var x = r.X;
				foreach (var f in e.Features)
				{
					var text = f.ToUpperInvariant();
					var cw = tiny.Measure(text).X + 26;
					if (x + cw > r.X + w)
					{
						x = r.X;
						y += 28;
					}

					var chip = new Rectangle(x, y, cw, 22);
					Fill(chip, Color.FromArgb(255, 22, 32, 38));
					PxWarChrome.DrawBorder(chip, Color.FromArgb(120, Holo), 1);
					WidgetUtils.FillEllipseWithColor(new Rectangle(chip.X + 8, chip.Y + 8, 6, 6), Holo);
					Text(tiny, text, chip.X + 19, chip.Y + 4, Ink, false);
					x += cw + 6;
				}

				y += 28 + 18;
			}

			// Dossier
			y = Section("FIELD DOSSIER", r.X, y, w);
			if (!string.IsNullOrEmpty(e.Lore))
			{
				foreach (var l in Wrap(e.Lore, w, body))
				{
					Text(body, l, r.X, y, Alpha(Ink, a), false);
					y += 22;
				}

				y += 8;
			}

			if (e.Notes != null)
			{
				foreach (var n in e.Notes.Skip(string.IsNullOrEmpty(e.Lore) ? 0 : 1))
				{
					var strong = n.StartsWith("Strong", StringComparison.Ordinal);
					var weak = n.StartsWith("Weak", StringComparison.Ordinal);
					var color = strong ? PxWarChrome.Friendly : weak ? VanguardText : Dim;
					foreach (var l in Wrap(n, w, small))
					{
						Text(small, l, r.X, y, color, false);
						y += 20;
					}
				}

				y += 8;
			}

			var requires = data.Requires(e, nation).ToList();
			if (requires.Count > 0)
			{
				PxWarChrome.DrawSpaced(tiny, "REQUIRES", r.X, y + 2, 1, Faint);
				foreach (var l in Wrap(string.Join("  ·  ", requires).ToUpperInvariant(), w - 90, small))
				{
					Text(small, l, r.X + 90, y, Ink, false);
					y += 20;
				}

				y += 8;
			}

			// Who fields it
			PxWarChrome.DrawSpaced(tiny, "FIELDED BY", r.X, y + 4, 1, Faint);
			var fx = r.X + 90;
			foreach (var n in data.Nations.Where(n => e.Nations.Contains(n.Id)))
			{
				if (fx + 30 > r.X + w)
				{
					fx = r.X + 90;
					y += 24;
				}

				var flag = Flag(n.Id);
				if (flag != null)
				{
					Fill(new Rectangle(fx - 1, y + 1, 30, 20), n == nation ? Gold : Color.FromArgb(255, 50, 51, 58));
					WidgetUtils.DrawSprite(flag, new float2(fx, y + 2), new float2(28, 18));
				}

				fx += 34;
			}

			y += 30;
			Game.Renderer.DisableScissor();

			infoHeight = y + infoScroll - r.Y;
			infoScroll = Math.Clamp(infoScroll, 0, Math.Max(0, infoHeight - r.Height));
			if (infoHeight > r.Height)
			{
				var track = new Rectangle(r.Right - 3, r.Y, 3, r.Height);
				Fill(track, Color.FromArgb(255, 30, 31, 36));
				var h = Math.Max(30, r.Height * r.Height / infoHeight);
				var ty = track.Y + (track.Height - h) * infoScroll / Math.Max(1, infoHeight - r.Height);
				Fill(new Rectangle(track.X, ty, 3, h), Accent);

				// Fade the cut-off edge
				Gradient(new Rectangle(r.X, r.Bottom - 24, r.Width - 6, 24), Color.FromArgb(0, 9, 10, 12), Color.FromArgb(230, 9, 10, 12));
			}
		}

		int Section(string text, int x, int y, int w)
		{
			Fill(new Rectangle(x, y + 4, 3, 11), Accent);
			PxWarChrome.DrawSpaced(header, text, x + 10, y, 2, Ink);
			var tw = PxWarChrome.SpacedWidth(header, text, 2);
			HGradient(new Rectangle(x + 22 + tw, y + 9, w - 22 - tw, 1), Color.FromArgb(90, 255, 106, 85), Color.FromArgb(0, 255, 106, 85));
			return y + 26;
		}

		static string ArmorName(string armor)
		{
			switch (armor)
			{
				case "None": return "INFANTRY";
				case "Wood": return "STRUCTURE";
				case "Concrete": return "FORTIFIED";
				default: return armor.ToUpperInvariant();
			}
		}

		static Color GradeColor(string g)
		{
			switch (g)
			{
				case "S": return Gold;
				case "A": return Color.FromArgb(132, 230, 110);
				case "B": return Color.FromArgb(120, 200, 255);
				case "C": return Color.FromArgb(220, 200, 160);
				case "D": return Color.FromArgb(200, 120, 110);
				default: return Faint;
			}
		}
	}
}
