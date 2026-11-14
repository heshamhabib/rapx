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
using System.Reflection;
using OpenRA.Effects;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Fighter aerobatics drawn from the existing top-down sprites (cosmetic only): the jet banks into turns",
		"(the sprite narrows across the wings, the low wing darker), optionally flicks an aileron roll when hit or now and",
		"then in a dogfight (Rolls, off by default), and turns smoothly between its rendered facings.",
		"Put it after PxAltitudeScale and WithShadow so the shadow banks and rolls too.")]
	public class WithPxAerobaticsInfo : ConditionalTraitInfo, Requires<BodyOrientationInfo>
	{
		[Desc("Steepest bank in a hard turn, degrees. Kept shallow: a flat sprite squashed much looks like folded paper.")]
		public readonly int MaxBank = 25;

		[Desc("Flick aileron rolls when hit or in a dogfight. Off: squashing the flat sprite through a full turn looked",
			"like a sheet of paper flipping (user's call, 2026-11-14).")]
		public readonly bool Rolls = false;

		[Desc("Turn rate (WAngle per tick) that gives the steepest bank.")]
		public readonly int FullBankTurn = 20;

		[Desc("Ticks for one full aileron roll.")]
		public readonly int RollTicks = 16;

		[Desc("Chance per second of a roll while enemy aircraft are within DogfightRange.")]
		public readonly float CombatRollChance = 0.18f;

		public readonly WDist DogfightRange = WDist.FromCells(10);

		[Desc("Decoy flares fired per roll under attack.")]
		public readonly int Flares = 6;

		[Desc("Smoothly rotate the sprite between its rendered facings.")]
		public readonly bool SmoothTurns = true;

		public override object Create(ActorInitializer init) { return new WithPxAerobatics(init.Self, this); }
	}

	public class WithPxAerobatics : ConditionalTrait<WithPxAerobaticsInfo>, ITick, IRenderModifier, INotifyDamage
	{
		static readonly FieldInfo SpriteField = typeof(SpriteRenderable).GetField("sprite", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo PosField = typeof(SpriteRenderable).GetField("pos", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo ScaleField = typeof(SpriteRenderable).GetField("scale", BindingFlags.NonPublic | BindingFlags.Instance);

		readonly BodyOrientation body;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		WAngle lastYaw;
		float bank; // radians, + = right wing down
		int rollTick = -1;
		int rollDir = 1;
		int scan;
		bool enemiesNear;
		PxFlareEffect flares;

		public WithPxAerobatics(Actor self, WithPxAerobaticsInfo info)
			: base(info)
		{
			body = self.Trait<BodyOrientation>();
		}

		void StartRoll(Actor self, bool withFlares)
		{
			if (!Info.Rolls)
				return;

			if (rollTick >= 0)
				return;

			rollTick = 0;
			rollDir = rng.Next(2) == 0 ? -1 : 1;
			if (withFlares && Info.Flares > 0)
			{
				if (flares == null || flares.Done)
				{
					flares = new PxFlareEffect(self.CenterPosition);
					var f = flares;
					self.World.AddFrameEndTask(w => w.Add(f));
				}

				var back = new WVec(0, 1024, 0).Rotate(WRot.FromYaw(self.Orientation.Yaw));
				flares.Fire(self.CenterPosition, back, Info.Flares, rng);
			}
		}

		void ITick.Tick(Actor self)
		{
			var yaw = self.Orientation.Yaw;
			var d = (yaw - lastYaw).Angle;
			var turn = d > 512 ? d - 1024 : d;
			lastYaw = yaw;
			if (IsTraitDisabled)
			{
				bank *= 0.8f;
				rollTick = -1;
				return;
			}

			// Bank follows the turn rate, eased in and out (WAngle grows counter-clockwise: a left turn banks left)
			var target = -Math.Clamp((float)turn / Info.FullBankTurn, -1, 1) * Info.MaxBank * MathF.PI / 180;
			bank += (target - bank) * 0.18f;

			if (rollTick >= 0 && ++rollTick > Info.RollTicks)
				rollTick = -1;

			if (--scan <= 0)
			{
				scan = 15;
				enemiesNear = self.World.FindActorsInCircle(self.CenterPosition, Info.DogfightRange)
					.Any(a => a.IsInWorld && a != self && a.Owner.RelationshipWith(self.Owner) == PlayerRelationship.Enemy
						&& a.Info.HasTraitInfo<AircraftInfo>() && self.World.Map.DistanceAboveTerrain(a.CenterPosition).Length > 0);
			}

			if (enemiesNear && rng.NextFloat() < Info.CombatRollChance / 25)
				StartRoll(self, rng.NextFloat() < 0.5f);
		}

		void INotifyDamage.Damaged(Actor self, AttackInfo e)
		{
			if (!IsTraitDisabled && e.Damage.Value > 0 && !self.IsDead)
				StartRoll(self, true);
		}

		IEnumerable<IRenderable> IRenderModifier.ModifyRender(Actor self, WorldRenderer wr, IEnumerable<IRenderable> r)
		{
			if (IsTraitDisabled)
				return r;

			var roll = rollTick >= 0 ? rollDir * 2 * MathF.PI * Smooth((float)rollTick / Info.RollTicks) : 0;
			var angle = bank + roll;
			var squash = MathF.Cos(angle);

			// Smooth turns: the rest of the turn between the rendered facings
			var rot = 0f;
			if (Info.SmoothTurns)
				rot = -(self.Orientation.Yaw - body.QuantizeFacing(self.Orientation.Yaw)).Angle switch
				{
					var a when a > 512 => (a - 1024) * MathF.PI / 512,
					var a => a * MathF.PI / 512,
				};

			if (MathF.Abs(squash - 1) < 0.01f && MathF.Abs(rot) < 0.002f)
				return r;

			// Light: the lowered wing turns from the sun a little; upside down the belly is in shadow
			var shade = squash < 0 ? 0.72f : 1 - 0.12f * MathF.Abs(MathF.Sin(angle));
			var forward = new WVec(0, -1024, 0).Rotate(WRot.FromYaw(self.Orientation.Yaw));
			var fx = forward.X / 1024f;
			var fy = forward.Y / 1024f;
			var wing = new float2(-fy, fx);
			return r.Select(x => x is SpriteRenderable s ? new PxBankedSpriteRenderable(s, (Sprite)SpriteField.GetValue(s),
				(WPos)PosField.GetValue(s), (float)ScaleField.GetValue(s), wing, squash, rot, shade) : x);
		}

		static float Smooth(float t) { t = Math.Clamp(t, 0, 1); return t * t * (3 - 2 * t); }

		IEnumerable<Rectangle> IRenderModifier.ModifyScreenBounds(Actor self, WorldRenderer wr, IEnumerable<Rectangle> bounds)
		{
			return bounds;
		}
	}

	/// <summary>A sprite squashed across the wings (bank / roll) and turned a little, drawn as a palette quad.</summary>
	public class PxBankedSpriteRenderable : IRenderable, IFinalizedRenderable
	{
		readonly SpriteRenderable source;
		readonly Sprite sprite;
		readonly WPos pos;
		readonly float scale;
		readonly float2 wing;
		readonly float squash;
		readonly float rot;
		readonly float shade;

		public PxBankedSpriteRenderable(SpriteRenderable source, Sprite sprite, WPos pos, float scale, float2 wing, float squash,
			float rot, float shade)
		{
			this.source = source;
			this.sprite = sprite;
			this.pos = pos;
			this.scale = scale;
			this.wing = wing;
			this.squash = squash;
			this.rot = rot;
			this.shade = shade;
		}

		public WPos Pos => source.Pos;
		public int ZOffset => source.ZOffset;
		public bool IsDecoration => source.IsDecoration;

		SpriteRenderable Wrap(IRenderable r) { return (SpriteRenderable)r; }

		public IRenderable WithZOffset(int newOffset)
		{
			var s = Wrap(source.WithZOffset(newOffset));
			return new PxBankedSpriteRenderable(s, sprite, pos, scale, wing, squash, rot, shade);
		}

		public IRenderable OffsetBy(in WVec vec)
		{
			var s = Wrap(source.OffsetBy(vec));
			return new PxBankedSpriteRenderable(s, sprite, pos + vec, scale, wing, squash, rot, shade);
		}

		public IRenderable AsDecoration()
		{
			return new PxBankedSpriteRenderable(Wrap(source.AsDecoration()), sprite, pos, scale, wing, squash, rot, shade);
		}

		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		float3 Transform(float3 p, float3 pivot)
		{
			var x = p.X - pivot.X;
			var y = p.Y - pivot.Y;

			// Squash along the wing axis
			var w = x * wing.X + y * wing.Y;
			x += (squash - 1) * w * wing.X;
			y += (squash - 1) * w * wing.Y;

			// Turn about the actor centre
			var c = MathF.Cos(rot);
			var s = MathF.Sin(rot);
			return new float3(pivot.X + x * c - y * s, pivot.Y + x * s + y * c, p.Z);
		}

		public void Render(WorldRenderer wr)
		{
			var pivot = wr.Screen3DPxPosition(pos) + wr.ScreenPxOffset(source.Offset);
			var half = 0.5f * scale * sprite.Size;
			var tl = pivot - new float3((int)half.X, (int)half.Y, half.Z) + scale * sprite.Offset;
			var size = scale * sprite.Size;
			var a = Transform(tl, pivot);
			var b = Transform(new float3(tl.X + size.X, tl.Y, tl.Z), pivot);
			var c = Transform(new float3(tl.X + size.X, tl.Y + size.Y, tl.Z + size.Z), pivot);
			var d = Transform(new float3(tl.X, tl.Y + size.Y, tl.Z + size.Z), pivot);

			var t = source.Alpha * shade * source.Tint;
			if (wr.TerrainLighting != null && (source.TintModifiers & TintModifiers.IgnoreWorldTint) == 0)
				t *= wr.TerrainLighting.TintAt(pos);

			var alpha = source.Alpha;
			if ((source.TintModifiers & TintModifiers.ReplaceColor) != 0)
			{
				alpha *= -1;
				t = source.Alpha * source.Tint; // shadows keep their colour
			}

			Game.Renderer.WorldSpriteRenderer.DrawSprite(sprite, source.Palette, a, b, c, d, t, alpha);
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }

		public Rectangle ScreenBounds(WorldRenderer wr) { return source.ScreenBounds(wr); }
	}

	/// <summary>Decoy flares: white-hot burning balls thrown behind and out, falling slowly with smoke trails.</summary>
	public class PxFlareEffect : IEffect
	{
		const float PixelPerWorld = 24f / 1024f;

		struct Flare
		{
			public float3 P, V;
			public int Age, Life;
		}

		readonly WPos anchor;
		readonly List<Flare> live = new();
		PxParticles particles;
		public bool Done;

		public PxFlareEffect(WPos at)
		{
			anchor = new WPos(at.X, at.Y, 0);
		}

		float3 Local(WPos p)
		{
			return new float3((p.X - anchor.X) * PixelPerWorld, (p.Y - anchor.Y) * PixelPerWorld, p.Z * PixelPerWorld);
		}

		public void Fire(WPos from, WVec back, int count, MersenneTwister rng)
		{
			var p = Local(from);
			var bx = back.X / 1024f;
			var by = back.Y / 1024f;
			for (var i = 0; i < count; i++)
			{
				var side = (i % 2 == 0 ? 1 : -1) * (0.6f + 0.8f * rng.NextFloat());
				live.Add(new Flare
				{
					P = p,
					V = new float3(bx * 1.4f - by * side, by * 1.4f + bx * side, 0.3f + 0.4f * rng.NextFloat()),
					Life = 40 + rng.Next(25),
					Age = -i * 2, // a quick ripple of flares, not all at once
				});
			}
		}

		public void Tick(World world)
		{
			particles ??= new PxParticles(world) { Max = 600 };
			particles.Update(1);
			for (var i = live.Count - 1; i >= 0; i--)
			{
				var f = live[i];
				f.Age++;
				if (f.Age > 0)
				{
					f.V = new float3(f.V.X * 0.95f, f.V.Y * 0.95f, f.V.Z - 0.04f);
					f.P += f.V;
					var t = (float)f.Age / f.Life;
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Glow, X = f.P.X, Y = f.P.Y, Z = f.P.Z, Life = 2,
						Size = 0.35f * (1 - 0.5f * t), Alpha = 1, Tint = new float3(1f, 0.95f, 0.8f),
					});
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Smoke, X = f.P.X, Y = f.P.Y, Z = f.P.Z, Life = 45, Drag = 0.02f, VX = 0.04f,
						Size = 0.12f, Grow = 2.2f, Alpha = 0.45f * (1 - t), Tint = new float3(0.95f, 0.95f, 0.95f),
						Angle = f.Age * 97 % 1024,
					});
				}

				if (f.Age >= f.Life)
					live.RemoveAt(i);
				else
					live[i] = f;
			}

			if (live.Count == 0 && particles.Items.Count == 0)
			{
				Done = true;
				world.AddFrameEndTask(w => w.Remove(this));
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			return particles == null ? Enumerable.Empty<IRenderable>() : particles.Render(anchor, 1024, p => wr.World.FogObscures(p));
		}
	}
}
