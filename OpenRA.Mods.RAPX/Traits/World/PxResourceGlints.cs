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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Living resources: short star-shaped glints pop on gold ore and gem crystals (each cell and glint on its own",
		"random rhythm, at a new spot every time; gem glints in gem colours), and gem fields glow softly in their colours.",
		"Purely cosmetic (local clock).")]
	public class PxResourceGlintsInfo : TraitInfo, Requires<IResourceLayerInfo>
	{
		[Desc("Resource types that glint.")]
		public readonly HashSet<string> GlintTypes = new() { "Ore", "Gems" };

		[Desc("Highest density of each resource type (MaxDensity in its ResourceLayer entry); glints and glow scale with it.")]
		public readonly Dictionary<string, int> MaxDensity = new() { { "Ore", 12 }, { "Gems", 3 } };

		[Desc("Glint colours per resource type (each glint picks one); types not listed use GlintColor.")]
		public readonly Dictionary<string, Color[]> GlintColors = new()
		{
			{
				"Gems", new[]
				{
					Color.FromArgb(150, 200, 255), Color.FromArgb(255, 140, 160), Color.FromArgb(150, 255, 190),
					Color.FromArgb(255, 230, 150), Color.FromArgb(215, 160, 255)
				}
			}
		};

		[Desc("Resource types that glow.")]
		public readonly HashSet<string> GlowTypes = new() { "Gems" };

		[Desc("Glints per cell at full density (fewer on thin ore).")]
		public readonly int GlintsPerCell = 3;

		[Desc("Seconds between two glints of the same slot (randomised between Min and Max).")]
		public readonly float MinPeriod = 1.8f;
		public readonly float MaxPeriod = 4.5f;

		[Desc("Seconds a glint lasts.")]
		public readonly float GlintLength = 0.45f;

		public readonly Color GlintColor = Color.FromArgb(255, 236, 170);
		public readonly float GlintSize = 0.8f;

		[Desc("Gem glow colours (each cell picks one).")]
		public readonly Color[] GlowColors = { Color.FromArgb(255, 70, 90), Color.FromArgb(90, 150, 255), Color.FromArgb(200, 90, 255) };
		public readonly float GlowSize = 1.3f;
		public readonly float GlowAlpha = 0.35f;

		public override object Create(ActorInitializer init) { return new PxResourceGlints(init.Self, this); }
	}

	public class PxResourceGlints : IRender
	{
		readonly PxResourceGlintsInfo info;
		readonly World world;
		readonly IResourceLayer layer;
		readonly PxParticles fx;

		public PxResourceGlints(Actor self, PxResourceGlintsInfo info)
		{
			this.info = info;
			world = self.World;
			layer = self.Trait<IResourceLayer>();
			fx = new PxParticles(world);
		}

		static uint Hash(int a, int b, int c)
		{
			var h = (uint)a * 0x8da6b343u ^ (uint)b * 0xd8163841u ^ (uint)c * 0xcb1ab31fu;
			h ^= h >> 15;
			h *= 0x2c1b3c6d;
			h ^= h >> 12;
			return h;
		}

		static float Unit(uint h) { return (h & 0xffffff) / (float)0xffffff; }

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			var t = Game.RunTime / 1000f;
			var shroud = world.RenderPlayer?.Shroud;
			var map = world.Map;
			var flare = fx.Sequence("flare");
			var glow = fx.Sequence("glow");

			foreach (var puv in wr.Viewport.VisibleCellsInsideBounds)
			{
				foreach (var uv in map.Unproject(puv))
				{
					var cell = uv.ToCPos(map);
					var r = layer.GetResource(cell);
					if (r.Type == null || r.Density <= 0)
						continue;

					if (shroud != null && !shroud.IsExplored(cell))
						continue;

					var centre = map.CenterOfCell(cell);
					var maxDensity = info.MaxDensity.TryGetValue(r.Type, out var md) ? md : 12;
					var fill = Math.Min(r.Density, maxDensity) / (float)maxDensity;
					info.GlintColors.TryGetValue(r.Type, out var colors);
					if (info.GlintTypes.Contains(r.Type))
					{
						var slots = Math.Max(1, (int)Math.Round(info.GlintsPerCell * fill));
						for (var k = 0; k < slots; k++)
						{
							var hs = Hash(cell.X, cell.Y, k);
							var period = info.MinPeriod + (info.MaxPeriod - info.MinPeriod) * Unit(hs);
							var local = t / period + Unit(hs * 7919u);
							var f = (local - MathF.Floor(local)) * period;
							if (f > info.GlintLength)
								continue;

							// New spot inside the cell every cycle
							var hp = Hash(cell.X, cell.Y, k * 977 + (int)MathF.Floor(local));
							var dx = (Unit(hp) - 0.5f) * 16;
							var dy = (Unit(hp >> 7) - 0.5f) * 14;
							var env = MathF.Sin(MathF.PI * f / info.GlintLength);
							env *= env;
							var pos = centre + PxParticles.ToWorld(dx, dy);
							var size = info.GlintSize * (0.6f + 0.4f * env) * (0.8f + 0.4f * Unit(hp >> 3));
							var spin = new WAngle((int)(Unit(hp >> 5) * 128) + (int)(f * 200));
							var col = colors != null && colors.Length > 0 ? colors[(hp >> 11) % (uint)colors.Length] : info.GlintColor;
							var c = 1 / 255f * new float3(col.R, col.G, col.B);

							// Four-point star: two crossed streaks plus a small core
							yield return new SpriteRenderable(flare.GetSprite(0), pos, WVec.Zero, 8, null, flare.Scale * size,
								env, c, TintModifiers.None, false, spin);
							yield return new SpriteRenderable(flare.GetSprite(0), pos, WVec.Zero, 8, null, flare.Scale * size * 0.7f,
								env, c, TintModifiers.None, false, spin + new WAngle(256));
							yield return new SpriteRenderable(glow.GetSprite(0), pos, WVec.Zero, 8, null, glow.Scale * size * 0.35f,
								env * 0.9f, c, TintModifiers.None, false, WAngle.Zero);
						}
					}

					if (info.GlowTypes.Contains(r.Type) && info.GlowColors.Length > 0)
					{
						var h = Hash(cell.X, cell.Y, 31);
						var col = info.GlowColors[h % (uint)info.GlowColors.Length];
						var a = info.GlowAlpha * (0.65f + 0.35f * MathF.Sin(t * 1.3f + Unit(h) * 6.28f));
						a *= 0.5f + 0.5f * fill;
						var c = 1 / 255f * new float3(col.R, col.G, col.B);
						yield return new SpriteRenderable(glow.GetSprite(0), centre, WVec.Zero, 4, null, glow.Scale * info.GlowSize,
							a, c, TintModifiers.None, false, WAngle.Zero);
					}
				}
			}
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr) { yield break; }
	}
}
