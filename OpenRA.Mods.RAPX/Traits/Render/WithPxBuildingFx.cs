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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	public enum PxBuildingFxType
	{
		Smoke,
		Steam,
		Sparks,
		Arcs,
		Flame,
		Pulse,
		Blink,
		Beacon,
		Orbit,
		Motes,
		Glints,
	}

	[Desc("A live effect on an HD building: chimney smoke or steam, welding sparks, electric arcs,",
		"pulsing or blinking lights, a rotating beacon or a light orbiting a dome.",
		"Flame is a burning gas flare: flickering flames with a glow and a trail of dark smoke.",
		"Motes are specks of light rising from Offset (spread over Radius.X) for Life ticks, e.g. energy climbing a column.",
		"Glints are short bright twinkles at random points of the Radius area, e.g. light catching crystals.",
		"Use several instances (WithPxBuildingFx@name) for several effects.")]
	public class WithPxBuildingFxInfo : ConditionalTraitInfo, Requires<BuildingInfo>
	{
		public readonly PxBuildingFxType Type = PxBuildingFxType.Smoke;

		[Desc("Position in screen pixels relative to the building's centre.")]
		public readonly float2 Offset = float2.Zero;

		[Desc("Half-size of the area the effect covers (Arcs, Sparks, Orbit), in screen pixels.")]
		public readonly float2 Radius = new(4, 2);

		public readonly Color Color = Color.White;

		[Desc("Size multiplier for the particles / light.")]
		public readonly float Size = 1f;

		[Desc("Cycle length in ticks for Pulse, Blink, Beacon and Orbit.")]
		public readonly int Period = 50;

		[Desc("Average ticks between particles / bursts.")]
		public readonly float Rate = 4f;

		[Desc("Start of the cycle in ticks (-1 = random). Use it to make several lights chase each other.")]
		public readonly int Phase = -1;

		[Desc("Particle lifetime in ticks.")]
		public readonly int Life = 70;

		[Desc("Light brightness range.")]
		public readonly float MinAlpha = 0f;
		public readonly float MaxAlpha = 1f;

		[Desc("Only active while this building is producing.")]
		public readonly bool OnlyWhileProducing = false;

		[Desc("Production queues that count for OnlyWhileProducing (empty = any).")]
		public readonly HashSet<string> Queues = new();

		public override object Create(ActorInitializer init) { return new WithPxBuildingFx(init.Self, this); }
	}

	public class WithPxBuildingFx : ConditionalTrait<WithPxBuildingFxInfo>, ITickRender, IRender, INotifyOwnerChanged
	{
		// Draw above the building sprite, which sorts at its centre
		const int ZBias = 512;

		readonly Actor self;
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float phase;
		readonly ISpriteSequence glow;
		readonly ISpriteSequence flare;

		ProductionQueue[] queues;
		long lastTime = -1;
		float clock;
		float emit;
		float strength;

		public WithPxBuildingFx(Actor self, WithPxBuildingFxInfo info)
			: base(info)
		{
			this.self = self;
			particles = new PxParticles(self.World);
			glow = particles.Sequence("glow");
			flare = particles.Sequence("flare");
			phase = info.Phase >= 0 ? info.Phase : random.Next(info.Period);
		}

		protected override void Created(Actor self)
		{
			base.Created(self);
			if (Info.OnlyWhileProducing)
				CacheQueues();
		}

		void INotifyOwnerChanged.OnOwnerChanged(Actor self, Player oldOwner, Player newOwner)
		{
			if (Info.OnlyWhileProducing)
				self.World.AddFrameEndTask(w => CacheQueues());
		}

		void CacheQueues()
		{
			var produces = self.Info.TraitInfos<ProductionInfo>().SelectMany(p => p.Produces).ToHashSet();
			bool Matches(ProductionQueue q) => produces.Contains(q.Info.Type) && (Info.Queues.Count == 0 || Info.Queues.Contains(q.Info.Type));

			queues = self.TraitsImplementing<ProductionQueue>().Where(Matches).ToArray();
			if (queues.Length == 0)
				queues = self.Owner.PlayerActor.TraitsImplementing<ProductionQueue>().Where(Matches).ToArray();
		}

		bool Active
		{
			get
			{
				if (IsTraitDisabled)
					return false;

				if (!Info.OnlyWhileProducing)
					return true;

				return queues != null && queues.Any(q => q.Enabled && q.AllQueued().Any(i => !i.Paused && i.Started)
					&& q.MostLikelyProducer().Actor == self);
			}
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			// Cosmetic only: advance with real time, at game speed, and freeze while paused
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)self.World.Timestep;
			lastTime = now;
			if (self.World.Paused || dt <= 0)
				return;

			clock += dt;
			var active = Active;

			// Lights fade in and out instead of popping (power outage, construction)
			strength = Math.Clamp(strength + (active ? dt : -dt) / 12f, 0, 1);

			particles.Update(dt);
			if (!active)
				return;

			emit += dt;
			while (emit >= Info.Rate)
			{
				emit -= Info.Rate * Rand(0.6f, 1.4f);
				Emit();
			}
		}

		void Emit()
		{
			var o = Info.Offset;
			var c = new float3(Info.Color.R, Info.Color.G, Info.Color.B) / 255f;
			switch (Info.Type)
			{
				case PxBuildingFxType.Motes:
				{
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Glow,
						X = o.X + Rand(-Info.Radius.X, Info.Radius.X),
						Y = o.Y + Rand(-Info.Radius.Y, Info.Radius.Y),
						VX = Rand(-0.02f, 0.02f),
						VZ = Rand(0.4f, 0.6f),
						Life = Info.Life * Rand(0.85f, 1.1f),
						Size = Info.Size * Rand(0.7f, 1.2f),
						Alpha = Info.MaxAlpha * Rand(0.6f, 1f),
						Tint = c,
					});
					break;
				}

				case PxBuildingFxType.Glints:
				{
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Glow,
						X = o.X + Rand(-Info.Radius.X, Info.Radius.X),
						Y = o.Y + Rand(-Info.Radius.Y, Info.Radius.Y),
						Life = Info.Life * Rand(0.7f, 1.2f),
						Size = Info.Size * Rand(0.6f, 1.1f),
						Grow = -0.6f,
						Alpha = Info.MaxAlpha,
						Tint = c,
					});
					break;
				}

				case PxBuildingFxType.Smoke:
				case PxBuildingFxType.Steam:
				{
					var steam = Info.Type == PxBuildingFxType.Steam;
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Smoke,
						X = o.X + Rand(-Info.Radius.X, Info.Radius.X),
						Y = o.Y + Rand(-Info.Radius.Y, Info.Radius.Y),
						Z = 0,
						VX = Rand(0.05f, 0.2f),
						VZ = Rand(0.35f, 0.6f) * (steam ? 1.3f : 1f),
						Drag = 0.01f,
						Life = Info.Life * Rand(0.8f, 1.2f),
						Size = Info.Size * Rand(0.35f, 0.5f),
						Grow = steam ? 2.6f : 2.2f,
						Alpha = Info.Color.A / 255f * Rand(0.7f, 1f),
						Tint = Rand(0.9f, 1.05f) * c,
						Frame = random.Next(particles.FrameCount(PxParticleKind.Smoke)),
						Angle = random.Next(1024),
						Spin = Rand(-3, 3),
					});
					break;
				}

				case PxBuildingFxType.Sparks:
				{
					// A short welding burst: a flash plus a handful of sparks falling under gravity
					var x = o.X + Rand(-Info.Radius.X, Info.Radius.X);
					var y = o.Y + Rand(-Info.Radius.Y, Info.Radius.Y);
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Glow,
						X = x,
						Y = y,
						Life = Rand(4, 8),
						Size = Info.Size * Rand(0.6f, 1f),
						Alpha = 0.9f,
						Tint = c,
					});

					var n = random.Next(3, 8);
					for (var i = 0; i < n; i++)
					{
						var a = Rand(0, MathF.PI * 2);
						var s = Rand(0.4f, 1.6f);
						particles.Add(new PxParticle
						{
							Kind = PxParticleKind.Spark,
							X = x,
							Y = y,
							Z = 2,
							VX = MathF.Cos(a) * s,
							VY = MathF.Sin(a) * s * 0.5f,
							VZ = Rand(0.5f, 2f),
							Gravity = 0.18f,
							Drag = 0.04f,
							Life = Rand(8, 18),
							Size = Info.Size * Rand(0.5f, 0.9f),
							Alpha = 1,
							Tint = new float3(1, 0.85f, 0.55f),
						});
					}

					break;
				}

				case PxBuildingFxType.Flame:
				{
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Flame,
						X = o.X + Rand(-Info.Radius.X, Info.Radius.X),
						Y = o.Y + Rand(-Info.Radius.Y, Info.Radius.Y),
						Z = Info.Size * 6,
						VX = Rand(0.05f, 0.15f),
						VZ = Rand(0.1f, 0.25f),
						Life = Rand(10, 16),
						Size = Info.Size * Rand(0.55f, 0.8f),
						Grow = -0.2f,
						Alpha = 1,
						Tint = c,
						Frame = random.Next(particles.FrameCount(PxParticleKind.Flame)),
					});

					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Glow,
						X = o.X,
						Y = o.Y,
						Z = Info.Size * 5,
						Life = Rand(6, 10),
						Size = Info.Size * Rand(1.6f, 2.2f),
						Alpha = 0.3f,
						Tint = new float3(1, 0.55f, 0.2f),
					});

					if (random.Next(3) == 0)
					{
						var grey = Rand(0.15f, 0.25f);
						particles.Add(new PxParticle
						{
							Kind = PxParticleKind.Smoke,
							X = o.X + Rand(-1, 1),
							Y = o.Y,
							Z = Info.Size * 14,
							VX = Rand(0.1f, 0.25f),
							VZ = Rand(0.35f, 0.55f),
							Drag = 0.008f,
							Life = Info.Life * Rand(0.8f, 1.2f),
							Size = Info.Size * Rand(0.3f, 0.45f),
							Grow = 2.4f,
							Alpha = 0.6f,
							Tint = new float3(grey, grey, grey),
							Frame = random.Next(particles.FrameCount(PxParticleKind.Smoke)),
							Angle = random.Next(1024),
							Spin = Rand(-3, 3),
						});
					}

					break;
				}

				case PxBuildingFxType.Arcs:
				{
					// A jagged bolt between two random points of the area, drawn as a chain of sparks
					var a = Rand(0, MathF.PI * 2);
					var b = a + Rand(1.5f, 4.7f);
					var (x0, y0) = (o.X + MathF.Cos(a) * Info.Radius.X, o.Y + MathF.Sin(a) * Info.Radius.Y);
					var (x1, y1) = (o.X + MathF.Cos(b) * Info.Radius.X, o.Y + MathF.Sin(b) * Info.Radius.Y);
					const int Segments = 10;
					var jitter = Math.Max(Info.Radius.X, Info.Radius.Y) * 0.35f;
					var life = Rand(3, 6);
					for (var i = 0; i <= Segments; i++)
					{
						var t = i / (float)Segments;
						var bend = MathF.Sin(t * MathF.PI) * jitter;
						particles.Add(new PxParticle
						{
							Kind = PxParticleKind.Spark,
							X = x0 + (x1 - x0) * t + Rand(-bend, bend),
							Y = y0 + (y1 - y0) * t + Rand(-bend, bend),
							Life = life,
							Size = Info.Size * Rand(0.6f, 1f),
							Alpha = 1,
							Tint = c,
						});
					}

					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Glow,
						X = o.X,
						Y = o.Y,
						Life = life * 1.5f,
						Size = Info.Size * 2.2f,
						Alpha = 0.6f,
						Tint = c,
					});
					break;
				}
			}
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			var origin = self.CenterPosition;
			foreach (var r in particles.Render(origin, ZBias))
				yield return r;

			if (strength <= 0)
				yield break;

			var c = new float3(Info.Color.R, Info.Color.G, Info.Color.B) / 255f;
			var t = (clock + phase) / Info.Period;
			var cycle = t - MathF.Floor(t);
			var range = Info.MaxAlpha - Info.MinAlpha;
			switch (Info.Type)
			{
				case PxBuildingFxType.Pulse:
				{
					var a = Info.MinAlpha + range * (0.5f + 0.5f * MathF.Sin(cycle * MathF.PI * 2));
					yield return Light(glow, origin, Info.Offset, Info.Size * (0.9f + 0.2f * a), a * strength, c);
					break;
				}

				case PxBuildingFxType.Blink:
				{
					// Short sharp flash with a quick decay
					var a = cycle < 0.12f ? 1 - cycle / 0.12f * 0.3f : cycle < 0.2f ? 0.7f * (0.2f - cycle) / 0.08f : 0;
					a = Info.MinAlpha + range * a;
					if (a > 0.01f)
						yield return Light(glow, origin, Info.Offset, Info.Size, a * strength, c);

					break;
				}

				case PxBuildingFxType.Beacon:
				{
					// A rotating lamp: brightest (with a lens streak) when it faces the camera
					var facing = MathF.Cos(cycle * MathF.PI * 2);
					var a = Info.MinAlpha + range * MathF.Pow(Math.Max(facing, 0), 3);
					var dx = MathF.Sin(cycle * MathF.PI * 2) * Info.Radius.X;
					var pos = new float2(Info.Offset.X + dx, Info.Offset.Y);
					yield return Light(glow, origin, pos, Info.Size * 0.7f, (0.25f + 0.75f * a) * strength, c);
					if (a > 0.3f)
						yield return Light(flare, origin, Info.Offset, Info.Size * 0.8f, (a - 0.3f) * strength, c);

					break;
				}

				case PxBuildingFxType.Orbit:
				{
					// A light circling a dome: bright in front, dimmed while behind it
					var ang = cycle * MathF.PI * 2;
					var pos = new float2(Info.Offset.X + MathF.Cos(ang) * Info.Radius.X, Info.Offset.Y + MathF.Sin(ang) * Info.Radius.Y);
					var front = 0.5f + 0.5f * MathF.Sin(ang);
					var a = Info.MinAlpha + range * front * front;
					yield return Light(glow, origin, pos, Info.Size * (0.7f + 0.3f * front), a * strength, c);
					break;
				}
			}
		}

		static IRenderable Light(ISpriteSequence seq, WPos origin, float2 offset, float size, float alpha, in float3 tint)
		{
			var o = PxParticles.ToWorld(offset.X, offset.Y);
			return new SpriteRenderable(seq.GetSprite(0), origin + o, WVec.Zero, ZBias - o.Y + 1, null,
				seq.Scale * size, alpha, tint, TintModifiers.IgnoreWorldTint, false);
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			// Generous box: smoke rises well above the building
			var c = wr.ScreenPxPosition(self.CenterPosition);
			yield return new Rectangle(c.X - 160, c.Y - 260, 320, 380);
		}
	}
}
