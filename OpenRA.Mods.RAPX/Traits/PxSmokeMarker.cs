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
using OpenRA.Activities;
using OpenRA.Graphics;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Red Smoke \"Danger Close\" (IDEA-46): a smoke canister on the ground that marks a target for all of its owner's",
		"support. After WarningTicks every idle long-range gun, rocket launcher and ship in range of the smoke fires on it,",
		"and up to MaxAircraft idle attack aircraft fly in. The cloud drifts with the weather wind (PxWeatherManager.SyncedWind),",
		"and the fire aims at the cloud, not the canister. Everyone sees the smoke, so the enemy gets a warning too.",
		"When the canister is spent the support stops firing, and a dye stain stays on the ground for StainTicks.",
		"Sprites: `pxsmoke` and `pxfx csmoke` (artsrc/fx/make_smoke_fx.py). Spawned at the exact point of impact by",
		"PxSpawnActor (Exact: true).")]
	public class PxSmokeMarkerInfo : TraitInfo
	{
		[Desc("Colour of fresh smoke at the nozzle.")]
		public readonly Color Color = Color.FromArgb(238, 52, 38);

		[Desc("Colour the smoke thins out to.")]
		public readonly Color FadeColor = Color.FromArgb(255, 150, 132);

		[Desc("Colour of the burning composition in the vent and the hot smoke right at it.")]
		public readonly Color VentColor = Color.FromArgb(255, 150, 48);

		[Desc("How long the canister pours out smoke (and the support keeps firing), in ticks.")]
		public readonly int SmokeTicks = 500;

		[Desc("Delay before the support opens fire: the time the enemy has to get out.")]
		public readonly int WarningTicks = 100;

		[Desc("How long the dye stain stays on the ground after the smoke is gone.")]
		public readonly int StainTicks = 1500;

		[Desc("How often the support re-aims at the drifting cloud and idle units join the fire mission.")]
		public readonly int RetargetInterval = 50;

		[Desc("How far the cloud's centre drifts from the canister in calm air ...")]
		public readonly WDist CalmDrift = new(512);

		[Desc("... and in a gale (PxWeatherManager wind strength 1000).")]
		public readonly WDist GaleDrift = new(3072);

		[Desc("Ticks for the cloud to drift its full distance.")]
		public readonly int DriftTicks = 200;

		[Desc("Ground units and defences answer only with weapons that reach at least this far (artillery, rockets, ships).")]
		public readonly WDist MinSupportRange = new(6144);

		[Desc("Call idle attack aircraft too.")]
		public readonly bool CallAircraft = true;

		[Desc("Aircraft this far from the smoke can be called.")]
		public readonly WDist AircraftRadius = new(40960);

		[Desc("Most aircraft one smoke calls in.")]
		public readonly int MaxAircraft = 4;

		[Desc("Played where the canister lands.")]
		public readonly string LandSound = "ra|audio/sfx/smokehiss.ogg";

		[Desc("Played to the owner when the fire mission starts.")]
		public readonly string FireMissionSound = "ra|audio/ui/bleep9.ogg";

		[FluentReference]
		[Desc("Shown to the owner when support opens fire on the smoke.")]
		public readonly string FireMissionNotification = "notification-red-smoke-fire-mission";

		[FluentReference]
		[Desc("Shown to the owner when nothing can reach the smoke.")]
		public readonly string NoSupportNotification = "notification-red-smoke-no-support";

		[FluentReference]
		[Desc("Shown to enemies who have units or buildings near the smoke.")]
		public readonly string SpottedNotification = "notification-red-smoke-spotted";

		[Desc("Enemies with anything this close to the smoke get the warning.")]
		public readonly WDist WarnRadius = new(10240);

		public override object Create(ActorInitializer init) { return new PxSmokeMarker(init, this); }
	}

	public class PxSmokeMarker : ITick, ITickRender, IRender, INotifyAddedToWorld, INotifyRemovedFromWorld
	{
		// Screen pixels per world unit (24 per 1024 cell) and the vent's offset from the canister's centre
		const float PixelsPerWorld = 24f / 1024f;
		const int ZBias = 1536;
		const int FlatZ = -1024;
		static readonly float2 Vent = new(4.5f, 1.5f);
		static readonly float2 Jet = new(1.5f, 0.55f);

		sealed class Mission
		{
			public Actor Actor;
			public AttackBase Attack;
			public Activity Activity;
			public WPos Aim;
			public bool Aircraft;
		}

		readonly PxSmokeMarkerInfo info;
		readonly WPos origin;
		readonly List<Mission> missions = new();
		PxWeatherManager weather;
		WVec windDirection = new(1024, 0, 0);
		int windStrength = 150;
		int age;
		WPos aim;

		// Cosmetic
		readonly PxParticles particles;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly ISpriteSequence can, stain, reticle, glow, light;
		readonly int stainFrame;
		readonly float3 color, fade, vent;
		float emit;
		bool burst = true;
		long lastTime = -1;

		public PxSmokeMarker(ActorInitializer init, PxSmokeMarkerInfo info)
		{
			this.info = info;
			var world = init.World;
			origin = init.GetValue<CenterPositionInit, WPos>(world.Map.CenterOfCell(init.GetValue<LocationInit, CPos>()));
			aim = origin;

			particles = new PxParticles(world) { Max = 360 };
			var sequences = world.Map.Sequences;
			can = sequences.GetSequence("pxsmoke", "can");
			stain = sequences.GetSequence("pxsmoke", "stain");
			reticle = sequences.GetSequence("pxsmoke", "reticle");
			glow = particles.Sequence("glow");
			light = particles.Sequence("xlight");
			stainFrame = random.Next(stain.Length);
			color = ToFloat3(info.Color);
			fade = ToFloat3(info.FadeColor);
			vent = ToFloat3(info.VentColor);
		}

		static float3 ToFloat3(Color c) { return new float3(c.R / 255f, c.G / 255f, c.B / 255f); }

		void INotifyAddedToWorld.AddedToWorld(Actor self)
		{
			var manager = self.World.WorldActor.TraitOrDefault<PxWeatherManager>();
			weather = manager;
			UpdateAim();

			Game.Sound.Play(SoundType.World, info.LandSound, origin);

			// Purely local: warn the player watching if the smoke is near anything of theirs
			var local = self.World.LocalPlayer;
			if (local != null && local.RelationshipWith(self.Owner) == PlayerRelationship.Enemy &&
				self.World.FindActorsInCircle(origin, info.WarnRadius).Any(a => a.Owner == local))
				TextNotificationsManager.AddTransientLine(local, info.SpottedNotification);
		}

		void INotifyRemovedFromWorld.RemovedFromWorld(Actor self) { Release(); }

		bool Smoking => age < info.SmokeTicks;

		void ITick.Tick(Actor self)
		{
			age++;
			UpdateAim();

			if (age == info.WarningTicks)
				CallFire(self, true);
			else if (age > info.WarningTicks && Smoking && (age - info.WarningTicks) % info.RetargetInterval == 0)
				CallFire(self, false);

			if (age == info.SmokeTicks)
				Release();

			if (age == info.SmokeTicks + info.StainTicks)
				self.World.AddFrameEndTask(w =>
				{
					if (!self.Disposed)
						self.Dispose();
				});
		}

		/// <summary>The cloud's centre: the canister plus a drift down the wind that builds up over DriftTicks.</summary>
		void UpdateAim()
		{
			if (weather != null)
				(windDirection, windStrength) = weather.SyncedWind();

			var calm = info.CalmDrift.Length;
			var drift = calm + (info.GaleDrift.Length - calm) * windStrength / 1000;
			var ramp = Math.Min(age, info.DriftTicks);
			var reach = (long)drift * ramp / Math.Max(1, info.DriftTicks);
			aim = origin + new WVec((int)(windDirection.X * reach / 1024), (int)(windDirection.Y * reach / 1024), 0);
		}

		static bool Running(Mission m)
		{
			if (m.Actor.IsDead || !m.Actor.IsInWorld || m.Activity.IsCanceling)
				return false;

			for (var a = m.Actor.CurrentActivity; a != null; a = a.NextActivity)
				if (a == m.Activity)
					return true;

			return false;
		}

		void CallFire(Actor self, bool first)
		{
			var world = self.World;
			var target = Target.FromPos(aim);

			// Ground support already on the smoke follows the drifting cloud; aircraft finish the run they started
			missions.RemoveAll(m => !Running(m));
			foreach (var m in missions)
			{
				if (m.Aircraft || (m.Aim - aim).HorizontalLengthSquared < 256 * 256 || !InRange(m.Actor, m.Attack, target))
					continue;

				Issue(m, target);
			}

			var aircraft = missions.Count(m => m.Aircraft);
			var aircraftRange = info.AircraftRadius.LengthSquared;
			var seen = new HashSet<Actor>(missions.Select(m => m.Actor));
			foreach (var p in world.ActorsWithTrait<AttackBase>())
			{
				var a = p.Actor;
				var attack = p.Trait;
				if (a.Owner != self.Owner || a.IsDead || !a.IsInWorld || !a.IsIdle || attack.IsTraitDisabled || !seen.Add(a))
					continue;

				if (!target.IsValidFor(a))
					continue;

				var isAircraft = a.Info.HasTraitInfo<AircraftInfo>();
				if (isAircraft)
				{
					if (!info.CallAircraft || aircraft >= info.MaxAircraft ||
						(a.CenterPosition - aim).HorizontalLengthSquared > aircraftRange || !attack.HasAnyValidWeapons(target))
						continue;

					var pools = a.TraitsImplementing<AmmoPool>().ToList();
					if (pools.Count > 0 && !pools.Any(pool => pool.HasAmmo))
						continue;

					aircraft++;
				}
				else if (!InRange(a, attack, target))
					continue;

				var m = new Mission { Actor = a, Attack = attack, Aircraft = isAircraft };
				Issue(m, target);
				missions.Add(m);
			}

			if (first)
			{
				var any = missions.Count > 0;
				TextNotificationsManager.AddTransientLine(self.Owner, any ? info.FireMissionNotification : info.NoSupportNotification);
				if (any)
					Game.Sound.PlayToPlayer(SoundType.UI, self.Owner, info.FireMissionSound);
			}
		}

		/// <summary>Long-range armament that reaches the target from where the unit stands (they do not drive up).</summary>
		bool InRange(Actor a, AttackBase attack, in Target target)
		{
			foreach (var arm in attack.Armaments)
			{
				if (arm.IsTraitDisabled || arm.MaxRange() < info.MinSupportRange || !arm.Weapon.IsValidAgainst(target, a.World, a))
					continue;

				if (!target.IsInRange(a.CenterPosition, arm.MaxRange()))
					continue;

				if (arm.Weapon.MinRange != WDist.Zero && target.IsInRange(a.CenterPosition, arm.Weapon.MinRange))
					continue;

				return true;
			}

			return false;
		}

		void Issue(Mission m, in Target target)
		{
			// Same as AttackBase.AttackTarget, but keeping the activity so the fire can be stopped when the smoke is gone
			var activity = m.Attack.GetAttackActivity(m.Actor, AttackSource.Default, target, m.Aircraft, true, info.Color);
			m.Actor.QueueActivity(false, activity);
			m.Attack.OnResolveAttackOrder(m.Actor, activity, target, false, true);
			m.Activity = activity;
			m.Aim = aim;
		}

		/// <summary>Smoke is gone: everyone still firing on it stops (aircraft head home on their own).</summary>
		void Release()
		{
			foreach (var m in missions)
				if (Running(m))
					m.Activity.Cancel(m.Actor);

			missions.Clear();
		}

		// ------------------------------------------------------------------------------------------------ rendering
		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		/// <summary>0..1: full output for most of the canister's life, sputtering out over the last quarter.</summary>
		float Output => age >= info.SmokeTicks ? 0 : Math.Clamp((info.SmokeTicks - age) / (info.SmokeTicks * 0.25f), 0, 1);

		void ITickRender.TickRender(WorldRenderer wr, Actor self)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)self.World.Timestep;
			lastTime = now;
			if (self.World.Paused || dt <= 0)
				return;

			// The same synced wind that moves the aim point pushes the puffs, so the cloud is where the fire lands:
			// over a puff's ~180-tick life its average drift matches the aim's full drift.
			var calm = info.CalmDrift.Length;
			var drift = (calm + (info.GaleDrift.Length - calm) * windStrength / 1000f) * PixelsPerWorld / 90f;
			particles.Wind = new float2(windDirection.X / 1024f, windDirection.Y / 1024f) * drift;
			particles.Update(dt);

			if (burst)
			{
				burst = false;
				Burst();
			}

			var output = Output;
			if (output <= 0)
				return;

			emit += dt * (0.25f + 0.95f * output);
			while (emit >= 1)
			{
				emit--;
				EmitPuff(output);
			}

			// Hot core at the vent: small orange-red puffs that cool into the cloud
			if (random.NextFloat() < 0.5f * dt * output)
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Dye,
					X = Vent.X + Rand(-0.5f, 0.5f),
					Y = Vent.Y + Rand(-0.3f, 0.3f),
					Z = 1,
					VX = Jet.X * Rand(0.6f, 1.1f),
					VY = Jet.Y * Rand(0.6f, 1.1f),
					VZ = Rand(0.05f, 0.2f),
					Drag = 0.06f,
					Life = Rand(18, 30),
					Size = Rand(0.1f, 0.15f),
					Grow = 2.5f,
					Alpha = 0.95f,
					Tint = vent,
					TintEnd = color,
					FadeTint = true,
					Frame = random.Next(12),
					Angle = random.Next(1024),
					Spin = Rand(-3, 3),
				});

			// Sparks spitting from the burning composition
			if (random.NextFloat() < 0.08f * dt * output)
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Spark,
					X = Vent.X,
					Y = Vent.Y,
					Z = 1.5f,
					VX = Jet.X * Rand(0.8f, 2f) + Rand(-0.3f, 0.3f),
					VY = Jet.Y * Rand(0.8f, 2f) + Rand(-0.2f, 0.2f),
					VZ = Rand(0.4f, 1.1f),
					Gravity = 0.08f,
					Life = Rand(8, 16),
					Size = Rand(0.12f, 0.22f),
					Alpha = 1,
					Tint = new float3(1, Rand(0.55f, 0.8f), 0.3f),
				});
		}

		void EmitPuff(float output)
		{
			// One in three rolls along the ground, the rest jet out of the nozzle and billow upwards
			var ground = random.NextFloat() < 0.33f;
			var spread = Rand(-0.5f, 0.5f);
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Dye,
				X = Vent.X + Rand(-1, 1),
				Y = Vent.Y + Rand(-0.5f, 0.5f),
				Z = ground ? 0.5f : 1.5f,
				VX = Jet.X * Rand(0.7f, 1.4f) * output - spread * Jet.Y * 2,
				VY = Jet.Y * Rand(0.7f, 1.4f) * output + spread * Jet.X * 0.6f,
				VZ = ground ? Rand(0.01f, 0.06f) : Rand(0.12f, 0.4f),
				Gravity = ground ? -0.0015f : -0.006f,
				Drag = 0.03f,
				Life = Rand(150, 210),
				Size = Rand(0.2f, 0.28f) * (0.6f + 0.4f * output),
				Grow = ground ? Rand(6, 8) : Rand(4.5f, 6.5f),
				Alpha = Rand(0.82f, 0.95f) * (0.5f + 0.5f * output),
				Tint = color,
				TintEnd = fade,
				FadeTint = true,
				Frame = random.Next(12),
				Angle = random.Next(1024),
				Spin = Rand(-1.2f, 1.2f),
				Wind = ground ? 0.7f : 1,
			});
		}

		/// <summary>Ignition: a pop of hot gas and a ring of smoke rolling out from the canister.</summary>
		void Burst()
		{
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Glow,
				X = Vent.X,
				Y = Vent.Y,
				Z = 2,
				Life = 10,
				Size = 1.4f,
				Alpha = 0.9f,
				Tint = vent,
			});

			for (var i = 0; i < 10; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				var v = Rand(0.5f, 1.2f);
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Dye,
					X = Vent.X,
					Y = Vent.Y,
					Z = 1,
					VX = MathF.Cos(a) * v,
					VY = MathF.Sin(a) * v * 0.6f,
					VZ = Rand(0.02f, 0.2f),
					Drag = 0.05f,
					Life = Rand(70, 110),
					Size = Rand(0.16f, 0.22f),
					Grow = Rand(4, 5),
					Alpha = 0.85f,
					Tint = color,
					TintEnd = fade,
					FadeTint = true,
					Frame = random.Next(12),
					Angle = random.Next(1024),
					Spin = Rand(-2, 2),
					Wind = 0.6f,
				});
			}
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			var now = Game.RunTime;
			var white = new float3(1, 1, 1);
			var output = Output;

			// Dye soaking into the ground: spreads while it pours, fades away after the smoke
			var spread = Math.Min(1f, age / 160f);
			var stainAlpha = age < info.SmokeTicks ? 1f : 1f - (float)(age - info.SmokeTicks) / Math.Max(1, info.StainTicks);
			if (stainAlpha > 0)
			{
				var offset = PxParticles.ToWorld(Vent.X + 4, Vent.Y + 1);
				yield return new SpriteRenderable(stain.GetSprite(stainFrame), origin + offset, WVec.Zero, FlatZ - 64 - offset.Y, null,
					stain.Scale * (0.35f + 0.65f * spread), 0.8f * MathF.Min(1, stainAlpha * 1.5f), white, TintModifiers.None, false, WAngle.Zero);
			}

			// Red light thrown on the ground around the canister
			if (output > 0)
			{
				var flicker = 0.85f + 0.15f * MathF.Sin(now * 0.031f) * MathF.Sin(now * 0.017f + 1);
				yield return new SpriteRenderable(light.GetSprite(0), origin + PxParticles.ToWorld(Vent.X, Vent.Y), WVec.Zero, FlatZ,
					null, light.Scale * 0.6f, 0.22f * output * flicker, color, TintModifiers.None, false, WAngle.Zero);
			}

			// The canister: sputtering vent while it burns, a dark spent can afterwards
			var frame = output > 0 ? (int)(now / 60) % can.Length : 0;
			var dim = output > 0 ? 1f : 0.55f;
			yield return new SpriteRenderable(can.GetSprite(frame), origin, WVec.Zero, 0, null, can.Scale, 1f,
				new float3(dim, dim, dim), TintModifiers.None, false, WAngle.Zero);

			if (output > 0)
			{
				var flicker = 0.7f + 0.3f * MathF.Sin(now * 0.05f) * MathF.Sin(now * 0.023f + 2);
				yield return new SpriteRenderable(glow.GetSprite(0), origin + PxParticles.ToWorld(Vent.X, Vent.Y - 0.5f), WVec.Zero, 32,
					null, glow.Scale * 0.55f, 0.6f * output * flicker, vent, TintModifiers.None, false, WAngle.Zero);
			}

			// Aim ring, for the thrower's side only: tightens while the support gets ready, then holds steady
			var viewer = self.World.RenderPlayer;
			if (Smoking && (viewer == null || viewer.IsAlliedWith(self.Owner)))
			{
				float scale, alpha;
				if (age < info.WarningTicks)
				{
					var k = (float)age / info.WarningTicks;
					scale = 1.7f - 0.7f * k * k;
					alpha = (0.35f + 0.35f * k) * (0.75f + 0.25f * MathF.Sin(now * 0.025f));
				}
				else
				{
					scale = 1f + 0.04f * MathF.Sin(now * 0.008f);
					alpha = 0.55f * Math.Min(1, output * 2);
				}

				yield return new SpriteRenderable(reticle.GetSprite(0), aim, WVec.Zero, FlatZ + 16, null, reticle.Scale * scale, alpha,
					color, TintModifiers.None, false, WAngle.Zero);
			}

			foreach (var r in particles.Render(origin, ZBias))
				yield return r;
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			var c = wr.ScreenPxPosition(origin);
			var a = wr.ScreenPxPosition(aim);
			var left = Math.Min(c.X, a.X) - 320;
			var top = Math.Min(c.Y, a.Y) - 420;
			yield return Rectangle.FromLTRB(left, top, Math.Max(c.X, a.X) + 320, Math.Max(c.Y, a.Y) + 160);
		}
	}
}
