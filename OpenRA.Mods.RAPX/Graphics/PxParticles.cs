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

namespace OpenRA.Mods.RAPX.Graphics
{
	public enum PxParticleKind { Smoke, Spark, Glow, Flame, Chunk, Ring, Plume, Fireball, Billow, Foam }

	/// <summary>One cosmetic particle. Positions are in screen pixels relative to the emitter's origin:
	/// X/Y on the ground plane, Z = height above it (drawn upwards).</summary>
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
	}

	/// <summary>
	/// Tiny particle simulation for building effects (smoke, sparks, flames, debris).
	/// Purely cosmetic: advanced with real frame time, never touches the synced simulation.
	/// Sprites come from the `pxfx` image (artsrc/fx/make_fx.py).
	/// </summary>
	public class PxParticles
	{
		public const string Image = "pxfx";

		// World units per screen pixel (1024 per 24 pixel cell)
		const float WorldPerPixel = 1024f / 24f;

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
		};

		public readonly List<PxParticle> Items = new();

		/// <summary>Most particles alive at once; extra ones are dropped.</summary>
		public int Max = 400;
		readonly Dictionary<PxParticleKind, ISpriteSequence> sequences = new();
		readonly SequenceSet sequenceSet;

		public PxParticles(World world)
		{
			sequenceSet = world.Map.Sequences;
		}

		public ISpriteSequence Sequence(string name)
		{
			return sequenceSet.GetSequence(Image, name);
		}

		ISpriteSequence Sequence(PxParticleKind kind)
		{
			if (!sequences.TryGetValue(kind, out var s))
				sequences[kind] = s = sequenceSet.GetSequence(Image, SequenceNames[kind]);

			return s;
		}

		public int FrameCount(PxParticleKind kind) { return Sequence(kind).Length; }

		public void Add(PxParticle p)
		{
			// Keep busy emitters bounded
			if (Items.Count < Max)
				Items.Add(p);
		}

		/// <summary>Advance by dt game ticks (fractional).</summary>
		public void Update(float dt)
		{
			for (var i = Items.Count - 1; i >= 0; i--)
			{
				var p = Items[i];
				p.Age += dt;
				if (p.Age >= p.Life)
				{
					Items.RemoveAt(i);
					continue;
				}

				var drag = p.Drag > 0 ? MathF.Pow(1 - p.Drag, dt) : 1;
				p.VX *= drag;
				p.VY *= drag;
				p.VZ = p.VZ * drag - p.Gravity * dt;
				p.X += p.VX * dt;
				p.Y += p.VY * dt;
				p.Z += p.VZ * dt;
				p.Angle += p.Spin * dt;

				// Debris and sparks bounce once on the ground and then settle
				if (p.Z < 0 && p.Gravity > 0)
				{
					p.Z = 0;
					p.VZ = -p.VZ * 0.3f;
					p.VX *= 0.5f;
					p.VY *= 0.5f;
					p.Spin *= 0.5f;
					if (p.VZ < 0.3f)
					{
						p.VZ = 0;
						p.Gravity = 0;
						p.VX = p.VY = p.Spin = 0;
					}
				}

				Items[i] = p;
			}
		}

		public static WVec ToWorld(float x, float y)
		{
			return new WVec((int)(x * WorldPerPixel), (int)(y * WorldPerPixel), 0);
		}

		/// <summary>Renders all particles around origin. Every particle sorts at origin.Y + zBias, so emitter effects
		/// stay on top of their building regardless of how high above it they are. Particles over a cell for which hidden
		/// returns true (e.g. fog) are skipped.</summary>
		public IEnumerable<IRenderable> Render(WPos origin, int zBias, Func<WPos, bool> hidden = null)
		{
			foreach (var p in Items)
			{
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
					case PxParticleKind.Billow:
						// Detailed smoke: builds up behind the flames, then thins out as it spreads
						alpha = Math.Min(t * 3, 1) * (1 - t) * (1 - t * 0.3f);
						break;
					case PxParticleKind.Foam:
						// Foam on water (artsrc/fx/make_water_fx.py): appears at once, then slowly breaks up
						alpha = Math.Min(t * 10, 1) * MathF.Pow(1 - t, 1.5f);
						break;
					case PxParticleKind.Chunk:
						alpha = t < 0.8f ? 1 : (1 - t) / 0.2f;
						break;
					case PxParticleKind.Ring:
						alpha = 1 - t;
						frame = Math.Min((int)(t * seq.Length), seq.Length - 1);
						break;
					default:
						alpha = 1 - t;
						break;
				}

				alpha *= p.Alpha;
				if (alpha <= 0.01f)
					continue;

				var size = p.Size * (1 + p.Grow * t);
				var offset = ToWorld(p.X, p.Y - p.Z);
				if (hidden != null && hidden(origin + ToWorld(p.X, p.Y)))
					continue;

				yield return new SpriteRenderable(seq.GetSprite(frame), origin + offset, WVec.Zero, zBias - offset.Y, null,
					seq.Scale * size, alpha, p.Tint, TintModifiers.None, false, new WAngle((int)p.Angle));
			}
		}
	}
}
