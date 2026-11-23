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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("When the building is destroyed it shakes and sinks into the ground (Sequence) while throwing debris and dust,",
		"then leaves a smouldering scorch mark with rubble that fades out.")]
	public class WithPxCollapseInfo : TraitInfo, Requires<RenderSpritesInfo>, Requires<BuildingInfo>
	{
		[SequenceReference]
		[Desc("Frames of the building sinking into the ground, spread over Duration.")]
		public readonly string Sequence = "collapse";

		[Desc("Ticks the building takes to sink into the ground.")]
		public readonly int Duration = 45;

		[Desc("Ticks the scorch mark and rubble stay before fading out.")]
		public readonly int Linger = 650;

		[Desc("The building stands in water: white spray instead of dust, debris sinks, no scorch mark.")]
		public readonly bool OnWater = false;

		[Desc("Filmed clips (sequences of image pxvideofx, artsrc/fx/make_video_fx.py): the fire loop burning on the ruins,",
			"the smoke column rising from them and the dust rolling out as the building goes down. Empty or missing =",
			"particles only. Not used on water.")]
		public readonly string FireVideo = "fire-small-b";

		public readonly string SmokeVideo = "smoke-column-a";

		public readonly string DustVideo = "dust-a";

		public override object Create(ActorInitializer init) { return new WithPxCollapse(init.Self, this); }
	}

	public class WithPxCollapse : INotifyKilled
	{
		readonly WithPxCollapseInfo info;
		readonly RenderSprites rs;
		readonly BuildingInfo building;

		public WithPxCollapse(Actor self, WithPxCollapseInfo info)
		{
			this.info = info;
			rs = self.Trait<RenderSprites>();
			building = self.Info.TraitInfo<BuildingInfo>();
		}

		void INotifyKilled.Killed(Actor self, AttackInfo e)
		{
			if (!self.IsInWorld)
				return;

			var image = rs.GetImage(self);
			var sequences = self.World.Map.Sequences;
			if (!sequences.HasSequence(image, info.Sequence))
				return;

			var palette = rs.Info.Palette ?? rs.Info.PlayerPalette + self.Owner.InternalName;

			// Footprint half-size in screen pixels (24 px cells), excluding the bib row
			var rows = building.Footprint
				.Where(kv => kv.Value is FootprintCellType.Occupied or FootprintCellType.OccupiedUntargetable)
				.Select(kv => kv.Key.Y).Distinct().Count();
			var radius = new float2(building.Dimensions.X * 12, Math.Max(rows, 1) * 12);

			var pos = self.CenterPosition;
			self.World.AddFrameEndTask(w => w.Add(new PxCollapseEffect(w, pos, image, info.Sequence, palette, radius, info)));
		}
	}

	public class PxCollapseEffect : IEffect
	{
		const int ScorchZ = -2048;

		readonly World world;
		readonly WPos pos;
		readonly string palette;
		readonly float2 radius;
		readonly WithPxCollapseInfo info;
		readonly ISpriteSequence building;
		readonly ISpriteSequence scorch;
		readonly ISpriteSequence ruin;
		readonly int ruinFrame;
		readonly PxParticleKind chunk;
		readonly PxParticles particles;
		readonly PxParticles debris;
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());
		readonly float2[] fires;
		readonly int[] phases;
		readonly ISpriteSequence fireVideo, smokeVideo, dustVideo;

		float time;
		float burn = 1;
		long lastTime = -1;
		float dustTimer;
		float smokeTimer;
		bool started;

		public PxCollapseEffect(World world, WPos pos, string image, string sequence, string palette, float2 radius, WithPxCollapseInfo info)
		{
			this.world = world;
			this.pos = pos;
			this.palette = palette;
			this.radius = radius;
			this.info = info;
			building = world.Map.Sequences.GetSequence(image, sequence);
			particles = new PxParticles(world);
			debris = new PxParticles(world);
			scorch = particles.Sequence("scorch");

			// HD ruins (artsrc/fx/make_ruin_fx.py) replace the plain scorch mark, rubble the plain chunks
			if (!info.OnWater)
				ruin = particles.Sequence("ruin");
			if (ruin != null)
				ruinFrame = random.Next(ruin.Length);

			chunk = particles.Sequence("rubble") != null ? PxParticleKind.Rubble : PxParticleKind.Chunk;

			fires = new float2[Math.Clamp((int)(radius.X * radius.Y / 300), 1, 4)];
			for (var i = 0; i < fires.Length; i++)
				fires[i] = new float2(Rand(-0.6f, 0.6f) * radius.X, Rand(-0.6f, 0.4f) * radius.Y);

			phases = new int[fires.Length];
			for (var i = 0; i < phases.Length; i++)
				phases[i] = random.Next(1024);

			if (!info.OnWater)
			{
				var sequences = world.Map.Sequences;
				ISpriteSequence Find(string name) =>
					!string.IsNullOrEmpty(name) && sequences.HasSequence("pxvideofx", name) ? sequences.GetSequence("pxvideofx", name) : null;
				fireVideo = Find(info.FireVideo);
				smokeVideo = Find(info.SmokeVideo);
				dustVideo = Find(info.DustVideo);
			}
		}

		float Rand(float min, float max) { return min + random.NextFloat() * (max - min); }

		float Total => info.Duration + info.Linger + 150;

		public void Tick(World world)
		{
			if (time > Total)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		void Start()
		{
			started = true;

			// Shockwave ring and a big dust burst rolling outwards from the base
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Ring,
				Life = 18,
				Size = (radius.X + 16) / 20f,
				Grow = 0.8f,
				Alpha = 0.55f,
				Tint = new float3(0.75f, 0.68f, 0.58f),
			});

			var n = (int)(radius.X * 0.9f) + 8;
			for (var i = 0; i < n; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				var (cx, cy) = (MathF.Cos(a), MathF.Sin(a));
				var s = Rand(0.5f, 1.4f);
				particles.Add(Dust(cx * radius.X * 0.8f, cy * radius.Y * 0.8f, cx * s, cy * s * 0.6f, Rand(0.1f, 0.4f),
					Rand(0.5f, 0.9f), Rand(60, 110)));
			}

			// Debris thrown out of the building
			var chunks = (int)(radius.X * 1.2f) + 10;
			for (var i = 0; i < chunks; i++)
			{
				var a = Rand(0, MathF.PI * 2);
				var s = Rand(0.3f, 1.1f);
				debris.Add(new PxParticle
				{
					Kind = chunk,
					X = Rand(-0.5f, 0.5f) * radius.X,
					Y = Rand(-0.5f, 0.5f) * radius.Y,
					Z = Rand(4, radius.Y + 10),
					VX = MathF.Cos(a) * s,
					VY = MathF.Sin(a) * s * 0.5f,
					VZ = Rand(1.5f, 3.5f),
					Gravity = 0.22f,
					Drag = 0.03f,
					Life = info.OnWater ? info.Duration + Rand(10, 30) : info.Duration + info.Linger * Rand(0.6f, 1f),
					Size = Rand(0.6f, 1.4f),
					Alpha = 1,
					Tint = new float3(1, 1, 1),
					Frame = random.Next(debris.FrameCount(chunk)),
					Angle = random.Next(1024),
					Spin = Rand(-40, 40),
				});
			}

			// Hot flash
			particles.Add(new PxParticle
			{
				Kind = PxParticleKind.Glow,
				Z = radius.Y * 0.5f,
				Life = 14,
				Size = radius.X / 6f,
				Alpha = 0.9f,
				Tint = new float3(1, 0.7f, 0.35f),
			});
		}

		PxParticle Dust(float x, float y, float vx, float vy, float vz, float size, float life)
		{
			var grey = info.OnWater ? Rand(0.8f, 0.92f) : Rand(0.5f, 0.65f);
			return new PxParticle
			{
				Kind = PxParticleKind.Smoke,
				X = x,
				Y = y,
				Z = Rand(0, 4),
				VX = vx,
				VY = vy,
				VZ = vz,
				Drag = 0.03f,
				Life = life,
				Size = size,
				Grow = 2.2f,
				Alpha = 0.8f,
				Tint = info.OnWater ? new float3(grey, grey, grey * 1.03f) : new float3(grey * 1.08f, grey, grey * 0.86f),
				Frame = random.Next(particles.FrameCount(PxParticleKind.Smoke)),
				Angle = random.Next(1024),
				Spin = Rand(-4, 4),
			};
		}

		void Update(float dt)
		{
			if (!started)
				Start();

			time += dt;
			particles.Update(dt);
			debris.Update(dt);

			// Dust keeps pouring out while the building sinks
			if (time < info.Duration)
			{
				dustTimer -= dt;
				while (dustTimer <= 0)
				{
					dustTimer += 1.2f;
					var x = Rand(-1, 1) * radius.X;
					var y = Rand(-0.3f, 1) * radius.Y;
					particles.Add(Dust(x, y, Rand(-0.3f, 0.3f), Rand(0, 0.3f), Rand(0.3f, 0.7f), Rand(0.5f, 0.8f), Rand(50, 80)));
				}
			}

			// Smouldering fires: dense at first, dying down over the linger time
			burn = 1 - Math.Clamp((time - info.Duration) / (info.Linger * 0.6f), 0, 1);
			if (burn > 0)
			{
				smokeTimer -= dt;
				while (smokeTimer <= 0)
				{
					// A filmed smoke column carries most of the smoke: fewer puffs around it
					smokeTimer += 3.5f / Math.Max(burn, 0.15f) / fires.Length * (smokeVideo != null ? 2.5f : 1);
					var f = fires[random.Next(fires.Length)];
					var grey = Rand(0.1f, 0.2f);
					particles.Add(new PxParticle
					{
						Kind = PxParticleKind.Smoke,
						X = f.X + Rand(-3, 3),
						Y = f.Y + Rand(-2, 2),
						Z = 2,
						VX = Rand(0.08f, 0.22f),
						VZ = Rand(0.4f, 0.7f),
						Drag = 0.008f,
						Life = Rand(80, 120),
						Size = Rand(0.4f, 0.6f) * (0.6f + 0.4f * burn),
						Grow = 2.8f,
						Alpha = 0.8f * burn + 0.2f,
						Tint = new float3(grey, grey, grey * 0.95f),
						Frame = random.Next(particles.FrameCount(PxParticleKind.Smoke)),
						Angle = random.Next(1024),
						Spin = Rand(-3, 3),
					});

					if (fireVideo == null && random.NextFloat() < burn)
					{
						particles.Add(new PxParticle
						{
							Kind = PxParticleKind.Flame,
							X = f.X + Rand(-3, 3),
							Y = f.Y + Rand(-2, 2),
							Z = 6 * burn + 2,
							VZ = 0.1f,
							Life = Rand(12, 20),
							Size = Rand(0.5f, 0.9f) * burn,
							Grow = -0.3f,
							Alpha = 1,
							Tint = new float3(1, 1, 1),
							Frame = random.Next(particles.FrameCount(PxParticleKind.Flame)),
						});
					}
				}
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 200) / (float)world.Timestep;
			lastTime = now;
			if (!world.Paused)
				Update(dt);

			if (world.FogObscures(pos))
				return SpriteRenderable.None;

			return RenderInner(wr);
		}

		IEnumerable<IRenderable> RenderInner(WorldRenderer wr)
		{
			// Scorch mark: appears under the collapsing building and fades at the end
			var fadeOut = 1 - Math.Clamp((time - info.Duration - info.Linger) / 150f, 0, 1);
			var scorchAlpha = Math.Clamp(time / 10f, 0, 1) * fadeOut;
			if (ruin != null)
			{
				// The ruin shows through as the building sinks, sized to the footprint
				var sprite = ruin.GetSprite(ruinFrame);
				var alpha = Math.Clamp(time / (info.Duration * 0.8f), 0, 1) * fadeOut;
				var scale = (radius.X * 2.7f + 24) / sprite.Size.X;
				if (alpha > 0)
					yield return new SpriteRenderable(sprite, pos, WVec.Zero, ScorchZ, null, scale, alpha,
						new float3(1, 1, 1), TintModifiers.None, false);
			}
			else if (scorchAlpha > 0 && !info.OnWater)
				yield return new SpriteRenderable(scorch.GetSprite(0), pos, WVec.Zero, ScorchZ, null,
					scorch.Scale * (radius.X * 2.6f + 20) / 80f, scorchAlpha, new float3(1, 1, 1), TintModifiers.None, false);

			if (time < info.Duration)
			{
				var t = time / info.Duration;
				var frame = Math.Min((int)(t * building.Length), building.Length - 1);

				// Shake hardest at the start, fade the last bit out
				var shake = (1 - t) * 2.5f;
				var jitter = PxParticles.ToWorld(Rand(-shake, shake), Rand(-shake, shake) * 0.5f);
				var alpha = t > 0.85f ? (1 - t) / 0.15f : 1;
				yield return new SpriteRenderable(building.GetSprite(frame), pos + jitter, WVec.Zero, 0, wr.Palette(palette), building.Scale, alpha,
					new float3(1, 1, 1), TintModifiers.None, false);
			}

			foreach (var r in RenderVideos())
				yield return r;

			foreach (var r in debris.Render(pos, -1024))
				yield return r;

			foreach (var r in particles.Render(pos, 512))
				yield return r;
		}

		/// <summary>The filmed dust, fires and smoke column. Time runs in 40 ms game ticks.</summary>
		IEnumerable<IRenderable> RenderVideos()
		{
			var white = new float3(1, 1, 1);

			// Dust rolling out once, sized to the footprint, its last frame thinning out
			if (dustVideo != null)
			{
				var end = dustVideo.Length * dustVideo.Tick / 40f;
				if (time < end + 60)
				{
					var sprite = dustVideo.GetSprite(Math.Min((int)(time * 40 / dustVideo.Tick), dustVideo.Length - 1));
					var linger = Math.Clamp((time - end) / 60, 0, 1);
					var scale = (radius.X * 2.4f + 40) / sprite.Size.X * (1 + 0.15f * linger);
					yield return new SpriteRenderable(sprite, pos, WVec.Zero, 512, null, scale, 1 - linger * linger * (3 - 2 * linger),
						white, TintModifiers.None, false);
				}
			}

			// Fires on the ruins, dying down
			if (fireVideo != null && burn > 0)
			{
				var now = Game.RunTime;
				for (var i = 0; i < fires.Length; i++)
				{
					var sprite = fireVideo.GetSprite((int)(now / fireVideo.Tick + phases[i]) % fireVideo.Length);
					var offset = PxParticles.ToWorld(fires[i].X, fires[i].Y);
					yield return new SpriteRenderable(sprite, pos + offset, WVec.Zero, 512 - offset.Y, null,
						fireVideo.Scale * 0.6f * (0.4f + 0.6f * burn), Math.Min(1, burn * 3), white, TintModifiers.None, false);
				}
			}

			// One smoke column over the ruins, outlasting the fires
			if (smokeVideo != null)
			{
				var strength = Math.Clamp(time / 40, 0, 1) * (1 - Math.Clamp((time - info.Duration) / (info.Linger * 0.9f), 0, 1));
				if (strength > 0)
				{
					var sprite = smokeVideo.GetSprite((int)(Game.RunTime / smokeVideo.Tick) % smokeVideo.Length);
					var offset = PxParticles.ToWorld(fires[0].X, fires[0].Y);
					var scale = (radius.X * 4.5f + 40) / sprite.Size.Y * (0.7f + 0.3f * strength);
					yield return new SpriteRenderable(sprite, pos + offset, WVec.Zero, 520 - offset.Y, null, scale, strength * 0.9f,
						white, TintModifiers.None, false);
				}
			}
		}
	}
}
