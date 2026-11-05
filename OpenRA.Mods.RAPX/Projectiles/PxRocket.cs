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
	[Desc("High-definition rocket: a drawn rocket body with a white-hot exhaust flame flying an arc to its target, a launch",
		"blast, and a thick HD smoke trail (pxfx particles) that billows, drifts and lingers after the impact.")]
	public class PxRocketInfo : IProjectileInfo
	{
		[Desc("Flight speed per tick.")]
		public readonly WDist Speed = new(220);

		[Desc("Draw this image's sequence (32 facings) as the missile instead of the drawn rocket body; the exhaust flame",
			"and smoke trail stay. Used by the jet weapons (rendered missiles, artsrc/jets/render_missiles.py).")]
		public readonly string Image = null;

		public readonly string Sequence = "idle";

		[Desc("Sequence of Image drawn while climbing steeply (nose up), e.g. a rocket just off its launch rail.",
			"Empty = always use Sequence.")]
		public readonly string ClimbSequence = null;

		[Desc("Sequence of Image drawn while diving steeply (nose down) onto the target. Empty = always use Sequence.")]
		public readonly string DiveSequence = null;

		[Desc("Slope (height gained per distance flown) beyond which ClimbSequence / DiveSequence is used.")]
		public readonly float AttitudeSlope = 0.36f;

		[Desc("0 = constant speed; up to 1 = leaves the launcher slowly and speeds up (a heavy rocket off its rail).")]
		public readonly float LaunchEase = 0f;

		[Desc("Height of the flight arc, as a fraction of the distance.")]
		public readonly float Arc = 0.12f;

		[Desc("Follow the targeted actor while flying.")]
		public readonly bool TrackTarget = true;

		[Desc("The maximum/constant/incremental inaccuracy used in conjunction with the InaccuracyType property.",
			"A missed rocket keeps its offset while tracking, so a salvo spreads over the target area.")]
		public readonly WDist Inaccuracy = WDist.Zero;

		[Desc("Controls the way inaccuracy is calculated. Possible values are " +
			"'Maximum' - scale from 0 to max with range, " +
			"'PerCellIncrement' - scale from 0 with range, " +
			"'Absolute' - use set value regardless of range.")]
		public readonly OpenRA.Mods.Common.InaccuracyType InaccuracyType = OpenRA.Mods.Common.InaccuracyType.Maximum;

		[Desc("Length of the rocket body.")]
		public readonly WDist Length = new(150);

		[Desc("Width of the rocket body.")]
		public readonly WDist Width = new(36);

		[Desc("Rocket body colour.")]
		public readonly Color BodyColor = Color.FromArgb(255, 70, 76, 82);

		[Desc("Nose / band colour.")]
		public readonly Color NoseColor = Color.FromArgb(255, 220, 220, 210);

		[Desc("Exhaust flame colour.")]
		public readonly Color FlameColor = Color.FromArgb(255, 255, 170, 60);

		[Desc("Trail and launch smoke colour (a white-hot solid motor gives pale smoke, a thermobaric or old motor darker).")]
		public readonly Color SmokeColor = Color.FromArgb(255, 217, 217, 217);

		[Desc("Size of the trail smoke puffs, as a multiple of the default.")]
		public readonly float TrailSize = 1f;

		[Desc("Length and size of the exhaust flame, as a multiple of the default.")]
		public readonly float FlameSize = 1f;

		[Desc("Smoke puffs emitted per tick of flight.")]
		public readonly int TrailDensity = 2;

		[Desc("How long trail smoke lingers, in ticks.")]
		public readonly int TrailLife = 45;

		[Desc("Smoke puffs in the launch blast.")]
		public readonly int LaunchPuffs = 10;

		[Desc("Launched from under water (missile submarine): the launch blast is a burst of foam, spray and steam.")]
		public readonly bool WaterLaunch = false;

		[Desc("Equivalent to sequence ZOffset. Controls Z sorting.")]
		public readonly int ZOffset = 1024;

		public IProjectile Create(ProjectileArgs args) { return new PxRocket(this, args); }
	}

	public class PxRocket : IProjectile, ISync
	{
		const float PixelPerWorld = 24f / 1024f;

		readonly PxRocketInfo info;
		readonly ProjectileArgs args;
		readonly WPos origin;
		readonly int flightTicks;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		PxParticles particles;
		int ticks;
		bool exploded;
		int lingering;

		[Sync]
		WPos target;

		[Sync]
		WPos pos;

		WPos lastPos;

		readonly WVec miss;

		public PxRocket(PxRocketInfo info, ProjectileArgs args)
		{
			this.info = info;
			this.args = args;
			origin = args.Source;
			pos = lastPos = args.Source;
			target = args.PassiveTarget;
			if (info.Inaccuracy.Length > 0)
			{
				var maxInaccuracyOffset = OpenRA.Mods.Common.Util.GetProjectileInaccuracy(info.Inaccuracy.Length, info.InaccuracyType, args);
				miss = WVec.FromPDF(args.SourceActor.World.SharedRandom, 2) * maxInaccuracyOffset / 1024;
				target += miss;
			}

			flightTicks = Math.Max(4, (target - origin).Length / Math.Max(1, info.Speed.Length));

			// One step "behind" the launcher, so the first frame already faces the target
			lastPos = origin - (target - origin) / flightTicks;
		}

		/// <summary>Still flying (not yet exploded or shot down): point defence (PxPointDefense) can engage it.</summary>
		public bool InFlight => !exploded && ticks > 0;

		public WPos Position => pos;

		/// <summary>Where it will hit.</summary>
		public WPos TargetPosition => target;

		/// <summary>The player who fired it (null if unknown).</summary>
		public Player Owner => args.SourceActor?.Owner;

		/// <summary>Shot down by point defence: bursts in the air without hitting anything.</summary>
		public void Intercept()
		{
			if (exploded)
				return;

			exploded = true;
			lingering = info.TrailLife * 2;
			if (particles == null)
				return;

			var at = Local(pos);
			Puff(PxParticleKind.Glow, at, 2, 1.1f, 8, 1f, new float3(1f, 0.85f, 0.5f), 0);
			for (var i = 0; i < 6; i++)
				Puff(PxParticleKind.Flame, at, 6, 0.4f, 9, 0.95f, new float3(1f, 0.7f, 0.35f), 0.05f);

			for (var i = 0; i < 10; i++)
				Puff(PxParticleKind.Smoke, at, 9, 0.5f, info.TrailLife, 0.75f, new float3(0.55f, 0.55f, 0.55f), 0.1f);
		}

		/// <summary>The exhaust colour, lightened towards white-hot, as a particle tint.</summary>
		float3 FlameTint => new((info.FlameColor.R + 255) / 510f, (info.FlameColor.G + 255) / 510f, (info.FlameColor.B + 255) / 510f);

		float3 Local(WPos p)
		{
			return new float3((p.X - origin.X) * PixelPerWorld, (p.Y - origin.Y) * PixelPerWorld, p.Z * PixelPerWorld);
		}

		void Puff(PxParticleKind kind, float3 at, float spread, float size, float life, float alpha, float3 tint, float rise)
		{
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = at.X + (rng.NextFloat() - 0.5f) * spread,
				Y = at.Y + (rng.NextFloat() - 0.5f) * spread * 0.6f,
				Z = at.Z + (rng.NextFloat() - 0.5f) * spread * 0.4f,
				VX = (rng.NextFloat() - 0.5f) * 0.25f + 0.08f,
				VY = (rng.NextFloat() - 0.5f) * 0.15f,
				VZ = rise * (0.5f + rng.NextFloat()),
				Drag = 0.04f,
				Life = life * (0.75f + 0.5f * rng.NextFloat()),
				Size = size * (0.8f + 0.4f * rng.NextFloat()),
				Grow = 1.6f,
				Alpha = alpha,
				Tint = tint,
				Frame = rng.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = (rng.NextFloat() - 0.5f) * 4,
				Angle = rng.Next(1024),
			});
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

			var grey = new float3(info.SmokeColor.R / 255f, info.SmokeColor.G / 255f, info.SmokeColor.B / 255f);
			if (ticks == 0)
			{
				// Launch blast: a burst of smoke and a hot glow at the pod
				var at = Local(origin);
				for (var i = 0; i < info.LaunchPuffs; i++)
					Puff(PxParticleKind.Smoke, at, 10 * info.TrailSize, 0.55f * info.TrailSize, info.TrailLife * 0.8f, 0.8f, grey, 0.15f);

				Puff(PxParticleKind.Glow, at, 2, 0.7f * info.FlameSize, 6, 1f, FlameTint, 0);
				if (info.WaterLaunch)
				{
					var white = new float3(1f, 1f, 1f);
					for (var i = 0; i < 10; i++)
					{
						Puff(PxParticleKind.Foam, at, 8, 0.5f, info.TrailLife, 0.8f, white, 0);
						Puff(PxParticleKind.Smoke, at, 6, 0.45f, info.TrailLife * 0.5f, 0.6f, white, 0.35f);
					}
				}
			}

			if (info.TrackTarget && args.GuidedTarget.IsValidFor(args.SourceActor))
				target = args.GuidedTarget.CenterPosition + miss;

			ticks++;
			var t = Math.Min(1f, (float)ticks / flightTicks);
			var u = t + info.LaunchEase * (t * t - t);
			var dist = (target - origin).Length;
			var height = (int)(Math.Sin(u * Math.PI) * dist * info.Arc);
			lastPos = pos;
			pos = WPos.Lerp(origin, target, (int)(u * 1024), 1024) + new WVec(0, 0, height);

			// Trail: fresh smoke behind the rocket and a short-lived flame glow
			var here = Local(pos);
			var back = Local(lastPos);
			for (var i = 0; i < info.TrailDensity; i++)
			{
				var f = (float)(i + 1) / info.TrailDensity;
				var at = new float3(back.X + (here.X - back.X) * f, back.Y + (here.Y - back.Y) * f, back.Z + (here.Z - back.Z) * f);
				Puff(PxParticleKind.Smoke, at, 3 * info.TrailSize, 0.32f * info.TrailSize, info.TrailLife, 0.7f, grey, 0.05f);
			}

			Puff(PxParticleKind.Flame, back, 1, 0.22f * info.FlameSize, 5, 0.9f, FlameTint, 0);

			if (u >= 1)
			{
				args.Weapon.Impact(Target.FromPos(target), new WarheadArgs(args) { ImpactPosition = target });
				exploded = true;
				lingering = info.TrailLife * 2;
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			if (particles != null)
				foreach (var r in particles.Render(new WPos(origin.X, origin.Y, 0), info.ZOffset))
					yield return r;

			if (!exploded && !wr.World.FogObscures(pos))
			{
				var sprite = info.Image != null;
				yield return new PxRocketRenderable(info, pos, lastPos, !sprite);
				if (sprite)
				{
					var d = pos - lastPos;
					var slope = d.Z / Math.Max(1f, (float)Math.Sqrt(d.HorizontalLengthSquared));
					var name = slope > info.AttitudeSlope && info.ClimbSequence != null ? info.ClimbSequence
						: slope < -info.AttitudeSlope && info.DiveSequence != null ? info.DiveSequence : info.Sequence;
					var seq = wr.World.Map.Sequences.GetSequence(info.Image, name);
					var yaw = d.HorizontalLengthSquared > 0 ? d.Yaw : WAngle.Zero;
					yield return new SpriteRenderable(seq.GetSprite(0, yaw), pos, WVec.Zero, info.ZOffset + 1, null,
						seq.Scale, 1f, float3.Ones, TintModifiers.None, true);
				}
			}
		}
	}

	public class PxRocketRenderable : IRenderable, IFinalizedRenderable
	{
		readonly PxRocketInfo info;
		readonly WPos last;
		readonly bool body;

		public PxRocketRenderable(PxRocketInfo info, WPos pos, WPos last, bool body = true)
		{
			this.info = info;
			Pos = pos;
			this.last = last;
			this.body = body;
		}

		public WPos Pos { get; }
		public int ZOffset => info.ZOffset;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxRocketRenderable(info, Pos + vec, last + vec, body); }
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
			var normal = new float3(-dir.Y, dir.X, 0);

			var bodyLen = wr.ScreenVector(new WVec(info.Length, WDist.Zero, WDist.Zero))[0];
			var w = Math.Max(1.5f, wr.ScreenVector(new WVec(info.Width, WDist.Zero, WDist.Zero))[0]);
			var tail = head - bodyLen * dir;

			// Exhaust: a flickering flame cone with a glow, hottest at the nozzle
			var flick = 0.8f + 0.2f * Game.CosmeticRandom.NextFloat();
			var flameEnd = tail - bodyLen * 0.9f * info.FlameSize * flick * dir;
			cr.DrawLine(tail, flameEnd, w * 3.2f, Alpha(info.FlameColor, 0.25f));
			cr.DrawLine(tail, flameEnd, w * 1.6f, Alpha(info.FlameColor, 0.7f));
			cr.DrawLine(tail, tail - bodyLen * 0.45f * dir, w * 0.8f, Color.FromArgb(255, 255, 250, 225));
			var g = w * 2.6f;
			cr.FillEllipse(tail - new float3(g, g * 0.75f, 0), tail + new float3(g, g * 0.75f, 0), Alpha(info.FlameColor, 0.35f * flick));

			if (!body)
				return;

			// Body, fins and a light nose
			var finRoot = tail + bodyLen * 0.2f * dir;
			cr.DrawLine(finRoot, tail - w * 0.9f * normal - w * 0.5f * dir, Math.Max(1, w * 0.45f), info.BodyColor);
			cr.DrawLine(finRoot, tail + w * 0.9f * normal - w * 0.5f * dir, Math.Max(1, w * 0.45f), info.BodyColor);
			cr.DrawLine(tail, head, w, info.BodyColor);
			cr.DrawLine(tail + w * 0.25f * normal, head - bodyLen * 0.2f * dir + w * 0.25f * normal, Math.Max(1, w * 0.3f), Alpha(Color.White, 0.25f));
			cr.DrawLine(head - bodyLen * 0.22f * dir, head, w * 0.9f, info.NoseColor);
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
