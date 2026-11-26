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
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World | SystemActors.EditorWorld)]
	[Desc("Animated lights on a painted backdrop (IDEA-28): additive glows from the map's lights file that hum, flicker,",
		"burn, blink or sweep over the static picture. The file (written by the map's build_backdrop.py) has one line per",
		"light: kind x y r g b size [aim_x aim_y], in cells of the playable area. Kinds: lamp (steady, a few faulty ones",
		"stutter), neon (steady with short flicker bursts), fire (restless orange), blink (red beacon), steady (slow",
		"breathing), search (a searchlight pool sweeping round its aim point, with a faint beam from the tower).",
		"Purely cosmetic (local clock). Maps without the file are unaffected.")]
	public class PxBackdropLightsInfo : TraitInfo, Requires<PxMapBackdropInfo>
	{
		[Desc("Lights file in the map package.")]
		public readonly string File = "lights.txt";

		[Desc("Glow opacity per kind.")]
		public readonly Dictionary<string, float> Alpha = new()
		{
			{ "lamp", 0.34f }, { "neon", 0.38f }, { "fire", 0.42f }, { "blink", 0.9f }, { "steady", 0.25f }, { "search", 0.28f }
		};

		[Desc("Glow size per kind (multiplied by the light's own size).")]
		public readonly Dictionary<string, float> Size = new()
		{
			{ "lamp", 1.35f }, { "neon", 1.2f }, { "fire", 1.0f }, { "blink", 0.5f }, { "steady", 1.2f }, { "search", 1.6f }
		};

		[Desc("Share of street lamps (percent) that are faulty and stutter.")]
		public readonly int FaultyLamps = 6;

		[Desc("Searchlight sweep: half width in cells and seconds per sweep.")]
		public readonly float SweepCells = 5f;
		public readonly float SweepSeconds = 7f;

		public override object Create(ActorInitializer init) { return new PxBackdropLights(init.World, this); }
	}

	public sealed class PxBackdropLights : IWorldLoaded, IRender
	{
		struct Light
		{
			public string Kind;
			public float X, Y, AimX, AimY, Size;
			public float3 Tint;
			public uint Seed;
			public bool HasAim;
		}

		readonly PxBackdropLightsInfo info;
		readonly World world;
		readonly List<Light> lights = new();
		PxParticles fx;
		bool active;

		public PxBackdropLights(World world, PxBackdropLightsInfo info)
		{
			this.info = info;
			this.world = world;
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			var map = w.Map;
			var backdrop = w.WorldActor.TraitOrDefault<PxMapBackdrop>();
			if (backdrop == null || !backdrop.Active || !map.Package.Contains(info.File))
				return;

			using (var reader = new StreamReader(map.Package.GetStream(info.File)))
			{
				string line;
				while ((line = reader.ReadLine()) != null)
				{
					line = line.Trim();
					if (line.Length == 0 || line[0] == '#')
						continue;

					var p = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
					if (p.Length < 7)
						continue;

					static float F(string s) => float.Parse(s, NumberStyles.Float, CultureInfo.InvariantCulture);
					var l = new Light
					{
						Kind = p[0],
						X = F(p[1]),
						Y = F(p[2]),
						Tint = new float3(F(p[3]), F(p[4]), F(p[5])),
						Size = F(p[6]),
						Seed = Hash(lights.Count, p[0].Length, 17)
					};

					if (p.Length >= 9)
					{
						l.AimX = F(p[7]);
						l.AimY = F(p[8]);
						l.HasAim = true;
					}

					lights.Add(l);
				}
			}

			fx = new PxParticles(w);
			active = lights.Count > 0;
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

		/// <summary>Smooth value noise in 0..1.</summary>
		static float Noise(float t, uint seed)
		{
			var i = (int)MathF.Floor(t);
			var f = t - i;
			f = f * f * (3 - 2 * f);
			return Unit(Hash(i, (int)seed, 3)) * (1 - f) + Unit(Hash(i + 1, (int)seed, 3)) * f;
		}

		/// <summary>Brightness (0..1+) and size factor of a light at time t.</summary>
		(float A, float S) Animate(in Light l, float t)
		{
			var phase = Unit(l.Seed) * 100f;
			switch (l.Kind)
			{
				case "neon":
				{
					// Steady, with a short burst of flicker every few seconds; some signs are worse than others
					var period = 3f + 9f * Unit(l.Seed >> 3);
					var local = (t + phase) / period;
					var f = (local - MathF.Floor(local)) * period;
					if (f < 0.6f && Unit(l.Seed >> 5) < 0.7f)
					{
						var blip = Hash((int)((t + phase) * 18), (int)l.Seed, 5);
						return (Unit(blip) < 0.5f ? 0.15f : 1f, 1f);
					}

					return (0.92f + 0.08f * MathF.Sin(t * 50f + phase), 1f);
				}

				case "fire":
					return (0.6f + 0.55f * Noise(t * 7f + phase, l.Seed), 0.85f + 0.3f * Noise(t * 5f + phase, l.Seed + 9));

				case "blink":
				{
					var local = (t * 0.7f + Unit(l.Seed)) % 1f;
					var on = local < 0.25f ? MathF.Sin(MathF.PI * local / 0.25f) : 0f;
					return (on, 1f);
				}

				case "steady":
					return (0.85f + 0.15f * MathF.Sin(t * 0.9f + phase), 1f);

				default:
				{
					// Street lamps: a slow warm breathing of the glow (each lamp on its own rhythm), with the halo
					// swelling a little as it brightens; a few faulty ones stutter now and then
					if (Hash((int)l.Seed, 1, 2) % 100 < (uint)info.FaultyLamps)
					{
						var dropout = Noise(t * 3f + phase, l.Seed) < 0.3f;
						var buzz = Unit(Hash((int)(t * 25f), (int)l.Seed, 7));
						return (dropout ? (buzz < 0.5f ? 0.1f : 0.6f) : 1f, 1f);
					}

					var breathe = 0.5f + 0.5f * MathF.Sin(t * (1.1f + 0.6f * Unit(l.Seed >> 4)) + phase);
					var shimmer = 0.04f * MathF.Sin(t * 13f + phase * 3f);
					return (0.68f + 0.32f * breathe + shimmer, 0.9f + 0.18f * breathe);
				}
			}
		}

		WPos ToWorld(float x, float y)
		{
			var b = world.Map.Bounds;
			return new WPos((int)((x + b.Left) * 1024), (int)((y + b.Top) * 1024), 0);
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			if (!active)
				yield break;

			var t = Game.RunTime / 1000f;
			var glow = fx.Sequence("glow");
			var flare = fx.Sequence("flare");
			var shroud = world.RenderPlayer?.Shroud;
			var view = wr.Viewport;
			var tl = view.TopLeft - new int2(256, 256);
			var br = view.BottomRight + new int2(256, 256);

			foreach (var l in lights)
			{
				info.Alpha.TryGetValue(l.Kind, out var alpha);
				if (alpha <= 0)
					alpha = 0.2f;

				var size = (info.Size.TryGetValue(l.Kind, out var s) ? s : 1f) * l.Size;
				var pos = ToWorld(l.X, l.Y);

				if (l.Kind == "search" && l.HasAim)
				{
					// Pool sweeping across the aim point, perpendicular to the tower's line of sight
					var dx = l.AimX - l.X;
					var dy = l.AimY - l.Y;
					var len = MathF.Max(0.01f, MathF.Sqrt(dx * dx + dy * dy));
					var sweep = MathF.Sin(t * 2 * MathF.PI / info.SweepSeconds + Unit(l.Seed) * 6.28f) * info.SweepCells;
					var ax = l.AimX - dy / len * sweep;
					var ay = l.AimY + dx / len * sweep;
					pos = ToWorld(ax, ay);
					var src = ToWorld(l.X, l.Y);
					var sp = wr.ScreenPxPosition(pos);
					if (sp.X < tl.X - 512 || sp.Y < tl.Y - 512 || sp.X > br.X + 512 || sp.Y > br.Y + 512)
						continue;

					var c = new float3(l.Tint.X, l.Tint.Y, l.Tint.Z);
					yield return new SpriteRenderable(glow.GetSprite(0), pos, WVec.Zero, 0, null, glow.Scale * size,
						alpha, c, TintModifiers.None, false, WAngle.Zero);
					yield return new SpriteRenderable(glow.GetSprite(0), pos, WVec.Zero, 0, null, glow.Scale * size * 0.5f,
						alpha * 0.8f, c, TintModifiers.None, false, WAngle.Zero);

					// Faint beam: a stretched flare from the tower to the pool
					var bx = ax - l.X;
					var by = ay - l.Y;
					var blen = MathF.Sqrt(bx * bx + by * by);
					var mid = ToWorld((l.X + ax) / 2, (l.Y + ay) / 2);
					var angle = new WAngle((int)(MathF.Atan2(by, bx) * 512 / MathF.PI));
					var beamScale = blen * 24f / flare.GetSprite(0).FrameSize.X;
					yield return new SpriteRenderable(flare.GetSprite(0), mid, WVec.Zero, 0, null, flare.Scale * beamScale,
						alpha * 0.35f, c, TintModifiers.None, false, angle);
					continue;
				}

				var spx = wr.ScreenPxPosition(pos);
				if (spx.X < tl.X || spx.Y < tl.Y || spx.X > br.X || spx.Y > br.Y)
					continue;

				if (shroud != null && !shroud.IsExplored(pos))
					continue;

				var (a, sf) = Animate(l, t + l.X * 0.01f);
				if (a <= 0.01f)
					continue;

				var tint = new float3(l.Tint.X, l.Tint.Y, l.Tint.Z);
				yield return new SpriteRenderable(glow.GetSprite(0), pos, WVec.Zero, 0, null, glow.Scale * size * sf,
					alpha * a, tint, TintModifiers.None, false, WAngle.Zero);

				// A small hot core makes neon, beacons and fires read as light sources
				if (l.Kind is "neon" or "blink" or "fire" or "lamp")
					yield return new SpriteRenderable(glow.GetSprite(0), pos, WVec.Zero, 0, null, glow.Scale * size * sf * 0.3f,
						MathF.Min(1f, alpha * a * 1.6f), tint, TintModifiers.None, false, WAngle.Zero);
			}
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr) { yield break; }
	}
}
