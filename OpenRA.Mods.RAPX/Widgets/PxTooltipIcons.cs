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
using OpenRA.FileFormats;
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>HD glyphs for the production tooltip: weapon kinds, target classes and stats
	/// (bits/hd/ui/tooltip-icons.png, artsrc/ui/make_tooltip_icons.py). White with a dark rim, tinted when drawn.</summary>
	public static class PxTooltipIcons
	{
		const string File = "ra|bits/hd/ui/tooltip-icons.png";
		const int Cell = 64;
		const int Columns = 8;

		// Same order as NAMES in artsrc/ui/make_tooltip_icons.py
		static readonly string[] Names =
		{
			"smallarms", "cannon", "artillery", "grenade", "missile", "bombs", "atomic", "beam",
			"tesla", "flame", "torpedo", "incendiary", "marker", "airdefence", "ciws", "support",
			"infantry", "light", "heavy", "building", "aircraft", "ship", "range", "damage",
			"reload", "strong", "weak", "rounds", "dps",
		};

		/// <summary>Target classes in PxCatalogueData.Classes order (INF, LIGHT, HEAVY, BLDG, AIR, SEA).</summary>
		public static readonly string[] ClassIcons = { "infantry", "light", "heavy", "building", "aircraft", "ship" };

		static readonly Dictionary<string, Sprite> Sprites = new();
		static ModData loadedFor;
		static Sheet sheet;

		static void Load()
		{
			if (loadedFor == Game.ModData && sheet != null)
				return;

			sheet?.Dispose();
			sheet = null;
			Sprites.Clear();
			loadedFor = Game.ModData;
			try
			{
				using (var stream = Game.ModData.DefaultFileSystem.Open(File))
				{
					var png = new Png(stream);
					sheet = new Sheet(SheetType.BGRA, new Size(png.Width, png.Height).NextPowerOf2());
					var all = new Sprite(sheet, new Rectangle(0, 0, png.Width, png.Height), TextureChannel.RGBA);
					OpenRA.Graphics.Util.FastCopyIntoSprite(all, png);
					sheet.ReleaseBuffer();
					sheet.GetTexture().ScaleFilter = TextureScaleFilter.Linear;
					for (var i = 0; i < Names.Length; i++)
						Sprites[Names[i]] = new Sprite(sheet, new Rectangle(i % Columns * Cell, i / Columns * Cell, Cell, Cell), TextureChannel.RGBA);
				}
			}
			catch (Exception ex)
			{
				Log.Write("debug", $"Tooltip icons failed: {ex.Message}");
			}
		}

		/// <summary>Glyph for a weapon kind (PxCatalogueData.Weapon.Kind).</summary>
		public static string ForKind(string kind, bool support)
		{
			switch (kind)
			{
				case "Small arms": return "smallarms";
				case "Cannon shell": return "cannon";
				case "Artillery shell": return "artillery";
				case "Grenade": return "grenade";
				case "Guided missile": return "missile";
				case "Bombs": return "bombs";
				case "Atomic bomb":
				case "Nuclear warhead": return "atomic";
				case "Energy beam":
				case "Beam": return "beam";
				case "Tesla arc": return "tesla";
				case "Flamethrower": return "flame";
				case "Torpedo": return "torpedo";
				case "Incendiary": return "incendiary";
				case "Target marker": return "marker";
				case "Air defence": return "airdefence";
				case "CIWS": return "ciws";
				default: return support ? "support" : "cannon";
			}
		}

		/// <summary>Glyph for a word in a unit description ("Strong vs Infantry and Tanks"), or null.</summary>
		public static string ForTerm(string term)
		{
			var t = term.ToLowerInvariant();
			if (t.Contains("infantry") || t.Contains("soldier"))
				return "infantry";
			if (t.Contains("aircraft") || t.Contains("air") || t.Contains("fighter") || t.Contains("plane") || t.Contains("helicopter") || t.Contains("drone"))
				return "aircraft";
			if (t.Contains("ship") || t.Contains("naval") || t.Contains("submarine") || t.Contains("boat"))
				return "ship";
			if (t.Contains("building") || t.Contains("structure") || t.Contains("defen") || t.Contains("base"))
				return "building";
			if (t.Contains("tank") || t.Contains("armo"))
				return "heavy";
			if (t.Contains("vehicle"))
				return "light";
			return null;
		}

		/// <summary>Draws a glyph size UI pixels square at pos, tinted.</summary>
		public static void Draw(string name, float2 pos, float size, Color tint, float alpha = 1f)
		{
			Load();
			if (name == null || !Sprites.TryGetValue(name, out var sprite))
				return;

			var t = new float3(tint.R / 255f, tint.G / 255f, tint.B / 255f);
			Game.Renderer.RgbaSpriteRenderer.DrawSprite(sprite,
				new float3(pos.X, pos.Y, 0), new float3(pos.X + size, pos.Y, 0),
				new float3(pos.X + size, pos.Y + size, 0), new float3(pos.X, pos.Y + size, 0), alpha * t, alpha);
		}
	}
}
