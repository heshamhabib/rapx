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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>The "ARMAMENT" block of the production tooltip: one armoured card per weapon the unit carries (jets list
	/// every pylon family with its rounds), with its kind, range, damage, reload and what it is good against.</summary>
	public class PxWeaponLoadoutWidget : Widget
	{
		const int Header = 22;
		const int CardHeight = 56;
		const int CardGap = 5;
		const int TileSize = 44;
		const int StatIcon = 11;
		const int ClassIcon = 14;
		const int ClassCell = 38;

		static readonly Color Red = Color.FromArgb(232, 52, 40);
		static readonly Color Strong = Color.FromArgb(120, 214, 96);

		sealed class Row
		{
			public PxCatalogueData.Weapon Weapon;
			public int Rounds;
			public string Note;
		}

		readonly List<Row> rows = new();
		ActorInfo shown;

		public string NameFont = "Bold";
		public string StatFont = "Tiny";
		public string ValueFont = "PXDigitsSmall";
		public string TagFont = "PXSidebarSmall";

		/// <summary>Height the block needs for the actor shown (0 when it carries no weapon).</summary>
		public int ContentHeight => rows.Count == 0 ? 0 : Header + rows.Count * (CardHeight + CardGap);

		/// <summary>Width the widest card needs.</summary>
		public int ContentWidth { get; private set; }

		public void SetActor(ActorInfo actor, Ruleset rules)
		{
			if (actor == shown)
				return;

			shown = actor;
			rows.Clear();
			if (actor == null)
				return;

			var pools = actor.TraitInfos<AmmoPoolInfo>().ToList();
			foreach (var arm in actor.TraitInfos<ArmamentInfo>())
			{
				if (arm.WeaponInfo == null)
					continue;

				var w = PxCatalogueData.CreateWeapon(arm.Weapon, arm.WeaponInfo, rules);
				if (w.Damage <= 0 && !w.Support)
					continue;

				// Rounds: the ammo pools that feed this armament (a jet's pylons), summed per weapon
				var rounds = pools.Where(p => p.Armaments.Contains(arm.Name)).Sum(p => p.Ammo);
				var row = rows.FirstOrDefault(r => r.Weapon.Name == w.Name);
				if (row != null)
				{
					row.Rounds += rounds;
					continue;
				}

				rows.Add(new Row { Weapon = w, Rounds = rounds });
			}

			foreach (var i in actor.TraitInfos<PxInterceptorInfo>())
				rows.Add(new Row
				{
					Weapon = new PxCatalogueData.Weapon { Name = PxText.T("Missile interceptors"), Kind = PxText.N("Air defence"), Range = i.Range.Length / 1024f, Versus = new int[6] },
					Rounds = i.Rails,
					Note = PxText.F("Shoots down {0}", string.Join(", ", i.Chances.Where(c => c.Value > 0).OrderByDescending(c => c.Value)
						.Select(c => $"{PxText.T(c.Key).ToLowerInvariant()} {c.Value}%")))
				});

			foreach (var p in actor.TraitInfos<PxPointDefenseInfo>())
				rows.Add(new Row
				{
					Weapon = new PxCatalogueData.Weapon { Name = PxText.T("Close-in point defence"), Kind = PxText.N("CIWS"), Range = p.Range.Length / 1024f, Versus = new int[6] },
					Rounds = p.Mounts.Length,
					Note = PxText.F("Shreds missiles aimed at it, {0}% per burst", p.Chance)
				});

			var nameFont = Game.Renderer.Fonts[NameFont];
			var statFont = Game.Renderer.Fonts[StatFont];
			var valueFont = Game.Renderer.Fonts[ValueFont];
			var tagFont = Game.Renderer.Fonts[TagFont];
			const int Lead = 8 + TileSize + 9 + 8;
			ContentWidth = rows.Select(r =>
			{
				var head = nameFont.Measure(r.Weapon.Name).X + 16 + tagFont.Measure(PxText.T(r.Weapon.Kind).ToUpperInvariant()).X +
					(Rounds(r) is string b ? tagFont.Measure(b).X + 18 : 0);
				var note = r.Note ?? r.Weapon.Note ?? (r.Weapon.Support ? PxText.T("Support: no direct damage") : null);
				var third = note != null ? statFont.Measure(note).X : PxTooltipIcons.ClassIcons.Length * ClassCell;
				return Lead + Math.Max(head, Math.Max(StatsWidth(r, valueFont, statFont), third));
			}).DefaultIfEmpty(0).Max();
			ContentWidth = Math.Max(ContentWidth, 300);
		}

		static string Num(float f) => f.ToString(f >= 10 ? "0" : "0.#", CultureInfo.InvariantCulture);

		static string Rounds(Row r)
		{
			if (r.Rounds <= 0)
				return null;

			return r.Note != null && r.Weapon.Kind == "Air defence" ? PxText.F("{0} RAILS", r.Rounds) : r.Note != null ? PxText.F("{0} MOUNTS", r.Rounds) : $"×{r.Rounds}";
		}

		/// <summary>Stat cells on the card's second line: glyph, value, unit.</summary>
		static IEnumerable<(string Icon, string Value, string Unit)> StatCells(Row r)
		{
			var w = r.Weapon;
			yield return ("range", Num(w.Range), w.MinRange > 0 ? PxText.F("cells (min {0})", Num(w.MinRange)) : PxText.T("cells"));
			if (w.Damage > 0)
				yield return ("damage", w.Burst > 1 ? $"{w.Damage}×{w.Burst}" : w.Damage.ToString(CultureInfo.InvariantCulture), PxText.T("dmg"));
			if (w.Reload > 0)
				yield return ("reload", Num(w.Reload), "s");
			if (w.Dps > 0)
				yield return ("dps", Num(w.Dps), "/s");
		}

		static int StatsWidth(Row r, SpriteFont value, SpriteFont unit) =>
			StatCells(r).Sum(c => StatIcon + 3 + value.Measure(c.Value).X + 3 + unit.Measure(c.Unit).X + 12);

		/// <summary>0-4 meter segments for a damage percentage against one class.</summary>
		static int Segments(int v) => v <= 0 ? 0 : v < 40 ? 1 : v < 75 ? 2 : v < 100 ? 3 : 4;

		static Color StrengthColor(int segments) => segments >= 3 ? Strong : segments == 2 ? PxWarChrome.Amber : PxWarChrome.Stencil;

		public override void Draw()
		{
			if (rows.Count == 0)
				return;

			var rb = RenderBounds;
			var cr = Game.Renderer.RgbaColorRenderer;
			var nameFont = Game.Renderer.Fonts[NameFont];
			var statFont = Game.Renderer.Fonts[StatFont];
			var valueFont = Game.Renderer.Fonts[ValueFont];
			var tagFont = Game.Renderer.Fonts[TagFont];

			// Header: spaced stencil title, weapon count and a red rule that fades out
			var y = rb.Y;
			PxWarChrome.DrawSpaced(statFont, PxText.T("ARMAMENT"), rb.X, y + 3, 3, PxWarChrome.Stencil);
			var titleW = PxWarChrome.SpacedWidth(statFont, PxText.T("ARMAMENT"), 3);
			var count = rows.Count.ToString(CultureInfo.InvariantCulture);
			statFont.DrawTextWithShadow(count, new float2(rb.Right - statFont.Measure(count).X, y + 3), PxWarChrome.Amber, Color.Black, 1);
			var ruleY = y + 10;
			cr.FillRect(new float3(rb.X + titleW + 8, ruleY, 0), new float3(rb.Right - 18, ruleY, 0),
				new float3(rb.Right - 18, ruleY + 2, 0), new float3(rb.X + titleW + 8, ruleY + 2, 0), Red, Color.FromArgb(0, Red), Color.FromArgb(0, Red), Red);
			y += Header;

			var pulse = PxWarChrome.Pulse(2400);
			foreach (var r in rows)
			{
				var w = r.Weapon;
				var card = new Rectangle(rb.X, y, rb.Width, CardHeight);
				var accent = w.Support ? PxWarChrome.Friendly : r.Note != null ? Color.FromArgb(120, 170, 255) : w.Air && !w.Ground ? Color.FromArgb(185, 140, 255) : Red;

				// Card: dark cut-corner plate with a gradient, an accent spine and a faint top highlight
				PxWarChrome.FillPlate(card, 6, Color.FromArgb(230, 36, 32, 30), Color.FromArgb(240, 14, 12, 12));
				cr.FillRect(new float3(card.X, card.Y + 6, 0), new float3(card.X + 3, card.Y + 6, 0), new float3(card.X + 3, card.Bottom, 0), new float3(card.X, card.Bottom, 0), accent);
				cr.DrawLine(new float3(card.X + 6, card.Y, 0), new float3(card.Right, card.Y, 0), 1, Color.FromArgb(40, 255, 255, 255));

				// Weapon tile: recessed square lit from below in the accent colour, with the weapon's glyph
				var tile = new Rectangle(card.X + 8, card.Y + 6, TileSize, TileSize);
				PxWarChrome.FillPlate(tile, 4, Color.FromArgb(255, 22, 20, 19), Color.FromArgb(255, 8, 7, 7));
				cr.FillRect(new float3(tile.X, tile.Y + tile.Height / 2, 0), new float3(tile.Right, tile.Y + tile.Height / 2, 0),
					new float3(tile.Right, tile.Bottom, 0), new float3(tile.X, tile.Bottom, 0),
					Color.FromArgb(0, accent), Color.FromArgb(0, accent), Color.FromArgb((int)(70 + 40 * pulse), accent), Color.FromArgb((int)(70 + 40 * pulse), accent));
				PxWarChrome.DrawBorder(tile, Color.FromArgb(110, accent), 1);
				PxTooltipIcons.Draw(PxTooltipIcons.ForKind(w.Kind, w.Support), new float2(tile.X + 4, tile.Y + 4), TileSize - 8,
					PxWarChrome.Lerp(Color.White, accent, 0.25f));

				// Line 1: name, then the kind as a tag on the right (and the rounds badge before it)
				var x = tile.Right + 9;
				nameFont.DrawTextWithShadow(w.Name, new float2(x, card.Y + 3), Color.White, Color.Black, 1);
				var kind = PxText.T(w.Kind).ToUpperInvariant();
				var kindW = tagFont.Measure(kind).X;
				var right = card.Right - 8;
				tagFont.DrawTextWithShadow(kind, new float2(right - kindW, card.Y + 6), PxWarChrome.Lerp(accent, Color.White, 0.3f), Color.Black, 1);
				right -= kindW + 8;
				var rounds = Rounds(r);
				if (rounds != null)
				{
					var bw = tagFont.Measure(rounds).X + 10;
					var b = new Rectangle(right - bw, card.Y + 5, bw, 14);
					PxWarChrome.FillPlate(b, 3, PxWarChrome.Amber, PxWarChrome.Darken(PxWarChrome.Amber, 0.35f));
					tagFont.DrawText(rounds, new float2(b.X + 5, b.Y + 1), Color.FromArgb(30, 22, 8));
				}

				// Line 2: stat cells — glyph, bright value, dim unit
				var sy = card.Y + 22;
				if (r.Note != null)
				{
					PxTooltipIcons.Draw("range", new float2(x, sy + 1), StatIcon, PxWarChrome.Stencil);
					valueFont.DrawTextWithShadow(Num(w.Range), new float2(x + StatIcon + 3, sy), Color.White, Color.Black, 1);
				}
				else
				{
					var cx = x;
					foreach (var (icon, value, unit) in StatCells(r))
					{
						PxTooltipIcons.Draw(icon, new float2(cx, sy + 1), StatIcon, PxWarChrome.Stencil);
						cx += StatIcon + 3;
						valueFont.DrawTextWithShadow(value, new float2(cx, sy), Color.White, Color.Black, 1);
						cx += valueFont.Measure(value).X + 3;
						statFont.DrawTextWithShadow(unit, new float2(cx, sy + 1), Color.FromArgb(150, PxWarChrome.Stencil), Color.Black, 1);
						cx += statFont.Measure(unit).X + 12;
					}
				}

				// Line 3: what it is good against — class glyph and a 4-segment meter each; or the support note
				var ey = card.Y + 39;
				if (r.Note != null || w.Support)
				{
					var note = r.Note ?? w.Note ?? PxText.T("Support: no direct damage");
					statFont.DrawTextWithShadow(note, new float2(x, ey), PxWarChrome.Lerp(accent, Color.White, 0.35f), Color.Black, 1);
				}
				else
				{
					var cx = x;
					for (var i = 0; i < PxTooltipIcons.ClassIcons.Length; i++)
					{
						var v = w.Versus != null && i < w.Versus.Length ? w.Versus[i] : 0;
						var segs = Segments(v);
						var color = segs > 0 ? StrengthColor(segs) : Color.FromArgb(255, 90, 86, 80);
						PxTooltipIcons.Draw(PxTooltipIcons.ClassIcons[i], new float2(cx, ey - 1), ClassIcon, color, segs > 0 ? 1f : 0.55f);
						var mx = cx + ClassIcon + 2;
						for (var k = 0; k < 4; k++)
						{
							var seg = new Rectangle(mx + k * 4, ey + 9 - k * 2, 3, 3 + k * 2);
							var on = k < segs;
							cr.FillRect(new float3(seg.X, seg.Y, 0), new float3(seg.Right, seg.Y, 0), new float3(seg.Right, seg.Bottom, 0), new float3(seg.X, seg.Bottom, 0),
								on ? color : Color.FromArgb(55, 255, 255, 255));
						}

						cx += ClassCell;
					}
				}

				y += CardHeight + CardGap;
			}
		}
	}
}
