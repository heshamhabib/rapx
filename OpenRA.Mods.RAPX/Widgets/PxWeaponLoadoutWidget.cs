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
		const int CardHeight = 40;
		const int CardGap = 4;

		// Effect chips, in PxCatalogueData.Classes order
		static readonly string[] ChipLabels = { "INF", "LIGHT", "HEAVY", "BLDG", "AIR", "SEA" };
		static readonly Color Red = Color.FromArgb(232, 52, 40);

		sealed class Row
		{
			public PxCatalogueData.Weapon Weapon;
			public int Rounds;
			public string Note;
		}

		readonly List<Row> rows = new();
		ActorInfo shown;

		public string NameFont = "TinyBold";
		public string StatFont = "Tiny";

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
					Weapon = new PxCatalogueData.Weapon { Name = "Missile interceptors", Kind = "Air defence", Range = i.Range.Length / 1024f, Versus = new int[6] },
					Rounds = i.Rails,
					Note = "Shoots down " + string.Join(", ", i.Chances.Where(c => c.Value > 0).OrderByDescending(c => c.Value)
						.Select(c => $"{c.Key.ToLowerInvariant()} {c.Value}%"))
				});

			foreach (var p in actor.TraitInfos<PxPointDefenseInfo>())
				rows.Add(new Row
				{
					Weapon = new PxCatalogueData.Weapon { Name = "Close-in point defence", Kind = "CIWS", Range = p.Range.Length / 1024f, Versus = new int[6] },
					Rounds = p.Mounts.Length,
					Note = $"Shreds missiles aimed at it, {p.Chance}% per burst"
				});

			var nameFont = Game.Renderer.Fonts[NameFont];
			var statFont = Game.Renderer.Fonts[StatFont];
			ContentWidth = rows.Select(r => Math.Max(
				nameFont.Measure(r.Weapon.Name).X + 80,
				Math.Max(statFont.Measure(Stats(r)).X + 16, ChipsWidth(statFont) + 16))).DefaultIfEmpty(0).Max();
			ContentWidth = Math.Max(ContentWidth, 300);
		}

		static string Num(float f) => f.ToString(f >= 10 ? "0" : "0.#", CultureInfo.InvariantCulture);

		static string Stats(Row r)
		{
			var w = r.Weapon;
			if (r.Note != null)
				return $"RANGE {Num(w.Range)}  ·  {r.Note}";

			var parts = new List<string> { w.Kind.ToUpperInvariant(), $"RANGE {Num(w.Range)}" };
			if (w.Damage > 0)
				parts.Add(w.Burst > 1 ? $"DMG {w.Damage}×{w.Burst}" : $"DMG {w.Damage}");
			if (w.Reload > 0)
				parts.Add($"RELOAD {Num(w.Reload)}s");
			if (w.Air && !w.Ground)
				parts.Add("AIR ONLY");
			return string.Join("  ·  ", parts);
		}

		static int ChipsWidth(SpriteFont font) => ChipLabels.Sum(l => font.Measure(l).X + 12) + 4 * ChipLabels.Length;

		public override void Draw()
		{
			if (rows.Count == 0)
				return;

			var rb = RenderBounds;
			var cr = Game.Renderer.RgbaColorRenderer;
			var nameFont = Game.Renderer.Fonts[NameFont];
			var statFont = Game.Renderer.Fonts[StatFont];

			// Header: spaced stencil title, weapon count and a red rule that fades out
			var y = rb.Y;
			PxWarChrome.DrawSpaced(statFont, "ARMAMENT", rb.X, y + 3, 3, PxWarChrome.Stencil);
			var titleW = PxWarChrome.SpacedWidth(statFont, "ARMAMENT", 3);
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
				PxWarChrome.FillPlate(card, 6, Color.FromArgb(225, 34, 30, 28), Color.FromArgb(235, 14, 12, 12));
				cr.FillRect(new float3(card.X, card.Y + 6, 0), new float3(card.X + 3, card.Y + 6, 0), new float3(card.X + 3, card.Bottom, 0), new float3(card.X, card.Bottom, 0), accent);
				cr.FillRect(new float3(card.X + 3, card.Y + 6, 0), new float3(card.X + 14, card.Y + 6, 0), new float3(card.X + 14, card.Bottom, 0), new float3(card.X + 3, card.Bottom, 0),
					Color.FromArgb((int)(40 + 30 * pulse), accent), Color.FromArgb(0, accent), Color.FromArgb(0, accent), Color.FromArgb((int)(40 + 30 * pulse), accent));
				cr.DrawLine(new float3(card.X + 6, card.Y, 0), new float3(card.Right, card.Y, 0), 1, Color.FromArgb(40, 255, 255, 255));

				// Line 1: name, rounds badge
				var x = card.X + 10;
				nameFont.DrawTextWithShadow(w.Name, new float2(x, card.Y + 3), Color.White, Color.Black, 1);
				if (r.Rounds > 0)
				{
					var badge = r.Note != null && w.Kind == "Air defence" ? $"{r.Rounds} RAILS" : r.Note != null ? $"{r.Rounds} MOUNTS" : $"×{r.Rounds}";
					var bw = statFont.Measure(badge).X + 10;
					var b = new Rectangle(card.Right - bw - 6, card.Y + 4, bw, 14);
					PxWarChrome.FillPlate(b, 3, PxWarChrome.Amber, PxWarChrome.Darken(PxWarChrome.Amber, 0.35f));
					statFont.DrawText(badge, new float2(b.X + 5, b.Y), Color.FromArgb(30, 22, 8));
				}

				// Line 2: stats; line 3 (right): effect chips lit by how hard it hits each class
				statFont.DrawTextWithShadow(Stats(r), new float2(x, card.Y + 15), PxWarChrome.Stencil, Color.Black, 1);
				if (r.Note == null && !w.Support)
				{
					var cx = x;
					for (var i = 0; i < ChipLabels.Length; i++)
					{
						var v = w.Versus != null && i < w.Versus.Length ? w.Versus[i] : 0;
						var label = ChipLabels[i];
						var cw = statFont.Measure(label).X + 8;
						var chip = new Rectangle(cx, card.Y + 27, cw, 11);
						if (v <= 0)
							PxWarChrome.DrawBorder(chip, Color.FromArgb(50, 255, 255, 255), 1);
						else
						{
							var strength = Math.Min(1f, v / 100f);
							var fill = v >= 75 ? accent : v >= 40 ? PxWarChrome.Amber : PxWarChrome.Darken(PxWarChrome.Stencil, 0.4f);
							cr.FillRect(new float3(chip.X, chip.Y, 0), new float3(chip.Right, chip.Y, 0), new float3(chip.Right, chip.Bottom, 0), new float3(chip.X, chip.Bottom, 0),
								Color.FromArgb((int)(90 + 140 * strength), fill));
						}

						statFont.DrawText(label, new float2(chip.X + 4, chip.Y - 2), v > 0 ? Color.White : Color.FromArgb(90, 255, 255, 255));
						cx += cw + 4;
					}
				}

				y += CardHeight + CardGap;
			}
		}
	}
}
