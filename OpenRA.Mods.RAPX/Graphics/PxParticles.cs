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
using OpenRA.Primitives;
using OpenRA.Support;

namespace OpenRA.Mods.RAPX.Graphics
{
	public enum PxParticleKind
	{
		Smoke, Spark, Glow, Flame, Chunk, Ring, Plume, Fireball, Billow, Foam,

		// Cinematic blast sprites (artsrc/fx/make_blast_particles.py)

		/// <summary>Rolling fireball that cools to sooty smoke over its life (two variants: Frame 0 or 16).</summary>
		Fire2,

		/// <summary>Volumetric lit smoke puff (12 variants).</summary>
		Smoke2,

		/// <summary>Dust wave on the ground, flat.</summary>
		Dust,

		/// <summary>Shock ring on the ground, flat.</summary>
		Shock,

		/// <summary>Detonation glare (additive).</summary>
		Flash,

		/// <summary>Light thrown on the ground (additive, flat).</summary>
		Light,

		/// <summary>Dirt clods, rocks and metal shards (16 variants).</summary>
		Debris,

		/// <summary>Glowing ember streak, turned along its flight (additive).</summary>
		Ember,

		/// <summary>Soft drop shadow, flat.</summary>
		Shadow,

		/// <summary>Billowing coloured smoke from a smoke grenade, white and lit, tinted by the emitter (12 variants,
		/// artsrc/fx/make_smoke_fx.py).</summary>
		Dye,

		/// <summary>Building rubble: concrete, bricks, rebar, charred beams (8 variants, artsrc/fx/make_ruin_fx.py).</summary>
		Rubble,
	}

	/// <summary>One cosmetic particle. Positions are in screen pixels relative to the emitter's origin:
	/// X/Y on the ground plane, Z = height above it (drawn upwards). A negative Age delays the particle: it neither
	/// moves nor shows until its age reaches zero.</summary>
	public struct PxParticle
	{
		public PxParticleKind Kind;
		public float X, Y, Z;
		public float VX, VY, VZ;
		public float Gravity;
		public float Drag;
		public float Age, Life;
		public float Size, Grow;
		public float Alpha;
		public float3 Tint;
		public int Frame;
		public float Spin, Angle;

		/// <summary>Colour at the end of the particle's life (used when FadeTint is set).</summary>
		public float3 TintEnd;
		public bool FadeTint;

		/// <summary>How much the emitter's wind moves this particle (0 = not at all, 1 = fully).</summary>
		public float Wind;

		/// <summary>Turn the sprite along the direction of flight (embers, streaks).</summary>
		public bool Align;

		/// <summary>Leave a trail: TrailRate particles of TrailKind per tick, TrailSize big, tinted TrailTint.</summary>
		public PxParticleKind TrailKind;
		public float TrailRate, TrailSize, TrailLife;
		public float3 TrailTint;
		public float TrailAcc;

		/// <summary>Kick up a little dust (tinted TrailTint) when it hits the ground.</summary>
		public bool Dusty;
	}

	/// <summary>One particle, fully prepared for drawing (sprite, final size, alpha and tint).</summary>
	public struct PxQuad
	{
		public Sprite Sprite;
		public WPos Pos;
		public float Scale, Alpha, Rotation;
		public float3 Tint;
	}

	/// <summary>Draws a whole emitter's particles as one renderable instead of one SpriteRenderable per particle.
	/// All of an emitter's airborne particles share one sort key (origin.Y + zBias; flat ground sprites origin.Y + FlatZ),
	/// so batching them keeps the exact draw order while the world renderer only allocates and sorts two entries per
	/// emitter — a salvo of rockets trailing ten thousand puffs no longer swamps it. Quads outside the viewport are
	/// skipped at draw time.</summary>
	public sealed class PxParticlesRenderable : IRenderable, IFinalizedRenderable
	{
		readonly List<PxQuad> quads;
		readonly WVec offset;

		public PxParticlesRenderable(List<PxQuad> quads, WPos pos, int zOffset, WVec offset)
		{
			this.quads = quads;
			Pos = pos;
			ZOffset = zOffset;
			this.offset = offset;
		}

		public WPos Pos { get; }
		public int ZOffset { get; }
		public bool IsDecoration => false;

		public IRenderable WithZOffset(int newOffset) { return new PxParticlesRenderable(quads, Pos, newOffset, offset); }
		public IRenderable OffsetBy(in WVec vec) { return new PxParticlesRenderable(quads, Pos + vec, ZOffset, offset + vec); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		public void Render(WorldRenderer wr)
		{
			// Alpha-blended quads first, then the additive ones: the sprite renderer flushes its batch on every
			// blend-mode switch, and a trail interleaves smoke (alpha) with glow and flame (additive) in spawn order,
			// which flushed the batch on nearly every particle — thousands of draw calls in a big salvo, which is what
			// actually dropped the frame rate. Two passes mean at most one switch per emitter, and consecutive emitters
			// that end and start in the same mode chain into one batch. Additive blending commutes, so order within the
			// second pass does not matter, and the glows now draw over their own smoke, which reads better anyway.
			DrawPass(wr, false);
			DrawPass(wr, true);
		}

		void DrawPass(WorldRenderer wr, bool additive)
		{
			var wsr = Game.Renderer.WorldSpriteRenderer;
			var lighting = wr.TerrainLighting;
			var tl = wr.Viewport.TopLeft;
			var br = wr.Viewport.BottomRight;
			foreach (var q in quads)
			{
				if (q.Sprite.BlendMode == BlendMode.Additive != additive)
					continue;

				var pos = q.Pos + offset;

				// Same placement as SpriteRenderable.ScreenPosition
				var s = 0.5f * q.Scale * q.Sprite.Size;
				var p = wr.Screen3DPxPosition(pos) - new float3((int)s.X, (int)s.Y, s.Z);

				// Off the screen: skip the draw (centre +- half size, with room for rotation and the sprite offset)
				var cx = p.X + s.X;
				var cy = p.Y + s.Y;
				var h = 1.6f * Math.Max(Math.Abs(s.X), Math.Abs(s.Y)) + 64;
				if (cx + h < tl.X || cx - h > br.X || cy + h < tl.Y || cy - h > br.Y)
					continue;

				var t = q.Alpha * q.Tint;
				if (lighting != null)
					t *= lighting.TintAt(pos);

				wsr.DrawSprite(q.Sprite, null, p, q.Scale, t, q.Alpha, q.Rotation);
			}
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}

	/// <summary>
	/// Tiny particle simulation for building effects (smoke, sparks, flames, debris).
	/// Purely cosmetic: advanced with real frame time, never touches the synced simulation.
	/// Sprites come from the `pxfx` image (artsrc/fx/make_fx.py, make_fire_fx.py, make_blast_particles.py).
	/// </summary>
	public class PxParticles
	{
		public const string Image = "pxfx";

		// World units per screen pixel (1024 per 24 pixel cell)
		const float WorldPerPixel = 1024f / 24f;

		// Flat ground sprites sort just above the terrain, under units
		const int FlatZ = -1024;

		static readonly Dictionary<PxParticleKind, string> SequenceNames = new()
		{
			{ PxParticleKind.Smoke, "puff" },
			{ PxParticleKind.Spark, "spark" },
			{ PxParticleKind.Glow, "glow" },
			{ PxParticleKind.Flame, "flame" },
			{ PxParticleKind.Chunk, "chunk" },
			{ PxParticleKind.Ring, "ring" },
			{ PxParticleKind.Plume, "wsmoke" },
			{ PxParticleKind.Fireball, "fireball" },
			{ PxParticleKind.Billow, "billow" },
			{ PxParticleKind.Foam, "foam" },
			{ PxParticleKind.Fire2, "xfire" },
			{ PxParticleKind.Smoke2, "xsmoke" },
			{ PxParticleKind.Dust, "xdust" },
			{ PxParticleKind.Shock, "xshock" },
			{ PxParticleKind.Flash, "xflash" },
			{ PxParticleKind.Light, "xlight" },
			{ PxParticleKind.Debris, "xdebris" },
			{ PxParticleKind.Ember, "xember" },
			{ PxParticleKind.Shadow, "shadow" },
			{ PxParticleKind.Dye, "csmoke" },
			{ PxParticleKind.Rubble, "rubble" },
		};

		public readonly List<PxParticle> Items = new();

		/// <summary>Most particles alive at once; extra ones are dropped.</summary>
		public int Max = 400;

		/// <summary>Wind in screen pixels per tick, applied to particles with a Wind factor.</summary>
		public float2 Wind = float2.Zero;

		/// <summary>Live particles across all emitters as of the last world tick: the effects governor's load measure.</summary>
		public static int LiveTotal { get; private set; }

		/// <summary>Scene-wide particle budget: above it the governor thins new particles out (and grows the survivors),
		/// so a dozen rocket salvos saturate in density instead of dragging the frame rate down. 6000 holds the worst
		/// benchmark frame (tools/test-missile-perf.sh, a 354-rocket double salvo on Berlin) under control while the
		/// smoke still reads as a solid wall.</summary>
		public const int GlobalBudget = 6000;

		/// <summary>RAPX_PARTICLE_LEGACY=1: the old path — one SpriteRenderable per particle and no governor — kept
		/// for A/B frame-rate comparisons (tools/test-missile-perf.sh).</summary>
		static readonly bool Legacy = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_PARTICLE_LEGACY"));

		static int statTick = -1;
		static int statAccum;
		static int bornTick = -1;
		static int bornThisTick;
		int censusTick = -1;

		readonly Dictionary<PxParticleKind, ISpriteSequence> sequences = new();
		readonly SequenceSet sequenceSet;
		readonly World world;
		readonly List<PxParticle> spawned = new();
		readonly List<PxQuad> airQuads = new();
		readonly List<PxQuad> flatQuads = new();
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());

		public PxParticles(World world)
		{
			this.world = world;
			sequenceSet = world.Map.Sequences;
		}

		public ISpriteSequence Sequence(string name)
		{
			return sequenceSet.HasSequence(Image, name) ? sequenceSet.GetSequence(Image, name) : null;
		}

		ISpriteSequence Sequence(PxParticleKind kind)
		{
			if (!sequences.TryGetValue(kind, out var s))
				sequences[kind] = s = sequenceSet.GetSequence(Image, SequenceNames[kind]);

			return s;
		}

		public int FrameCount(PxParticleKind kind) { return Sequence(kind).Length; }

		public static bool IsFlat(PxParticleKind kind)
		{
			return kind is PxParticleKind.Dust or PxParticleKind.Shock or PxParticleKind.Light or PxParticleKind.Shadow or PxParticleKind.Ring;
		}

		public void Add(PxParticle p)
		{
			// Keep busy emitters bounded
			if (Items.Count >= Max)
				return;

			// Effects governor: when the whole scene is over budget (every launcher of a salvo trailing smoke at once),
			// admit fewer new particles and grow the survivors to match, so the smoke keeps its mass and the particle
			// count — and with it the frame time — levels off. Births this tick count too, or a burst of forty
			// explosions in one tick (a whole salvo landing) would sail past the budget before the census sees it.
			// One-shot cinematic sprites (the flash, ring and ground light of a blast) are too few to matter and
			// always get in.
			if (bornTick != world.WorldTick)
			{
				bornTick = world.WorldTick;
				bornThisTick = 0;
			}

			if (!Legacy && LiveTotal + bornThisTick > GlobalBudget &&
				p.Kind is not (PxParticleKind.Flash or PxParticleKind.Shock or PxParticleKind.Light or PxParticleKind.Ring))
			{
				var load = (float)(LiveTotal + bornThisTick) / GlobalBudget;
				if (random.NextFloat() * load >= 1f)
					return;

				p.Size *= MathF.Min(1.5f, MathF.Sqrt(load));
			}

			Items.Add(p);
			bornThisTick++;
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		/// <summary>Advance by dt game ticks (fractional).</summary>
		public void Update(float dt)
		{
			// Census for the effects governor: every live emitter contributes its count once per world tick (render-frame
			// updaters like the wreck fires call Update more often), so last tick's sum is the scene's live particle
			// count. Dead emitters simply stop being counted.
			if (world.WorldTick != statTick)
			{
				LiveTotal = statAccum;
				statAccum = 0;
				statTick = world.WorldTick;
			}

			if (censusTick != world.WorldTick)
			{
				censusTick = world.WorldTick;
				statAccum += Items.Count;
			}

			for (var i = Items.Count - 1; i >= 0; i--)
			{
				var p = Items[i];
				var wasWaiting = p.Age < 0;
				p.Age += dt;
				if (p.Age >= p.Life)
				{
					Items.RemoveAt(i);
					continue;
				}

				if (p.Age < 0)
				{
					Items[i] = p;
					continue;
				}

				// Delayed particles start their motion on the tick they appear
				var step = wasWaiting ? p.Age : dt;
				var drag = p.Drag > 0 ? MathF.Pow(1 - p.Drag, step) : 1;
				p.VX *= drag;
				p.VY *= drag;
				p.VZ = p.VZ * drag - p.Gravity * step;
				p.X += p.VX * step;
				p.Y += p.VY * step;
				p.Z += p.VZ * step;
				p.Angle += p.Spin * step;
				if (p.Wind > 0)
				{
					p.X += Wind.X * p.Wind * step;
					p.Y += Wind.Y * p.Wind * step;
				}

				if (p.TrailRate > 0)
				{
					p.TrailAcc += p.TrailRate * step;
					while (p.TrailAcc >= 1)
					{
						p.TrailAcc--;
						spawned.Add(new PxParticle
						{
							Kind = p.TrailKind,
							X = p.X + Rand(-0.5f, 0.5f),
							Y = p.Y + Rand(-0.3f, 0.3f),
							Z = p.Z,
							VX = p.VX * 0.08f + Rand(-0.08f, 0.08f),
							VY = p.VY * 0.08f + Rand(-0.05f, 0.05f),
							VZ = Rand(0.05f, 0.2f),
							Drag = 0.05f,
							Life = (p.TrailLife > 0 ? p.TrailLife : 24) * Rand(0.8f, 1.2f),
							Size = p.TrailSize * Rand(0.85f, 1.15f),
							Grow = 2.2f,
							Alpha = 0.6f,
							Tint = p.TrailTint,
							Frame = random.Next(Math.Max(1, FrameCount(p.TrailKind))),
							Spin = Rand(-1, 1),
							Angle = random.Next(1024),
							Wind = 1,
						});
					}
				}

				// Debris and sparks bounce once on the ground and then settle
				if (p.Z < 0 && p.Gravity > 0)
				{
					if (p.Dusty && p.VZ < -0.8f)
					{
						var n = p.VZ < -2.5f ? 2 : 1;
						for (var j = 0; j < n; j++)
							spawned.Add(new PxParticle
							{
								Kind = PxParticleKind.Smoke2,
								X = p.X + Rand(-1, 1),
								Y = p.Y + Rand(-0.6f, 0.6f),
								Z = 0.5f,
								VX = p.VX * 0.25f + Rand(-0.25f, 0.25f),
								VY = p.VY * 0.25f + Rand(-0.15f, 0.15f),
								VZ = Rand(0.1f, 0.35f) * Math.Min(1.5f, -p.VZ * 0.4f),
								Drag = 0.08f,
								Life = Rand(18, 30),
								Size = Rand(0.22f, 0.36f) * Math.Min(1.4f, 0.6f + p.Size),
								Grow = 2.6f,
								Alpha = 0.55f,
								Tint = p.TrailTint,
								Frame = random.Next(FrameCount(PxParticleKind.Smoke2)),
								Spin = Rand(-1, 1),
								Angle = random.Next(1024),
								Wind = 1,
							});
					}

					p.Z = 0;
					p.VZ = -p.VZ * 0.3f;
					p.VX *= 0.5f;
					p.VY *= 0.5f;
					p.Spin *= 0.5f;
					p.TrailRate *= 0.5f;
					if (p.VZ < 0.3f)
					{
						p.VZ = 0;
						p.Gravity = 0;
						p.VX = p.VY = p.Spin = 0;
						p.TrailRate = 0;
						p.Dusty = false;
					}
				}

				Items[i] = p;
			}

			if (spawned.Count > 0)
			{
				foreach (var s in spawned)
					Add(s);

				spawned.Clear();
			}
		}

		public static WVec ToWorld(float x, float y)
		{
			return new WVec((int)(x * WorldPerPixel), (int)(y * WorldPerPixel), 0);
		}

		static float3 Lerp(float3 a, float3 b, float t)
		{
			return new float3(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t, a.Z + (b.Z - a.Z) * t);
		}

		/// <summary>Renders all particles around origin. Every particle sorts at origin.Y + zBias, so emitter effects
		/// stay on top of their building regardless of how high above it they are; flat ground sprites (dust, shock
		/// rings, light, shadows) sort just above the terrain instead. Particles over a cell for which hidden returns
		/// true (e.g. fog) are skipped. The whole emitter draws as (at most) two batched renderables, one per layer,
		/// so the world renderer never sees the individual particles.</summary>
		public IEnumerable<IRenderable> Render(WPos origin, int zBias, Func<WPos, bool> hidden = null)
		{
			airQuads.Clear();
			flatQuads.Clear();
			foreach (var p in Items)
			{
				if (p.Age < 0)
					continue;

				var t = p.Age / p.Life;
				var seq = Sequence(p.Kind);
				float alpha;
				var frame = p.Frame;
				switch (p.Kind)
				{
					case PxParticleKind.Smoke:
						// Quick fade-in, long fade-out
						alpha = Math.Min(t * 6, 1) * (1 - t) * (1 - t);
						break;
					case PxParticleKind.Plume:
						// Thick volumetric smoke: dense while it rises, thins out as it spreads
						alpha = Math.Min(t * 8, 1) * (1 - t) * (1 - t * 0.5f);
						break;
					case PxParticleKind.Flame:
						alpha = Math.Min(t * 5, 1) * (1 - t * t);
						frame = (p.Frame + (int)(p.Age / 2)) % seq.Length;
						break;
					case PxParticleKind.Fireball:
						// Rolling flame (artsrc/fx/make_fire_fx.py): flares up, burns out as it expands
						alpha = Math.Min(t * 10, 1) * (1 - t) * (1 - t * 0.6f);
						frame = (p.Frame + (int)(p.Age / 1.5f)) % seq.Length;
						break;
					case PxParticleKind.Fire2:
					{
						// Each fireball plays its 16-frame burst over its own life: white-hot, orange, red, then soot
						var frames = seq.Length / 2;
						alpha = Math.Min(t * 14, 1) * (1 - MathF.Pow(Math.Max(0, (t - 0.7f) / 0.3f), 1.5f));
						frame = (p.Frame >= frames ? frames : 0) + Math.Min(frames - 1, (int)(t * frames));
						break;
					}

					case PxParticleKind.Billow:
						// Detailed smoke: builds up behind the flames, then thins out as it spreads
						alpha = Math.Min(t * 3, 1) * (1 - t) * (1 - t * 0.3f);
						break;
					case PxParticleKind.Smoke2:
						alpha = Math.Min(t * 4, 1) * MathF.Pow(1 - t, 1.25f);
						break;
					case PxParticleKind.Dye:
						// Dense coloured smoke: pours out opaque, keeps its body, thins out only late in life
						alpha = Math.Min(t * 5, 1) * (1 - MathF.Pow(t, 1.6f));
						break;
					case PxParticleKind.Foam:
						// Foam on water (artsrc/fx/make_water_fx.py): appears at once, then slowly breaks up
						alpha = Math.Min(t * 10, 1) * MathF.Pow(1 - t, 1.5f);
						break;
					case PxParticleKind.Chunk:
					case PxParticleKind.Debris:
					case PxParticleKind.Rubble:
						alpha = t < 0.85f ? 1 : (1 - t) / 0.15f;
						break;
					case PxParticleKind.Ring:
						alpha = 1 - t;
						frame = Math.Min((int)(t * seq.Length), seq.Length - 1);
						break;
					case PxParticleKind.Dust:
						alpha = Math.Min(t * 10, 1) * MathF.Pow(1 - t, 1.4f);
						frame = Math.Min((int)(t * seq.Length), seq.Length - 1);
						break;
					case PxParticleKind.Shock:
						alpha = (1 - t) * (1 - t);
						frame = Math.Min((int)(t * seq.Length), seq.Length - 1);
						break;
					case PxParticleKind.Flash:
						alpha = MathF.Pow(1 - t, 1.6f);
						break;
					case PxParticleKind.Light:
						alpha = Math.Min(t * 6, 1) * MathF.Pow(1 - t, 2f);
						break;
					case PxParticleKind.Ember:
						alpha = Math.Min(t * 8, 1) * MathF.Pow(1 - t, 1.3f);
						break;
					case PxParticleKind.Shadow:
						alpha = 1;
						break;
					default:
						alpha = 1 - t;
						break;
				}

				alpha *= p.Alpha;
				if (alpha <= 0.01f)
					continue;

				var size = p.Size * (1 + p.Grow * t);
				var flat = IsFlat(p.Kind);
				var offset = flat ? ToWorld(p.X, p.Y) : ToWorld(p.X, p.Y - p.Z);
				if (hidden != null && hidden(origin + ToWorld(p.X, p.Y)))
					continue;

				var tint = p.FadeTint ? Lerp(p.Tint, p.TintEnd, Math.Min(1, t * 1.8f)) : p.Tint;
				var angle = p.Angle;
				if (p.Align)
				{
					// Screen-space direction of flight: up on screen is -Y, height adds to it
					var sx = p.VX;
					var sy = p.VY - p.VZ;
					if (sx * sx + sy * sy > 0.0001f)
						angle = MathF.Atan2(sy, sx) * 512f / MathF.PI;
				}

				if (Legacy)
				{
					var z = flat ? FlatZ - offset.Y : zBias - offset.Y;
					yield return new SpriteRenderable(seq.GetSprite(frame), origin + offset, WVec.Zero, z, null,
						seq.Scale * size, alpha, tint, TintModifiers.None, false, new WAngle((int)angle));
					continue;
				}

				(flat ? flatQuads : airQuads).Add(new PxQuad
				{
					Sprite = seq.GetSprite(frame),
					Pos = origin + offset,
					Scale = seq.Scale * size,
					Alpha = alpha,
					Tint = tint,
					Rotation = new WAngle((int)angle).RendererRadians(),
				});
			}

			if (flatQuads.Count > 0)
				yield return new PxParticlesRenderable(flatQuads, origin, FlatZ, WVec.Zero);

			if (airQuads.Count > 0)
				yield return new PxParticlesRenderable(airQuads, origin, zBias, WVec.Zero);
		}
	}
}
