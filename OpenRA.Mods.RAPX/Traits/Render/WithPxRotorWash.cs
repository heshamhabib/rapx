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
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Rotor downwash (IDEA-47): a helicopter close to the ground blasts a ring of dust outwards from under itself",
		"(snow on snow maps, sand in the desert, spray on water), strongest right above the ground. Purely cosmetic.",
		"Uses `pxfx` xdust/xsmoke/foam particles.")]
	public class WithPxRotorWashInfo : ConditionalTraitInfo, Requires<AircraftInfo>
	{
		[Desc("No downwash above this height.")]
		public readonly WDist Height = new(1024);

		[Desc("Dust puffs per tick right above the ground.")]
		public readonly float Rate = 1.6f;

		[Desc("Radius of the rotor disc: puffs start at its rim.")]
		public readonly WDist RotorRadius = new(384);

		[Desc("Terrain target types that get spray instead of dust.")]
		public readonly BitSet<TargetableType> WaterTypes = new("Water");

		public override object Create(ActorInitializer init) { return new WithPxRotorWash(init.Self, this); }
	}

	public class WithPxRotorWash : ConditionalTrait<WithPxRotorWashInfo>, ITickRender, IRender
	{
		const float PixelsPerWorld = 24f / 1024f;

		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float3 dust;
		readonly float3 spray = new(0.88f, 0.93f, 0.96f);
		Aircraft aircraft;
		WPos anchor, lastGround;
		float emit;
		long lastTime = -1;

		public WithPxRotorWash(Actor self, WithPxRotorWashInfo info)
			: base(info)
		{
			particles = new PxParticles(self.World) { Max = 160 };
			dust = self.World.Map.Tileset switch
			{
				"SNOW" => new float3(0.92f, 0.94f, 0.97f),
				"DESERT" => new float3(0.78f, 0.68f, 0.5f),
				_ => new float3(0.6f, 0.53f, 0.42f),
			};
		}

		protected override void Created(Actor self)
		{
			aircraft = self.Trait<Aircraft>();
			base.Created(self);
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)self.World.Timestep;
			lastTime = now;
			if (self.World.Paused || dt <= 0)
				return;

			particles.Update(dt);
			if (IsTraitDisabled || !self.IsInWorld)
				return;

			// Rotors only blow hard while flying: a landed helicopter idles them
			var map = self.World.Map;
			var height = map.DistanceAboveTerrain(self.CenterPosition).Length;
			if (aircraft.AtLandAltitude || height >= Info.Height.Length)
				return;

			var cell = map.CellContaining(self.CenterPosition);
			if (!map.Contains(cell))
				return;

			var ground = new WPos(self.CenterPosition.X, self.CenterPosition.Y, self.CenterPosition.Z - height);
			if (particles.Items.Count == 0)
				anchor = ground;

			lastGround = ground;

			var strength = 1f - (float)height / Info.Height.Length;
			var water = map.GetTerrainInfo(cell).TargetTypes.Overlaps(Info.WaterTypes);
			var o = ground - anchor;
			var ox = o.X * PixelsPerWorld;
			var oy = o.Y * PixelsPerWorld;
			var rim = Info.RotorRadius.Length * PixelsPerWorld;

			emit += dt * Info.Rate * strength * strength;
			while (emit >= 1)
			{
				emit--;
				var a = Rand(0, MathF.PI * 2);
				var c = MathF.Cos(a);
				var s = MathF.Sin(a) * 0.78f;
				var v = Rand(0.9f, 1.6f) * (0.5f + 0.5f * strength);

				// Low rolling cloud racing outwards from under the rotor
				particles.Add(new PxParticle
				{
					Kind = water ? PxParticleKind.Foam : PxParticleKind.Smoke2,
					X = ox + c * rim * Rand(0.3f, 0.8f),
					Y = oy + s * rim * Rand(0.3f, 0.8f),
					Z = 0.5f,
					VX = c * v,
					VY = s * v,
					VZ = water ? 0 : Rand(0.01f, 0.07f),
					Drag = 0.045f,
					Life = water ? Rand(18, 28) : Rand(34, 52),
					Size = Rand(0.1f, 0.16f),
					Grow = water ? 1.5f : Rand(2.5f, 3.5f),
					Alpha = (water ? 0.6f : 0.42f) * (0.4f + 0.6f * strength),
					Tint = water ? spray : dust,
					Frame = random.Next(12),
					Angle = random.Next(1024),
					Spin = Rand(-2, 2),
				});
			}

			// Now and then a flat ring of blown dust (or ripples on water) right under the rotor
			if (random.NextFloat() < 0.08f * dt * strength)
				particles.Add(new PxParticle
				{
					Kind = water ? PxParticleKind.Ring : PxParticleKind.Dust,
					X = ox,
					Y = oy,
					Life = Rand(18, 26),
					Size = Rand(0.35f, 0.5f),
					Grow = 1.2f,
					Alpha = (water ? 0.35f : 0.3f) * strength,
					Tint = water ? spray : dust,
				});
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			if (particles.Items.Count == 0)
				return Array.Empty<IRenderable>();

			// Sorts with the ground units around it, under the helicopter
			return particles.Render(anchor, 0);
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			if (particles.Items.Count == 0)
				yield break;

			var a = wr.ScreenPxPosition(anchor);
			var g = wr.ScreenPxPosition(lastGround);
			yield return Rectangle.FromLTRB(Math.Min(a.X, g.X) - 140, Math.Min(a.Y, g.Y) - 100, Math.Max(a.X, g.X) + 140, Math.Max(a.Y, g.Y) + 100);
		}
	}
}
