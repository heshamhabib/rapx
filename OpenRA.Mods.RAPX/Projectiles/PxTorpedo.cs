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
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Projectiles
{
	[Desc("High-definition torpedo: a dark shape running just under the surface, homing on its target, with a white",
		"foam wake (pxfx foam, artsrc/fx/make_water_fx.py) spreading out in a V behind it and lingering after the hit.",
		"Explodes when it reaches the target, runs out of range or leaves the terrain type it is bound to.")]
	public class PxTorpedoInfo : IProjectileInfo
	{
		[Desc("Speed per tick.")]
		public readonly WDist Speed = new(85);

		[Desc("How fast it can turn towards its target per tick.")]
		public readonly WAngle TurnRate = new(16);

		[Desc("Explode after travelling this far. Zero = 1.25 x the weapon's range.")]
		public readonly WDist RangeLimit = WDist.Zero;

		[Desc("Explode when entering a cell of another terrain type (e.g. hitting the shore).")]
		public readonly string BoundToTerrainType = "Water";

		[Desc("Length of the torpedo shape.")]
		public readonly WDist Length = new(200);

		[Desc("Width of the torpedo shape.")]
		public readonly WDist Width = new(44);

		[Desc("Colour of the submerged torpedo.")]
		public readonly Color BodyColor = Color.FromArgb(150, 12, 24, 32);

		[Desc("Foam patches emitted per tick on each side of the wake.")]
		public readonly int WakeDensity = 1;

		[Desc("How long the wake foam lingers, in ticks.")]
		public readonly int WakeLife = 75;

		[Desc("Equivalent to sequence ZOffset. The wake lies on the water, under the ships.")]
		public readonly int ZOffset = -16384;

		public IProjectile Create(ProjectileArgs args) { return new PxTorpedo(this, args); }
	}

	public class PxTorpedo : IProjectile, ISync
	{
		const float PixelPerWorld = 24f / 1024f;

		readonly PxTorpedoInfo info;
		readonly ProjectileArgs args;
		readonly WPos origin;
		readonly int rangeLimit;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		PxParticles particles;
		int travelled;
		int ticks;
		bool exploded;
		int lingering;

		[Sync]
		WPos pos;

		[Sync]
		WAngle facing;

		WPos target;
		WPos lastPos;

		public PxTorpedo(PxTorpedoInfo info, ProjectileArgs args)
		{
			this.info = info;
			this.args = args;
			origin = args.Source;
			pos = lastPos = args.Source;
			target = args.PassiveTarget;
			var d = target - origin;
			facing = d.HorizontalLengthSquared > 0 ? d.Yaw : args.Facing;
			rangeLimit = info.RangeLimit != WDist.Zero ? info.RangeLimit.Length : args.Weapon.Range.Length * 5 / 4;
		}

		float3 Local(WPos p)
		{
			return new float3((p.X - origin.X) * PixelPerWorld, (p.Y - origin.Y) * PixelPerWorld, 0);
		}

		void Foam(float3 at, float vx, float vy, float size, float life, float alpha)
		{
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Foam,
				X = at.X + (rng.NextFloat() - 0.5f) * 1.5f,
				Y = at.Y + (rng.NextFloat() - 0.5f) * 1.5f,
				VX = vx,
				VY = vy,
				Drag = 0.035f,
				Life = life * (0.75f + 0.5f * rng.NextFloat()),
				Size = size * (0.8f + 0.4f * rng.NextFloat()),
				Grow = 1.5f,
				Alpha = alpha,
				Tint = new float3(0.95f, 0.98f, 1f),
				Frame = rng.Next(Math.Max(1, particles.FrameCount(PxParticleKind.Foam))),
			});
		}

		void Explode(WPos at)
		{
			args.Weapon.Impact(Target.FromPos(at), new WarheadArgs(args) { ImpactPosition = at });
			exploded = true;
			lingering = info.WakeLife * 2;
		}

		public void Tick(World world)
		{
			particles ??= new PxParticles(world);
			particles.Update(1);

			if (exploded)
			{
				if (--lingering <= 0 || particles.Items.Count == 0)
					world.AddFrameEndTask(w => w.Remove(this));

				return;
			}

			if (ticks++ == 0)
			{
				// Launch: churned water bursting out of the tube
				var at = Local(origin);
				for (var i = 0; i < 6; i++)
				{
					var a = rng.NextFloat() * MathF.PI * 2;
					Foam(at, MathF.Cos(a) * 0.3f, MathF.Sin(a) * 0.3f, 0.45f, info.WakeLife * 0.6f, 0.75f);
				}
			}

			if (args.GuidedTarget.IsValidFor(args.SourceActor))
				target = args.GuidedTarget.CenterPosition;

			var toTarget = target - pos;
			if (toTarget.HorizontalLength <= info.Speed.Length)
			{
				lastPos = pos;
				pos = new WPos(target.X, target.Y, pos.Z);
				Explode(pos);
				return;
			}

			// Steer towards the target, limited by the turn rate
			var turn = (toTarget.Yaw - facing).Angle;
			if (turn > 512)
				turn -= 1024;

			facing += new WAngle(Math.Clamp(turn, -info.TurnRate.Angle, info.TurnRate.Angle));

			lastPos = pos;
			pos += new WVec(0, -info.Speed.Length, 0).Rotate(WRot.FromYaw(facing));
			travelled += info.Speed.Length;

			var cell = world.Map.CellContaining(pos);
			if (travelled >= rangeLimit || !world.Map.Contains(cell) ||
				(!string.IsNullOrEmpty(info.BoundToTerrainType) && world.Map.GetTerrainInfo(cell).Type != info.BoundToTerrainType))
			{
				Explode(pos);
				return;
			}

			// Wake: foam pushed out to both sides (a V behind the torpedo) and a bright churn at its tail
			var here = Local(pos);
			var back = Local(lastPos);
			var dx = here.X - back.X;
			var dy = here.Y - back.Y;
			var len = MathF.Max(0.01f, MathF.Sqrt(dx * dx + dy * dy));
			var nx = -dy / len;
			var ny = dx / len;
			for (var i = 0; i < info.WakeDensity; i++)
			{
				var f = (float)(i + 1) / info.WakeDensity;
				var at = new float3(back.X + dx * f, back.Y + dy * f, 0);
				for (var side = -1; side <= 1; side += 2)
				{
					var s = side * (0.12f + 0.12f * rng.NextFloat());
					Foam(at, nx * s - dx / len * 0.04f, ny * s - dy / len * 0.04f, 0.32f, info.WakeLife, 0.6f);
				}
			}

			Foam(back, 0, 0, 0.26f, info.WakeLife * 0.35f, 0.85f);
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			if (particles != null)
				foreach (var r in particles.Render(new WPos(origin.X, origin.Y, 0), info.ZOffset, p => wr.World.FogObscures(p)))
					yield return r;

			if (!exploded && !wr.World.FogObscures(pos))
				yield return new PxTorpedoRenderable(info, pos, lastPos);
		}
	}

	public class PxTorpedoRenderable : IRenderable, IFinalizedRenderable
	{
		readonly PxTorpedoInfo info;
		readonly WPos last;

		public PxTorpedoRenderable(PxTorpedoInfo info, WPos pos, WPos last)
		{
			this.info = info;
			Pos = pos;
			this.last = last;
		}

		public WPos Pos { get; }
		public int ZOffset => info.ZOffset + 1;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxTorpedoRenderable(info, Pos + vec, last + vec); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		static Color Alpha(Color c, float a) { return Color.FromArgb((int)Math.Clamp(c.A * a, 0, 255), c.R, c.G, c.B); }

		public void Render(WorldRenderer wr)
		{
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			var head = wr.Screen3DPosition(Pos);
			var prev = wr.Screen3DPosition(last);
			var d = head - prev;
			var len = (float)Math.Sqrt(d.X * d.X + d.Y * d.Y);
			var dir = len > 0.01f ? new float3(d.X / len, d.Y / len, 0) : new float3(1, 0, 0);

			var bodyLen = wr.ScreenVector(new WVec(info.Length, WDist.Zero, WDist.Zero))[0];
			var w = Math.Max(1.5f, wr.ScreenVector(new WVec(info.Width, WDist.Zero, WDist.Zero))[0]);
			var tail = head - bodyLen * dir;

			// A dark, soft-edged shape seen through the water, with a faint glint along its back
			cr.DrawLine(tail, head, w * 1.8f, Alpha(info.BodyColor, 0.35f));
			cr.DrawLine(tail + w * 0.2f * dir, head - w * 0.2f * dir, w, info.BodyColor);
			cr.DrawLine(tail + bodyLen * 0.3f * dir, head - bodyLen * 0.15f * dir, Math.Max(1, w * 0.25f), Color.FromArgb(40, 200, 230, 240));
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
