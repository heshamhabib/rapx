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
using OpenRA.Effects;
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Warheads;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Warheads
{
	/// <summary>The look of a PxExplosion; each matches a kind of warhead.</summary>
	public enum PxExplosionStyle
	{
		/// <summary>Flash, rolling fireball, sparks, debris and a smoke column.</summary>
		Standard,

		/// <summary>Guided warhead: a sharp, tight flash, lots of sparks, little smoke.</summary>
		Precision,

		/// <summary>Big rocket or ballistic warhead: a wide dust ring, heavy debris and a tall smoke column.</summary>
		Heavy,

		/// <summary>Fuel-air blast: a pale pressure flash, two shock rings, a huge rising fireball and a dark mushroom.</summary>
		Thermobaric,

		/// <summary>Anti-ship hit: a fireball on the ship, burning fuel and thick black smoke, spray around it.</summary>
		Naval,

		/// <summary>Cluster bomblet: a small sharp pop with sparks and a puff of grey smoke.</summary>
		Bomblet,

		/// <summary>Proximity-fused fragmentation warhead: a sharp flash, a sphere of fragment streaks and a black flak
		/// puff that hangs in the air.</summary>
		Fragmentation,

		/// <summary>Hit-to-kill interceptor: a blinding blue-white flash, a shock ring, a shower of white-hot sparks and
		/// tumbling wreckage, a cloud of white vapour; no fireball.</summary>
		HitToKill,

		/// <summary>Blast-fragmentation warhead: a big orange fireball inside a ring of black smoke, burning debris
		/// falling out of it trailing smoke.</summary>
		Fireball,
	}

	[Desc("High-definition explosion (pxfx particles, cosmetic only): a detonation glare that lights the ground, a shock",
		"front and a dust wave racing out over it, a rolling fireball that cools into a lit column of smoke drifting",
		"with the wind, dirt and burning debris trailing smoke, embers, and now and then a second cook-off. Big blasts",
		"shake the screen and bend the picture (PxBlastWaves); soldiers they kill are thrown (PxBlastRegistry,",
		"WithPxBlastDeath). Air bursts skip the ground effects. Does nothing on open water (pair it with the classic",
		"splash warhead), but does explode on ships. Plays ImpactSounds like CreateEffect.")]
	public class PxExplosionWarhead : Warhead
	{
		[Desc("Overall size: 1 = a rocket hit, 0.6 = a grenade, 2 = a heavy shell or V2.")]
		public readonly float Size = 1f;

		[Desc("Amount of smoke, as a multiple of the default.")]
		public readonly float Smoke = 1f;

		[Desc("Look of the blast: Standard, Precision, Heavy, Thermobaric, Naval, Bomblet, Fragmentation, HitToKill or Fireball.")]
		public readonly PxExplosionStyle Style = PxExplosionStyle.Standard;

		[Desc("Fire colour (tint of the flames and fireball).")]
		public readonly Color FireColor = Color.FromArgb(255, 255, 209, 140);

		[Desc("Smoke colour.")]
		public readonly Color SmokeColor = Color.FromArgb(255, 204, 199, 191);

		[Desc("Only play when an actor with one of these target types is at the impact (e.g. Ship for a hit on a ship).",
			"Empty = always.")]
		public readonly BitSet<TargetableType> OnlyOn = default;

		[Desc("Do not play when an actor with one of these target types is at the impact.")]
		public readonly BitSet<TargetableType> NotOn = default;

		[Desc("Leave a short-lived scorch mark on the ground.")]
		public readonly bool Scorch = true;

		[Desc("Chance (0-1) that a ground blast keeps burning for a few seconds afterwards (Standard, Heavy, Thermobaric,",
			"Naval and Fireball only, Size 0.9 or more).")]
		public readonly float LingerChance = 0.45f;

		[Desc("Shake the screen, scaled by Size and the distance to the camera (Size 0.9 or more).")]
		public readonly bool Shake = true;

		[Desc("Register the blast with PxBlastRegistry: soldiers it kills are thrown, units around it are shoved.")]
		public readonly bool Throw = true;

		[Desc("Draw the pressure wave over the picture (PxBlastWaves).")]
		public readonly bool Wave = true;

		[Desc("Sounds to play on impact.")]
		public readonly string[] ImpactSounds = Array.Empty<string>();

		public override void DoImpact(in Target target, WarheadArgs args)
		{
			if (target.Type == TargetType.Invalid)
				return;

			var world = args.SourceActor.World;
			var pos = target.CenterPosition;
			var air = world.Map.DistanceAboveTerrain(pos) > AirThreshold;
			if (!air)
			{
				var cell = world.Map.CellContaining(pos);

				// On water only when something is hit there (a ship); plain water keeps the classic splash
				if (!world.Map.Contains(cell) ||
					(world.Map.GetTerrainInfo(cell).TargetTypes.Contains("Water") && !world.FindActorsOnCircle(pos, new WDist(256)).Any()))
					return;
			}

			if (!OnlyOn.IsEmpty || !NotOn.IsEmpty)
			{
				var types = world.FindActorsOnCircle(pos, new WDist(341))
					.SelectMany(a => a.GetEnabledTargetTypes()).ToHashSet();
				if (!OnlyOn.IsEmpty && !types.Any(t => OnlyOn.Contains(t)))
					return;

				if (types.Any(t => NotOn.Contains(t)))
					return;
			}

			if (Throw && !air)
				world.WorldActor.TraitOrDefault<PxBlastRegistry>()?.Register(world, pos, Size);

			if (Shake && Size >= 0.9f)
			{
				var shaker = world.WorldActor.TraitOrDefault<ScreenShaker>();
				if (shaker != null)
				{
					// The shaker's own falloff is steep (1/distance squared, capped at 10 px): small blasts get a fraction of it
					var intensity = Size > 2f ? (int)(Size * Size / 2) : 1;
					var multiplier = Size > 2f ? 1f : Math.Min(1f, 0.3f + 0.64f * (Size - 0.9f));
					shaker.AddEffect((int)(5 + 5 * Size), pos, intensity, new float2(multiplier, multiplier));
				}
			}

			world.AddFrameEndTask(w => w.Add(new PxExplosionEffect(w, pos, this, air)));

			var sound = ImpactSounds.RandomOrDefault(world.LocalRandom);
			if (sound != null)
				Game.Sound.Play(SoundType.World, sound, pos);
		}
	}

	public class PxExplosionEffect : IEffect
	{
		const int ScorchZ = -2048;

		/// <summary>How much of each ingredient a style gets, as multiples of the Standard blast.</summary>
		readonly struct Recipe
		{
			public readonly float Flash, Light, Shock, Dust, Fire, FireSize, Rise, Smoke, Column, Soot, Debris, Burning, Sparks, Embers, Pops, Wave;

			public Recipe(float flash, float light, float shock, float dust, float fire, float fireSize, float rise, float smoke, float column,
				float soot, float debris, float burning, float sparks, float embers, float pops, float wave)
			{
				Flash = flash;
				Light = light;
				Shock = shock;
				Dust = dust;
				Fire = fire;
				FireSize = fireSize;
				Rise = rise;
				Smoke = smoke;
				Column = column;
				Soot = soot;
				Debris = debris;
				Burning = burning;
				Sparks = sparks;
				Embers = embers;
				Pops = pops;
				Wave = wave;
			}
		}

		static readonly Dictionary<PxExplosionStyle, Recipe> Recipes = new()
		{
			//                                       flash light shock dust  fire  fsize rise  smoke col   soot  debris burn  sparks ember pops  wave
			{ PxExplosionStyle.Standard, new Recipe(1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 0.9f, 1.0f, 1.0f, 0.6f, 0.5f, 1.0f, 0.3f, 1.0f, 1.0f, 0.25f, 1.0f) },
			{ PxExplosionStyle.Precision, new Recipe(1.3f, 0.8f, 0.8f, 0.5f, 0.6f, 0.8f, 0.8f, 0.5f, 0.0f, 0.3f, 0.5f, 0.2f, 2.0f, 1.2f, 0.0f, 0.8f) },
			{ PxExplosionStyle.Heavy, new Recipe(1.2f, 1.3f, 1.3f, 1.6f, 1.3f, 1.1f, 1.1f, 1.4f, 1.3f, 0.6f, 1.6f, 0.35f, 1.0f, 1.3f, 0.4f, 1.3f) },
			{ PxExplosionStyle.Thermobaric, new Recipe(1.6f, 1.8f, 1.6f, 1.4f, 1.8f, 1.35f, 1.4f, 1.4f, 1.4f, 0.75f, 0.6f, 0.2f, 0.6f, 1.0f, 0.2f, 1.7f) },
			{ PxExplosionStyle.Naval, new Recipe(1.0f, 0.8f, 0.0f, 0.0f, 1.2f, 1.0f, 1.0f, 1.5f, 1.2f, 0.9f, 0.7f, 0.5f, 1.0f, 1.2f, 0.4f, 0.8f) },
			{ PxExplosionStyle.Bomblet, new Recipe(0.7f, 0.5f, 0.5f, 0.6f, 0.5f, 0.7f, 0.6f, 0.5f, 0.0f, 0.4f, 0.5f, 0.1f, 1.0f, 0.6f, 0.0f, 0.5f) },
			{ PxExplosionStyle.Fragmentation, new Recipe(1.0f, 0.3f, 0.6f, 0.4f, 0.4f, 0.6f, 0.3f, 1.2f, 0.0f, 1.0f, 0.3f, 0.0f, 3.0f, 1.2f, 0.0f, 0.6f) },
			{ PxExplosionStyle.HitToKill, new Recipe(1.6f, 0.3f, 0.6f, 0.3f, 0.25f, 0.6f, 0.3f, 0.9f, 0.0f, 0.0f, 1.2f, 0.6f, 3.0f, 0.8f, 0.0f, 0.7f) },
			{ PxExplosionStyle.Fireball, new Recipe(1.2f, 1.4f, 1.1f, 1.2f, 1.7f, 1.25f, 0.9f, 1.3f, 0.9f, 0.85f, 1.2f, 0.5f, 1.0f, 1.4f, 0.5f, 1.3f) },
		};

		readonly World world;
		readonly WPos pos;
		readonly WPos ground;
		readonly PxExplosionWarhead info;
		readonly bool air;
		readonly PxParticles particles;
		readonly ISpriteSequence scorch;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly PxWeatherManager weather;
		readonly PxBlastWaves waves;
		readonly float height;
		readonly float3 dust;
		readonly float3 fire;
		readonly float3 smoke;
		readonly Recipe recipe;

		// A fire left burning at the impact (LingerChance): how long, and when the next flames are due
		float burn;
		float burnLeft;
		float nextFlame;
		float time;
		long lastTime = -1;
		bool started;

		public PxExplosionEffect(World world, WPos pos, PxExplosionWarhead info, bool air)
		{
			this.world = world;
			this.pos = pos;
			this.info = info;
			this.air = air;
			var above = world.Map.DistanceAboveTerrain(pos).Length;
			ground = pos - new WVec(0, 0, above);
			height = above * 24f / 1024f;
			particles = new PxParticles(world) { Max = (int)(500 + 350 * info.Size) };
			scorch = particles.Sequence("scorch");
			weather = world.WorldActor.TraitOrDefault<PxWeatherManager>();
			if (weather != null && !weather.Enabled)
				weather = null;

			waves = world.WorldActor.TraitOrDefault<PxBlastWaves>();
			recipe = Recipes[info.Style];

			// Dust takes the colour of the ground; smoke goes from the warhead's colour towards soot
			dust = world.Map.Tileset switch
			{
				"SNOW" => new float3(0.9f, 0.92f, 0.95f),
				"DESERT" => new float3(0.76f, 0.66f, 0.48f),
				_ => new float3(0.52f, 0.44f, 0.34f),
			};

			var white = new float3(1, 1, 1);
			fire = Lerp(white, Tint(info.FireColor), 0.4f);
			smoke = Lerp(Tint(info.SmokeColor), new float3(0.1f, 0.1f, 0.1f), recipe.Soot);
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		static float3 Shade(float3 c, float f) { return new float3(c.X * f, c.Y * f, c.Z * f); }

		static float3 Lerp(float3 a, float3 b, float t) { return new float3(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t, a.Z + (b.Z - a.Z) * t); }

		static float3 Tint(Color c) { return new float3(c.R / 255f, c.G / 255f, c.B / 255f); }

		/// <summary>A particle at distance r from the centre in direction a, flying outwards along it at speed s.
		/// Delay holds it back that many ticks.</summary>
		PxParticle Make(PxParticleKind kind, float a, float r, float z, float size, float grow, float life, float alpha,
			float s, float vz, float gravity, float drag, float3 tint, float delay = 0)
		{
			return new PxParticle
			{
				Kind = kind,
				X = MathF.Cos(a) * r,
				Y = MathF.Sin(a) * r * 0.6f,
				Z = z,
				VX = MathF.Cos(a) * s,
				VY = MathF.Sin(a) * s * 0.6f,
				VZ = vz,
				Gravity = gravity,
				Drag = drag,
				Age = -delay,
				Life = life * Rand(0.75f, 1.25f),
				Size = size * Rand(0.8f, 1.2f),
				Grow = grow,
				Alpha = alpha,
				Tint = tint,
				Frame = random.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = Rand(-3, 3),
				Angle = random.Next(1024),
			};
		}

		/// <summary>A particle somewhere within spread of the centre, flying outwards.</summary>
		PxParticle Make(PxParticleKind kind, float spread, float z, float size, float grow, float life, float alpha,
			float speed, float vz, float gravity, float drag, float3 tint, float delay = 0)
		{
			return Make(kind, Rand(0, MathF.PI * 2), Rand(0, spread), z, size, grow, life, alpha, Rand(0.4f, 1f) * speed, vz, gravity, drag, tint, delay);
		}

		void Add(PxParticleKind kind, float spread, float z, float size, float grow, float life, float alpha,
			float speed, float vz, float gravity, float drag, float3 tint, float delay = 0)
		{
			particles.Add(Make(kind, spread, z, size, grow, life, alpha, speed, vz, gravity, drag, tint, delay));
		}

		float3 SmokeShade() { return Shade(smoke, Rand(0.75f, 1.15f)); }

		/// <summary>Smoke lit orange by the fire inside it, cooling to its own grey.</summary>
		float3 FireLit() { return new float3(Rand(0.85f, 1f), Rand(0.45f, 0.6f), Rand(0.18f, 0.3f)); }

		void Start()
		{
			started = true;
			var k = info.Size;
			var r = recipe;
			var s = info.Smoke;
			var white = new float3(1, 1, 1);

			waves?.Add(ground, k * r.Wave, air);
			if (weather != null)
			{
				var f = weather.Frame();
				particles.Wind = f.WindDir * (0.06f + 0.55f * f.Wind);
			}
			else
				particles.Wind = new float2(0.08f, -0.02f);

			// --- Detonation: glare, bloom and the light it throws on the ground ---
			var flashTint = info.Style == PxExplosionStyle.HitToKill ? new float3(0.88f, 0.94f, 1f) : white;
			if (r.Flash > 0)
			{
				particles.Add(Make(PxParticleKind.Flash, 0, 0, height, (1.0f + 0.9f * k) * r.Flash, -0.25f, 3.5f, 1f, 0, 0, 0, 0, flashTint));
				particles.Add(Make(PxParticleKind.Flash, 0, 0, height, (0.6f + 0.5f * k) * r.Flash, 0.6f, 6f, 0.7f, 0, 0, 0, 0, flashTint));
				particles.Add(Make(PxParticleKind.Glow, 0, 0, height, 1.4f * k * r.Flash, 0.6f, 8, 1f, 0, 0, 0, 0,
					info.Style == PxExplosionStyle.HitToKill ? flashTint : new float3(1f, 0.85f, 0.6f)));
			}

			if (!air && r.Light > 0)
				particles.Add(Make(PxParticleKind.Light, 0, 0, 0, (1.2f + 1.2f * k) * r.Light, 0.15f, 7 + 2 * k, 0.9f, 0, 0, 0, 0, new float3(1f, 0.85f, 0.6f)));

			// --- Ground waves: the shock front, then the dust it lifts ---
			if (!air)
			{
				if (r.Shock > 0)
				{
					particles.Add(Make(PxParticleKind.Shock, 0, 0, 0, (0.9f + 1.0f * k) * r.Shock, 0, 9 + 3 * k, 0.85f, 0, 0, 0, 0, white));
					if (info.Style == PxExplosionStyle.Thermobaric)
						particles.Add(Make(PxParticleKind.Shock, 0, 0, 0, (1.1f + 1.3f * k) * r.Shock, 0, 16 + 5 * k, 0.6f, 0, 0, 0, 0, new float3(1f, 0.92f, 0.8f), 4));
				}

				if (r.Dust > 0)
				{
					particles.Add(Make(PxParticleKind.Dust, 0, 0, 0, (0.6f + 0.7f * k) * r.Dust, 0.25f, 20 + 10 * k, 0.9f, 0, 0, 0, 0, dust));
					particles.Add(Make(PxParticleKind.Dust, 0, 0, 0, (0.45f + 0.55f * k) * r.Dust, 0.35f, 24 + 10 * k, 0.6f, 0, 0, 0, 0, Shade(dust, 0.9f), 2));

					// Dust thrown out low along the ground
					for (var i = 0; i < (int)(8 * k * r.Dust) + 2; i++)
					{
						var p = Make(PxParticleKind.Smoke2, 3 * k, 0.5f, Rand(0.35f, 0.5f) * k, 2.2f, Rand(35, 60), 0.7f,
							1.8f * k, Rand(0.2f, 0.5f), 0, 0.08f, Shade(dust, Rand(0.85f, 1.1f)), Rand(0, 2));
						p.Wind = 1;
						particles.Add(p);
					}
				}
			}

			// --- The fireball: lumps of flame swelling out of the centre, flame tongues around them ---
			var fireSpread = (air ? 1.5f : 1.2f) * k;
			var fireCount = (int)((5 + 7 * k) * r.Fire);
			for (var i = 0; i < fireCount; i++)
			{
				var p = Make(PxParticleKind.Fire2, fireSpread, height + 0.5f + Rand(0, 2 * k), Rand(0.55f, 0.85f) * k * r.FireSize, 0.9f,
					Rand(16, 26), 1f, Rand(0.3f, 1.1f) * k, Rand(0.5f, 1.3f) * r.Rise, air ? 0.01f : 0, 0.1f, Shade(fire, Rand(0.92f, 1.05f)), Rand(0, 2.5f));
				p.Frame = random.Next(2) * 16;
				p.Spin = Rand(-1.5f, 1.5f);
				particles.Add(p);
			}

			for (var i = 0; i < (int)((4 + 5 * k) * r.Fire); i++)
				Add(PxParticleKind.Flame, 2 * k, height + Rand(0, 2 * k), Rand(0.4f, 0.7f) * k * r.FireSize, 0.4f, Rand(10, 16), 1f,
					1.4f * k, Rand(0.3f, 1.0f) * r.Rise, 0, 0.12f, Tint(info.FireColor), Rand(0, 1));

			// --- Smoke: lit by the fire while it boils out, then its own colour as it rises ---
			var soot = Shade(smoke, 0.8f);
			for (var i = 0; i < (int)((8 + 8 * k) * s * r.Smoke); i++)
			{
				var p = Make(PxParticleKind.Smoke2, 1.5f * k, height + Rand(1, 4 * k), Rand(0.5f, 0.8f) * k, 2.6f, Rand(60, 110) * (1 + 0.2f * k), 0.9f,
					0.7f * k, Rand(0.3f, 0.7f) * r.Rise, air ? 0.004f : 0, 0.05f, Shade(FireLit(), Rand(0.8f, 1.1f)), Rand(1, 6));
				p.FadeTint = true;
				p.TintEnd = SmokeShade();
				p.Wind = 1;
				particles.Add(p);
			}

			if (!air && r.Column > 0)
			{
				for (var i = 0; i < (int)((10 + 10 * k) * s * r.Column); i++)
				{
					var p = Make(PxParticleKind.Smoke2, 1.0f * k, Rand(2 * k, 6 * k), Rand(0.55f, 0.85f) * k, 3.0f, Rand(100, 160) * (1 + 0.3f * k), 0.95f,
						0.25f * k, Rand(0.9f, 1.7f) * r.Column, 0, 0.025f, Shade(FireLit(), 0.6f), Rand(5, 16));
					p.FadeTint = true;
					p.TintEnd = Shade(soot, Rand(0.8f, 1.1f));
					p.Wind = 0.8f;
					particles.Add(p);
				}

				// Mushroom cap spreading at the top of big columns
				if (k >= 1.2f)
					for (var i = 0; i < (int)(6 * k * s); i++)
					{
						var p = Make(PxParticleKind.Smoke2, 1.5f * k, Rand(10 * k, 14 * k), Rand(0.8f, 1.2f) * k, 2.6f, Rand(120, 180), 0.9f,
							0.6f * k, Rand(0.5f, 0.9f), 0, 0.03f, SmokeShade(), Rand(14, 28));
						p.Wind = 1;
						particles.Add(p);
					}
			}

			// --- Debris: dirt and metal arcing out, some of it burning and trailing smoke ---
			var debrisTint = Shade(dust, 1.05f);
			for (var i = 0; i < (int)((8 + 10 * k) * r.Debris); i++)
			{
				var burning = random.NextFloat() < r.Burning;
				var p = Make(PxParticleKind.Debris, 1.5f * k, height + 1, Rand(0.6f, 1.2f) * (0.7f + 0.3f * k), 0, Rand(35, 65), 1f,
					Rand(1.5f, 4.5f) * k, Rand(2f, 5.5f) * MathF.Sqrt(k), 0.22f, 0.015f, burning ? new float3(1f, 0.8f, 0.6f) : debrisTint, Rand(0, 1.5f));
				p.Spin = Rand(4, 9) * (random.Next(2) == 0 ? -1 : 1);
				p.Dusty = !air;
				p.TrailTint = dust;
				if (burning)
				{
					p.TrailKind = PxParticleKind.Smoke2;
					p.TrailRate = 0.35f;
					p.TrailSize = 0.2f * (0.6f + 0.4f * k);
					p.TrailLife = 22;
					p.TrailTint = Shade(soot, 0.9f);
				}

				particles.Add(p);
			}

			// Burning fragments: flames arcing down with their own smoke trails
			for (var i = 0; i < (int)((4 + 5 * k) * r.Burning * 2); i++)
			{
				var p = Make(PxParticleKind.Flame, 1.5f * k, height + 1, Rand(0.22f, 0.38f) * k, 0.1f, Rand(25, 45), 1f,
					3f * k, Rand(2f, 4.5f), 0.15f, 0.01f, Tint(info.FireColor), Rand(0, 1));
				p.TrailKind = PxParticleKind.Smoke2;
				p.TrailRate = 0.4f;
				p.TrailSize = 0.18f * (0.6f + 0.4f * k);
				p.TrailLife = 20;
				p.TrailTint = Shade(soot, 0.9f);
				particles.Add(p);
			}

			Embers(k, r.Embers);
			Sparks(k, r.Sparks);

			// --- Style extras ---
			switch (info.Style)
			{
				case PxExplosionStyle.Fragmentation:
					// The fragment sphere: fast pale streaks in every direction, down as well as up
					for (var i = 0; i < (int)(30 * k) + 10; i++)
						Add(PxParticleKind.Spark, 1 * k, height + Rand(-2, 2) * k, Rand(0.2f, 0.35f), 0, Rand(7, 12), 1f,
							7f * k, Rand(-3f, 3f), 0.02f, 0.02f, new float3(1f, 0.95f, 0.75f));

					// A dense black flak clump that hangs in the air
					for (var i = 0; i < (int)(8 * k * s) + 4; i++)
					{
						var p = Make(PxParticleKind.Smoke2, 1.5f * k, height + Rand(-1, 2) * k, Rand(0.45f, 0.65f) * k, 1.7f, Rand(80, 120), 0.95f,
							0.35f * k, Rand(0.05f, 0.2f), 0, 0.04f, Shade(new float3(0.16f, 0.15f, 0.15f), Rand(0.7f, 1.3f)), Rand(0, 2));
						p.Wind = 1;
						particles.Add(p);
					}

					break;

				case PxExplosionStyle.HitToKill:
					// White-hot spark shower and a cloud of white vapour where the two met
					for (var i = 0; i < (int)(36 * k) + 10; i++)
						Add(PxParticleKind.Spark, 1 * k, height + Rand(-1, 2) * k, Rand(0.2f, 0.4f), 0, Rand(14, 28), 1f,
							6f * k, Rand(-1f, 4f), 0.12f, 0.03f, new float3(Rand(0.85f, 1f), Rand(0.9f, 1f), 1f));

					for (var i = 0; i < (int)(8 * k * s) + 3; i++)
					{
						var p = Make(PxParticleKind.Smoke2, 2 * k, height + Rand(-1, 2) * k, Rand(0.4f, 0.6f) * k, 2.2f, Rand(50, 80), 0.6f,
							0.8f * k, Rand(0, 0.25f), 0, 0.05f, Shade(new float3(0.95f, 0.96f, 1f), Rand(0.85f, 1f)), Rand(0, 2));
						p.Wind = 1;
						particles.Add(p);
					}

					break;

				case PxExplosionStyle.Naval:
					// Spray thrown up around the hull
					for (var i = 0; i < (int)(10 * k); i++)
						Add(PxParticleKind.Foam, 6 * k, 1, Rand(0.4f, 0.7f) * k, 1.4f, Rand(30, 50), 0.85f,
							1.4f * k, Rand(1.5f, 3f), 0.15f, 0.04f, white);
					break;
			}

			// --- Second cook-offs: ammunition or fuel going up a moment later ---
			if (!air && k >= 0.9f && random.NextFloat() < r.Pops)
			{
				var pops = random.Next(1, 4);
				for (var j = 0; j < pops; j++)
					Pop(k, Rand(8, 45), Rand(0, MathF.PI * 2), Rand(0.5f, 2f) * k);
			}

			if (!air && k >= 0.9f && r.Column > 0 && random.NextFloat() < info.LingerChance)
				burn = burnLeft = Rand(90, 220) * Math.Min(k, 2f);
		}

		/// <summary>A small secondary blast at (a, r) from the centre, delay ticks later.</summary>
		void Pop(float k, float delay, float a, float dist)
		{
			var ox = MathF.Cos(a) * dist;
			var oy = MathF.Sin(a) * dist * 0.6f;
			void At(PxParticle p)
			{
				p.X += ox;
				p.Y += oy;
				particles.Add(p);
			}

			var size = Rand(0.35f, 0.55f) * k;
			At(Make(PxParticleKind.Flash, 0, 0, 1, 0.6f + 0.4f * size, -0.2f, 3, 0.9f, 0, 0, 0, 0, new float3(1, 1, 1), delay));
			At(Make(PxParticleKind.Light, 0, 0, 0, 0.9f + 0.6f * size, 0.1f, 6, 0.7f, 0, 0, 0, 0, new float3(1f, 0.85f, 0.6f), delay));
			for (var i = 0; i < 3; i++)
			{
				var p = Make(PxParticleKind.Fire2, 0.6f * size, 1, size * Rand(0.9f, 1.2f), 0.8f, Rand(12, 18), 1f, 0.5f, Rand(0.4f, 0.9f), 0, 0.1f, fire, delay + Rand(0, 1));
				p.Frame = random.Next(2) * 16;
				At(p);
			}

			for (var i = 0; i < 8; i++)
				At(Make(PxParticleKind.Spark, 0.5f, 1.5f, Rand(0.25f, 0.45f), 0, Rand(8, 14), 1f, 3.5f * size + 1, Rand(1, 3), 0.2f, 0.04f, new float3(1, 1, 1), delay));

			for (var i = 0; i < 6; i++)
			{
				var p = Make(PxParticleKind.Ember, 0.5f, 1.5f, Rand(0.6f, 1.1f), 0, Rand(20, 35), 1f, 3f * size + 1, Rand(1.5f, 3.5f), 0.12f, 0.02f,
					new float3(1f, Rand(0.5f, 0.75f), Rand(0.15f, 0.3f)), delay);
				p.Align = true;
				At(p);
			}

			for (var i = 0; i < 3; i++)
			{
				var p = Make(PxParticleKind.Smoke2, 0.8f * size, 1.5f, Rand(0.35f, 0.5f) * k, 2.4f, Rand(45, 70), 0.85f, 0.4f, Rand(0.4f, 0.8f), 0, 0.05f, FireLit(), delay + 1);
				p.FadeTint = true;
				p.TintEnd = SmokeShade();
				p.Wind = 1;
				At(p);
			}
		}

		/// <summary>Glowing embers thrown out of every blast, streaking along their flight and burning out.</summary>
		void Embers(float k, float amount)
		{
			for (var i = 0; i < (int)((16 + 14 * k) * amount); i++)
			{
				var p = Make(PxParticleKind.Ember, 1.5f * k, height + Rand(1, 3) * k, Rand(0.6f, 1.3f), 0, Rand(25, 50), 1f,
					Rand(2.5f, 5f) * k, Rand(1.5f, 5f), air ? 0.06f : 0.12f, 0.02f, new float3(1f, Rand(0.5f, 0.75f), Rand(0.15f, 0.3f)));
				p.Align = true;
				particles.Add(p);
			}
		}

		/// <summary>White-hot sparks, fast and short-lived.</summary>
		void Sparks(float k, float amount)
		{
			for (var i = 0; i < (int)((10 + 10 * k) * amount); i++)
				Add(PxParticleKind.Spark, 2 * k, height + 2, Rand(0.3f, 0.6f), 0, Rand(8, 16), 1f,
					4f * k, Rand(1f, 3f), air ? 0.05f : 0.2f, 0.04f, new float3(1, 1, 1));
		}

		/// <summary>The fire left at the impact: flames licking up and dark smoke, dying down as it burns out.</summary>
		void Burn(float dt)
		{
			burnLeft -= dt;
			nextFlame -= dt;
			if (nextFlame > 0)
				return;

			var k = info.Size;
			var heat = Math.Clamp(burnLeft / burn, 0, 1);
			nextFlame = Rand(1.5f, 3f) / (0.4f + 0.6f * heat);
			var p = Make(PxParticleKind.Fire2, 1.5f * k, Rand(0, 1), Rand(0.22f, 0.4f) * k * (0.5f + 0.5f * heat), 0.6f, Rand(12, 20), 0.9f,
				0.1f, Rand(0.4f, 0.9f), 0, 0.1f, fire);
			p.Frame = random.Next(2) * 16;
			particles.Add(p);

			if (random.NextFloat() < 0.7f)
				Add(PxParticleKind.Flame, 1.5f * k, Rand(0, 1), Rand(0.3f, 0.5f) * k * (0.5f + 0.5f * heat), 0.4f, Rand(10, 16), 0.9f,
					0.2f, Rand(0.4f, 0.9f), 0, 0.1f, Tint(info.FireColor));

			if (random.NextFloat() < 0.6f)
			{
				var q = Make(PxParticleKind.Smoke2, 1.5f * k, Rand(3, 6) * k * 0.5f, Rand(0.3f, 0.5f) * k, 2.2f, Rand(60, 90), 0.7f,
					0.15f, Rand(0.5f, 0.9f), 0, 0.03f, Shade(new float3(0.22f, 0.21f, 0.2f), Rand(0.8f, 1.2f)));
				q.Wind = 1;
				particles.Add(q);
			}
		}

		public void Tick(World world)
		{
			if ((time > 40 && burnLeft <= 0 && particles.Items.Count == 0) || time > 1200)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)world.Timestep;
			lastTime = now;
			if (!world.Paused)
			{
				if (!started)
					Start();

				time += dt;
				if (burnLeft > 0)
					Burn(dt);

				particles.Update(dt);
			}

			if (world.FogObscures(pos))
				yield break;

			if (info.Scorch && !air && scorch != null)
			{
				var alpha = Math.Clamp(time / 4f, 0, 1) * (1 - Math.Clamp((time - 100 - burn) / 60f, 0, 1)) * 0.8f;
				if (alpha > 0)
					yield return new SpriteRenderable(scorch.GetSprite(0), ground, WVec.Zero, ScorchZ, null,
						scorch.Scale * 0.45f * info.Size, alpha, new float3(1, 1, 1), TintModifiers.None, false);
			}

			foreach (var r in particles.Render(ground, 1024))
				yield return r;
		}
	}
}
