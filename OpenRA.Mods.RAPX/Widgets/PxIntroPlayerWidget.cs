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
using System.Diagnostics;
using OpenRA.Graphics;
using OpenRA.Primitives;
using OpenRA.Video;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	public enum PxIntroTransition { Barrage, Melt }

	/// <summary>
	/// Fullscreen intro player that hands over to whatever is underneath (the main menu) with a transition instead of a cut.
	/// The video is drawn as a grid of tiles so it can be torn apart while it keeps playing.
	/// Barrage: artillery shells streak in and blast burning craters through the picture (the menu shows through the holes),
	/// then a heavy shell lands on the logo: white flash, a shockwave cracks the rest of the frame into shards that are
	/// blown towards the camera, and the dust settles over the menu.
	/// Melt: the tiles dissolve from the edges inward with a molten glow while the video logo glides onto the menu art's logo.
	/// </summary>
	public class PxIntroPlayerWidget : Widget
	{
		// Barrage timeline in seconds for a BarrageDuration of BarrageLength; everything scales with it
		const float BarrageLength = 3.2f;
		const float BlastAt = 1.4f;
		const float ShellFlight = 0.16f;
		const float ShardLife = 1.1f;
		const float DebrisLife = 0.6f;
		const float Gravity = 700f;

		public Hotkey CancelKey = new(Keycode.ESCAPE, Modifiers.None);

		public PxIntroTransition Transition = PxIntroTransition.Barrage;

		[Desc("Seconds the melt takes.")]
		public float MeltDuration = 2.2f;

		[Desc("Seconds the barrage takes, from the first incoming shell to the dust settling. The big blast lands at 44% of it.")]
		public float BarrageDuration = 3.2f;

		[Desc("Sounds played as each barrage shell lands (picked at random).")]
		public string[] ImpactSounds = { "kaboom22.aud", "kaboom15.aud" };

		[Desc("Sound of the final blast.")]
		public string BlastSound = "kaboom25.aud";

		[Desc("Size of a tile in video pixels.")]
		public int TileSize = 8;

		[Desc("Point in the video (pixels) that travels onto TargetAnchor while melting, and where the barrage's final shell lands.")]
		public float2 VideoAnchor = new(640, 360);

		[Desc("Matching point in the menu art (pixels of an image of TargetImageSize drawn in cover mode).")]
		public float2 TargetAnchor = float2.Zero;

		[Desc("Size of the menu art the anchor refers to. Leave zero to melt in place.")]
		public float2 TargetImageSize = float2.Zero;

		[Desc("HorizontalAlign of the menu art's FullscreenImage.")]
		public float TargetAlign = 0.5f;

		[Desc("How many art pixels one video pixel covers once aligned (relative size of the shared subject).")]
		public float VideoToArtScale = 1f;

		[Desc("Soft round sprite used for sparks, flashes and smoke.")]
		public string SparkImage = null;

		static readonly float3 GlowColor = new(1f, 0.42f, 0.1f);
		static readonly float3 SparkColor = new(1f, 0.6f, 0.2f);
		static readonly float3 CrackColor = new(1f, 0.78f, 0.45f);
		static readonly float3 SmokeColor = new(0.09f, 0.08f, 0.07f);
		static readonly float3 DustColor = new(0.3f, 0.26f, 0.22f);

		static readonly float[] ShellTimes = { 0.16f, 0.44f, 0.67f, 0.86f, 1.02f };

		// Impact points as fractions of the video, kept clear of the logo in the middle
		static readonly float2[] ShellSpots = { new(0.15f, 0.28f), new(0.84f, 0.22f), new(0.27f, 0.82f), new(0.88f, 0.74f), new(0.6f, 0.9f) };

		readonly ModData modData;
		readonly Stopwatch playTime = new();
		readonly Random random = new();

		IVideo video;
		Action onComplete;
		Sheet sheet;
		Sprite frame;
		Sprite[] tiles;
		Sprite[] glowTiles;
		int cols, rows, textureWidth, textureHeight;
		float invLength;

		// Melt
		float[] thresholds;
		float[] drips;

		// Barrage
		Shell[] shells;
		Shard[] shards;
		float[] killTime;
		float[] charAmount;
		int[] rimShell;
		float2[] debrisVel;
		float[] debrisSpin;
		int[] shardOf;
		bool[] edge;
		float[] waveTime;
		float shockSpeed;
		int shellsLanded;
		bool blasted;
		int[] glowIndex;
		float3[] glowQuads;
		float3[] glowTints;

		Sheet sparkSheet, smokeSheet;
		Sprite spark, smoke;
		Particle[] sparks = Array.Empty<Particle>();
		Particle[] puffs = Array.Empty<Particle>();
		int sparkCount, puffCount;

		long transitionStart = -1;
		long lastDraw;
		float videoVolume;
		bool finished;

		struct Particle
		{
			public float2 Pos;
			public float2 Vel;
			public float Age;
			public float Life;
			public float Size;
			public float Grow;
			public float Drag;
			public float Gravity;
			public float Alpha;
			public float3 Color;
		}

		struct Shell
		{
			public float2 Pos;
			public float2 Dir;
			public float Radius;
			public float Time;
		}

		struct Shard
		{
			public float2 Center;
			public float2 Vel;
			public float Spin;
			public float Start;
		}

		[ObjectCreator.UseCtor]
		public PxIntroPlayerWidget(ModData modData)
		{
			this.modData = modData;
		}

		bool Transitioning => transitionStart >= 0;

		float BarrageScale => BarrageDuration / BarrageLength;

		/// <summary>Seconds before the end of the video the transition starts, so its main beat lands as the video ends.</summary>
		float TransitionLead => Transition == PxIntroTransition.Barrage ? BlastAt * BarrageScale : MeltDuration;

		public void Play(IVideo video, Action onComplete)
		{
			this.video = video;
			this.onComplete = onComplete;

			invLength = video.Framerate * 1f / video.FrameCount;
			textureWidth = Exts.NextPowerOf2(video.Width);
			textureHeight = Exts.NextPowerOf2(video.Height);
			sheet = new Sheet(SheetType.BGRA, new Size(textureWidth, textureHeight));
			sheet.GetTexture().ScaleFilter = TextureScaleFilter.Linear;
			sheet.GetTexture().SetData(video.CurrentFrameData, textureWidth, textureHeight);
			frame = new Sprite(sheet, new Rectangle(0, 0, video.Width, video.Height), TextureChannel.RGBA);

			cols = (video.Width + TileSize - 1) / TileSize;
			rows = (video.Height + TileSize - 1) / TileSize;
			tiles = new Sprite[cols * rows];
			glowTiles = new Sprite[cols * rows];
			for (var y = 0; y < rows; y++)
			{
				for (var x = 0; x < cols; x++)
				{
					var r = new Rectangle(x * TileSize, y * TileSize, Math.Min(TileSize, video.Width - x * TileSize), Math.Min(TileSize, video.Height - y * TileSize));
					tiles[y * cols + x] = new Sprite(sheet, r, TextureChannel.RGBA);
					glowTiles[y * cols + x] = new Sprite(sheet, r, 0, float3.Zero, TextureChannel.RGBA, BlendMode.Additive);
				}
			}

			if (Transition == PxIntroTransition.Barrage)
				SetupBarrage();
			else
				SetupMelt();

			if (SparkImage != null)
			{
				spark = FullscreenImageWidget.LoadImage(modData, SparkImage, out sparkSheet, BlendMode.Additive);
				smoke = CreatePuff(out smokeSheet);
				sparks = new Particle[1000];
				puffs = new Particle[200];
			}

			videoVolume = Game.Sound.VideoVolume;
			if (video.HasAudio)
				Game.Sound.PlayVideo(video.AudioData, video.AudioChannels, video.SampleBits, video.SampleRate);

			playTime.Start();
			lastDraw = Game.RunTime;
		}

		void SetupMelt()
		{
			thresholds = new float[tiles.Length];
			drips = new float[cols];
			for (var x = 0; x < cols; x++)
				drips[x] = 0.3f + 0.7f * (float)random.NextDouble() * (float)random.NextDouble();

			var seed = (float)random.NextDouble() * 100;
			for (var y = 0; y < rows; y++)
			{
				for (var x = 0; x < cols; x++)
				{
					// Melts from the edges in towards the anchor along a ragged noise front, so the subject goes last
					var u = (float)x / cols;
					var v = (float)y / rows;
					var dx = (x * TileSize + TileSize / 2f - VideoAnchor.X) / video.Width;
					var dy = (y * TileSize + TileSize / 2f - VideoAnchor.Y) / video.Height;
					var d = Math.Min(1f, MathF.Sqrt(dx * dx + dy * dy) * 1.6f);
					var n = 0.55f * Noise2(u * 6 + seed, v * 4) + 0.3f * Noise2(u * 15 + seed, v * 11) + 0.15f * Noise2(u * 40, v * 30 + seed);
					var threshold = 0.6f * (1 - d) + 0.4f * n - 0.08f * drips[x];

					// The frame's border must be gone before it starts shrinking, or its edge shows
					var border = Math.Min(Math.Min(x, cols - 1 - x), Math.Min(y, rows - 1 - y)) / (rows * 0.3f);
					thresholds[y * cols + x] = Math.Clamp(Math.Min(threshold, 0.05f + 0.35f * border + 0.1f * n), 0f, 1f);
				}
			}
		}

		void SetupBarrage()
		{
			var k = BarrageScale;
			var w = video.Width;
			var h = video.Height;
			var blast = BlastAt * k;
			shockSpeed = 1.8f * w / k;

			// Shells land on the spots in a random order, each one from a slightly different angle
			var order = new List<int>();
			for (var i = 0; i < ShellSpots.Length; i++)
				order.Insert(random.Next(order.Count + 1), i);

			shells = new Shell[ShellSpots.Length];
			for (var j = 0; j < shells.Length; j++)
			{
				var spot = ShellSpots[order[j]];
				var dir = new float2((spot.X < 0.5f ? 0.35f : -0.35f) + 0.5f * (Rand() - 0.5f), 1f);
				shells[j] = new Shell
				{
					Pos = new float2((spot.X + 0.08f * (Rand() - 0.5f)) * w, (spot.Y + 0.08f * (Rand() - 0.5f)) * h),
					Dir = dir / dir.Length,
					Radius = w * (0.095f + 0.035f * Rand()),
					Time = ShellTimes[j] * k
				};
			}

			// Shards: a jittered Voronoi grid, denser around the blast so it breaks up finest there
			var seeds = new List<float2>();
			for (var y = 0; y < 5; y++)
				for (var x = 0; x < 8; x++)
					seeds.Add(new float2((x + 0.15f + 0.7f * Rand()) * w / 8f, (y + 0.15f + 0.7f * Rand()) * h / 5f));

			for (var i = 0; i < 14; i++)
			{
				var a = Rand() * MathF.PI * 2;
				var r = 0.16f * w * MathF.Sqrt(Rand());
				seeds.Add(VideoAnchor + new float2(r * MathF.Cos(a), r * MathF.Sin(a)));
			}

			var n = tiles.Length;
			killTime = new float[n];
			charAmount = new float[n];
			rimShell = new int[n];
			debrisVel = new float2[n];
			debrisSpin = new float[n];
			shardOf = new int[n];
			edge = new bool[n];
			waveTime = new float[n];
			glowIndex = new int[n];
			glowQuads = new float3[4 * n];
			glowTints = new float3[n];

			var noiseSeed = Rand() * 100;
			var centroids = new float2[seeds.Count];
			var counts = new int[seeds.Count];
			for (var i = 0; i < n; i++)
			{
				var home = TileCenter(i);
				var nz = Noise2(home.X / 40 + noiseSeed, home.Y / 40);

				// Craters: tiles inside a ragged radius are blown out as debris, a ring around it is scorched
				killTime[i] = float.MaxValue;
				rimShell[i] = -1;
				for (var j = 0; j < shells.Length; j++)
				{
					var offset = home - shells[j].Pos;
					var len = offset.Length;
					var d = len / shells[j].Radius + 0.35f * (nz - 0.5f);
					if (d < 1f)
					{
						var kt = shells[j].Time + 0.06f * k * d;
						if (kt < killTime[i])
						{
							killTime[i] = kt;
							var dir = len > 1 ? offset / len : new float2(0, -1);
							debrisVel[i] = (300 + 700 * Rand()) / k * dir + new float2(0, -350 * Rand() / k);
							debrisSpin[i] = (Rand() - 0.5f) * 16 / k;
						}
					}
					else if (d < 1.8f && 1 - (d - 1) / 0.8f > charAmount[i])
					{
						charAmount[i] = 1 - (d - 1) / 0.8f;
						rimShell[i] = j;
					}
				}

				// Jag the shard borders by sampling the nearest seed from a noisy position
				var p = home + 3f * TileSize * new float2(Noise2(home.X / 30, home.Y / 30 + noiseSeed) - 0.5f, Noise2(home.X / 30 + noiseSeed, home.Y / 30) - 0.5f);
				var best = 0;
				var bestDist = float.MaxValue;
				for (var s = 0; s < seeds.Count; s++)
				{
					var dist = (p - seeds[s]).LengthSquared;
					if (dist < bestDist)
					{
						bestDist = dist;
						best = s;
					}
				}

				shardOf[i] = best;
				centroids[best] += home;
				counts[best]++;
				waveTime[i] = blast + (home - VideoAnchor).Length / shockSpeed;
			}

			shards = new Shard[seeds.Count];
			for (var s = 0; s < shards.Length; s++)
			{
				var center = counts[s] > 0 ? centroids[s] / counts[s] : seeds[s];
				var offset = center - VideoAnchor;
				var dist = offset.Length;
				var dir = dist > 1 ? offset / dist : new float2(0, -1);
				var near = 1.25f - 0.75f * Math.Min(1f, dist / (0.6f * w));
				shards[s] = new Shard
				{
					Center = center,
					Vel = (500 + 900 * Rand()) * near / k * dir + new float2(0, (-150 - 200 * Rand()) / k),
					Spin = (Rand() - 0.5f) * 5 / k,
					Start = blast + dist / shockSpeed
				};
			}

			// Cracks run along the shard borders
			for (var y = 0; y < rows; y++)
			{
				for (var x = 0; x < cols; x++)
				{
					var i = y * cols + x;
					if (x + 1 < cols && shardOf[i] != shardOf[i + 1])
						edge[i] = edge[i + 1] = true;

					if (y + 1 < rows && shardOf[i] != shardOf[i + cols])
						edge[i] = edge[i + cols] = true;
				}
			}
		}

		public void Skip()
		{
			if (video != null && !Transitioning)
				transitionStart = Game.RunTime;
		}

		public override void Draw()
		{
			if (video == null || finished)
				return;

			var now = Game.RunTime;
			var dt = Math.Clamp((now - lastDraw) / 1000f, 0f, 0.1f);
			lastDraw = now;

			AdvanceVideo();

			if (!Transitioning && playTime.Elapsed.TotalSeconds >= video.FrameCount / (float)video.Framerate - TransitionLead)
				transitionStart = now;

			if (!Transitioning)
			{
				var (origin, scale) = Placement(0);
				var a = new float3(origin.X, origin.Y, 0);
				var c = new float3(origin.X + scale * video.Width, origin.Y + scale * video.Height, 0);
				Game.Renderer.RgbaSpriteRenderer.DrawSprite(frame, a, new float3(c.X, a.Y, 0), c, new float3(a.X, c.Y, 0), new float3(1, 1, 1), 1f);
				return;
			}

			var elapsed = (now - transitionStart) / 1000f;
			if (Transition == PxIntroTransition.Barrage)
				DrawBarrage(elapsed, dt);
			else
				DrawMelt(elapsed, dt);
		}

		void DrawMelt(float elapsed, float dt)
		{
			var progress = Math.Clamp(elapsed / MeltDuration, 0f, 1f);
			if (video.HasAudio)
				Game.Sound.VideoVolume = videoVolume * (1 - progress);

			var (origin, scale) = Placement(progress);
			var tileScreen = TileSize * scale;

			// A tile starts melting when progress passes its threshold and is gone Band later
			const float Band = 0.25f;
			var front = progress * (1 + Band);
			var renderer = Game.Renderer.RgbaSpriteRenderer;

			for (var pass = 0; pass < 2; pass++)
			{
				for (var i = 0; i < tiles.Length; i++)
				{
					var local = Math.Clamp((front - thresholds[i]) / Band, 0f, 1f);
					if (local >= 1f)
						continue;

					var x = i % cols;
					var y = i / cols;
					var drop = local * local * drips[x] * 60 * scale;
					var tl = origin + new float2(x * tileScreen, y * tileScreen + drop);
					var size = scale * new float2(tiles[i].Bounds.Width, tiles[i].Bounds.Height);

					// Overlap neighbours by a pixel so no seams show between tiles
					var a = new float3(tl.X - 0.5f, tl.Y - 0.5f, 0);
					var c = new float3(tl.X + size.X + 0.5f, tl.Y + size.Y + 0.5f, 0);

					if (pass == 0)
					{
						var alpha = 1 - local * local;
						renderer.DrawSprite(tiles[i], a, new float3(c.X, a.Y, 0), c, new float3(a.X, c.Y, 0), new float3(alpha, alpha, alpha), alpha);
					}
					else if (local > 0)
					{
						// Molten rim: the tile glows hot just before it disappears
						var glow = 0.9f * MathF.Sin(local * MathF.PI) * (1 - local * 0.6f);
						renderer.DrawSprite(glowTiles[i], a, new float3(c.X, a.Y, 0), c, new float3(a.X, c.Y, 0), glow * GlowColor, 1f);

						if (spark != null && local > 0.35f && random.NextDouble() < 0.012)
						{
							var angle = Rand() * MathF.PI * 2;
							EmitSpark(new Particle
							{
								Pos = tl + 0.5f * size,
								Vel = scale * new float2(MathF.Cos(angle) * 60, -40 - 120 * Rand()),
								Life = 0.6f + 0.8f * Rand(),
								Size = (10 + 16 * Rand()) * scale,
								Gravity = 50 * scale,
								Color = SparkColor
							});
						}
					}
				}
			}

			DrawParticles(sparks, ref sparkCount, spark, dt, true);

			if (progress >= 1f)
				Finish();
		}

		void DrawBarrage(float t, float dt)
		{
			var k = BarrageScale;
			var blast = BlastAt * k;
			var total = BarrageLength * k;
			var (origin, scale) = Placement(0);

			// Zoom in a touch before the first hit so the shake never shows the screen edge
			var bounds = RenderBounds;
			var mid = new float2(bounds.X + bounds.Width / 2f, bounds.Y + bounds.Height / 2f);
			var overscan = 1 + 0.03f * Math.Min(1f, t / (ShellTimes[0] * k));
			origin = mid + overscan * (origin - mid);
			scale *= overscan;

			// Every hit shakes the picture
			var shake = 0f;
			foreach (var s in shells)
				if (t >= s.Time)
					shake += 9f * MathF.Exp(-(t - s.Time) * 10 / k);

			if (t >= blast)
				shake += 24f * MathF.Exp(-(t - blast) * 5 / k);

			origin += 0.66f * shake * new float2(MathF.Sin(t * 97.3f) + 0.5f * MathF.Sin(t * 151.7f), MathF.Cos(t * 83.1f) + 0.5f * MathF.Cos(t * 139.3f));

			while (shellsLanded < shells.Length && t >= shells[shellsLanded].Time)
				Impact(shells[shellsLanded++], origin, scale, total - t);

			if (!blasted && t >= blast)
			{
				blasted = true;
				Blast(origin + scale * VideoAnchor, scale, total - t);
			}

			if (video.HasAudio)
				Game.Sound.VideoVolume = videoVolume * (1 - Math.Clamp((t - blast) / (0.4f * k), 0f, 1f));

			var renderer = Game.Renderer.RgbaSpriteRenderer;
			var glowCount = 0;
			var pad = 0.5f / scale;
			for (var i = 0; i < tiles.Length; i++)
			{
				var home = TileCenter(i);
				var center = home;
				var angle = 0f;
				var grow = 1f;
				var alpha = 1f;
				var heat = 0f;
				var charred = 0f;
				var hot = GlowColor;

				if (rimShell[i] >= 0 && t >= shells[rimShell[i]].Time)
				{
					charred = charAmount[i];
					heat = charred * MathF.Exp(-(t - shells[rimShell[i]].Time) / (0.6f * k));
				}

				if (t >= killTime[i])
				{
					// Blown out of a crater as a burning clod
					var s = t - killTime[i];
					if (s >= DebrisLife * k)
						continue;

					var f = s / (DebrisLife * k);
					center = home + s * debrisVel[i] + new float2(0, 0.5f * Gravity / (k * k) * s * s);
					angle = debrisSpin[i] * s;
					grow = 1 - 0.5f * f;
					alpha = 1 - f * f;
					charred = 0.5f;
					heat = 1.2f * (1 - f);
				}
				else
				{
					ref var shard = ref shards[shardOf[i]];
					var s = t - shard.Start;
					if (s >= 0)
					{
						// Blown out by the shock front, tumbling towards the camera
						if (s >= ShardLife * k)
							continue;

						var f = s / (ShardLife * k);
						angle = shard.Spin * s;
						grow = 1 + 1.4f * s / k;
						alpha = 1 - f * f;
						var rel = grow * (home - shard.Center);
						var cs = MathF.Cos(angle);
						var sn = MathF.Sin(angle);
						center = shard.Center + s * shard.Vel + new float2(rel.X * cs - rel.Y * sn, 0.5f * Gravity / (k * k) * s * s + rel.X * sn + rel.Y * cs);
					}

					// Cracks flash white-hot as the shock front passes
					if (edge[i] && t >= waveTime[i])
					{
						var crack = 1.3f * MathF.Exp(-(t - waveTime[i]) / (0.3f * k));
						if (crack > heat)
						{
							heat = crack;
							hot = CrackColor;
						}
					}
				}

				var tile = tiles[i].Bounds;
				var cos = MathF.Cos(angle);
				var sin = MathF.Sin(angle);
				var hw = scale * (grow * tile.Width / 2f + pad);
				var hh = scale * (grow * tile.Height / 2f + pad);
				var sc = origin + scale * center;
				var ax = hw * cos;
				var ay = hw * sin;
				var bx = -hh * sin;
				var by = hh * cos;
				var q0 = new float3(sc.X - ax - bx, sc.Y - ay - by, 0);
				var q1 = new float3(sc.X + ax - bx, sc.Y + ay - by, 0);
				var q2 = new float3(sc.X + ax + bx, sc.Y + ay + by, 0);
				var q3 = new float3(sc.X - ax + bx, sc.Y - ay + by, 0);

				var lum = alpha * (1 - 0.75f * charred);
				renderer.DrawSprite(tiles[i], q0, q1, q2, q3, new float3(lum, lum, lum), alpha);

				if (heat * alpha > 0.02f)
				{
					// Glow is drawn in a second batch so the blend mode doesn't flip per tile
					glowIndex[glowCount] = i;
					glowQuads[4 * glowCount] = q0;
					glowQuads[4 * glowCount + 1] = q1;
					glowQuads[4 * glowCount + 2] = q2;
					glowQuads[4 * glowCount + 3] = q3;
					glowTints[glowCount++] = Math.Min(heat * alpha, 1f) * hot;
				}
			}

			for (var g = 0; g < glowCount; g++)
				renderer.DrawSprite(glowTiles[glowIndex[g]], glowQuads[4 * g], glowQuads[4 * g + 1], glowQuads[4 * g + 2], glowQuads[4 * g + 3], glowTints[g], 1f);

			DrawParticles(puffs, ref puffCount, smoke, dt, false);
			DrawParticles(sparks, ref sparkCount, spark, dt, true);

			if (spark != null)
				DrawBarrageLights(t, origin, scale);

			if (t >= total)
				Finish();
		}

		/// <summary>Incoming shell tracers, muzzle-bright impact flashes and fireballs, and the final blast with its shockwave ring.</summary>
		void DrawBarrageLights(float t, float2 origin, float scale)
		{
			var k = BarrageScale;
			var flight = ShellFlight * k;
			foreach (var s in shells)
			{
				var target = origin + scale * s.Pos;
				if (t < s.Time && t >= s.Time - flight)
				{
					var u = (t - (s.Time - flight)) / flight;
					var head = target - (1 - u) * 900 * scale * s.Dir;
					DrawStreak(head - 220 * scale * s.Dir, head, 5 * scale, new float3(1f, 0.85f, 0.5f));
					DrawGlow(head, 40 * scale, new float3(1f, 0.9f, 0.6f));
				}
				else if (t >= s.Time && t < s.Time + 0.8f * k)
				{
					var a = (t - s.Time) / k;
					DrawGlow(target, scale * s.Radius * (1.6f + 3 * a), 1.4f * MathF.Exp(-a / 0.07f) * new float3(1f, 0.9f, 0.7f));
					DrawGlow(target, scale * s.Radius * (1.1f + 2 * a), 1.1f * MathF.Exp(-a / 0.25f) * new float3(1f, 0.45f, 0.12f));
				}
			}

			var b = (t - BlastAt * k) / k;
			if (b < 0)
				return;

			var bounds = RenderBounds;
			var center = origin + scale * VideoAnchor;
			DrawGlow(center, 4 * Math.Max(bounds.Width, bounds.Height), 1.8f * MathF.Exp(-b / 0.09f) * new float3(1f, 0.92f, 0.8f));
			DrawGlow(center, (0.6f + 1f * b) * bounds.Height, 1.4f * MathF.Exp(-b / 0.5f) * new float3(1f, 0.5f, 0.15f));

			if (b < 0.8f)
			{
				// Shockwave ring, riding the front that breaks the shards loose
				const int Dots = 120;
				var radius = scale * shockSpeed * b * k;
				var size = (30 + 60 * b) * scale;
				var color = 0.9f * (1 - b / 0.8f) * (1 - b / 0.8f) * new float3(1f, 0.7f, 0.35f);
				for (var i = 0; i < Dots; i++)
				{
					var a = i * MathF.PI * 2 / Dots;
					DrawGlow(center + radius * new float2(MathF.Cos(a), MathF.Sin(a)), size, color);
				}
			}
		}

		void Impact(Shell s, float2 origin, float scale, float remaining)
		{
			if (ImpactSounds.Length > 0)
				Game.Sound.Play(SoundType.UI, ImpactSounds[random.Next(ImpactSounds.Length)], 0.8f);

			if (spark == null)
				return;

			var k = BarrageScale;
			var p = origin + scale * s.Pos;
			for (var i = 0; i < 45; i++)
			{
				var a = -MathF.PI / 2 + (Rand() - 0.5f) * 2.6f;
				EmitSpark(new Particle
				{
					Pos = p,
					Vel = (200 + 600 * Rand()) * scale / k * new float2(MathF.Cos(a), MathF.Sin(a)),
					Life = Math.Min((0.35f + 0.55f * Rand()) * k, remaining),
					Size = (4 + 8 * Rand()) * scale,
					Drag = 1.5f / k,
					Gravity = 900 * scale / (k * k),
					Color = new float3(1f, 0.6f + 0.25f * Rand(), 0.2f + 0.2f * Rand())
				});
			}

			for (var i = 0; i < 8; i++)
			{
				var a = Rand() * MathF.PI * 2;
				EmitPuff(new Particle
				{
					Pos = p + 0.4f * scale * s.Radius * Rand() * new float2(MathF.Cos(a), MathF.Sin(a)),
					Vel = scale / k * new float2((Rand() - 0.5f) * 80, -20 - 40 * Rand()),
					Life = Math.Min((1.4f + 0.8f * Rand()) * k, remaining),
					Size = scale * s.Radius * (0.7f + 0.5f * Rand()),
					Grow = 0.9f / k,
					Drag = 0.8f / k,
					Alpha = 0.6f,
					Color = SmokeColor
				});
			}
		}

		void Blast(float2 center, float scale, float remaining)
		{
			if (!string.IsNullOrEmpty(BlastSound))
				Game.Sound.Play(SoundType.UI, BlastSound);

			if (spark == null)
				return;

			var k = BarrageScale;
			for (var i = 0; i < 180; i++)
			{
				var a = Rand() * MathF.PI * 2;
				EmitSpark(new Particle
				{
					Pos = center,
					Vel = (400 + 1200 * Rand()) * scale / k * new float2(MathF.Cos(a), MathF.Sin(a)),
					Life = Math.Min((0.5f + 0.9f * Rand()) * k, remaining),
					Size = (5 + 12 * Rand()) * scale,
					Drag = 1.8f / k,
					Gravity = 500 * scale / (k * k),
					Color = new float3(1f, 0.65f + 0.3f * Rand(), 0.3f + 0.3f * Rand())
				});
			}

			// A ring of dust rolls out with the shockwave and settles as it thins over the menu
			for (var i = 0; i < 80; i++)
			{
				var a = (i + Rand()) * MathF.PI * 2 / 80;
				var dir = new float2(MathF.Cos(a), MathF.Sin(a));
				EmitPuff(new Particle
				{
					Pos = center + 30 * scale * dir,
					Vel = (500 + 600 * Rand()) * scale / k * dir,
					Life = remaining * (0.75f + 0.25f * Rand()),
					Size = (120 + 140 * Rand()) * scale,
					Grow = 0.6f / k,
					Drag = 2.2f / k,
					Alpha = 0.4f,
					Color = DustColor
				});
			}
		}

		/// <summary>A lumpy, soft-edged white puff with real transparency (the spark dot is black-backed, only fit for additive).</summary>
		Sprite CreatePuff(out Sheet puffSheet)
		{
			const int Size = 128;
			var data = new byte[Size * Size * 4];
			var seed = Rand() * 100;
			for (var y = 0; y < Size; y++)
			{
				for (var x = 0; x < Size; x++)
				{
					var u = (x + 0.5f) / Size * 2 - 1;
					var v = (y + 0.5f) / Size * 2 - 1;
					var r = MathF.Sqrt(u * u + v * v);
					var lumps = 0.6f * Noise2(u * 3 + seed, v * 3) + 0.4f * Noise2(u * 7, v * 7 + seed);
					var falloff = Math.Clamp(1 - r / (0.7f + 0.3f * lumps), 0f, 1f);
					var a = (byte)(255 * falloff * falloff * (0.7f + 0.3f * lumps));
					var i = 4 * (y * Size + x);
					data[i] = data[i + 1] = data[i + 2] = data[i + 3] = a;
				}
			}

			puffSheet = new Sheet(SheetType.BGRA, new Size(Size, Size));
			puffSheet.GetTexture().ScaleFilter = TextureScaleFilter.Linear;
			puffSheet.GetTexture().SetData(data, Size, Size);
			return new Sprite(puffSheet, new Rectangle(0, 0, Size, Size), TextureChannel.RGBA);
		}

		float2 TileCenter(int i)
		{
			var bounds = tiles[i].Bounds;
			return new float2(bounds.X + bounds.Width / 2f, bounds.Y + bounds.Height / 2f);
		}

		float Rand() { return (float)random.NextDouble(); }

		/// <summary>Cover the screen while playing; while melting, glide so VideoAnchor lands on the menu art's TargetAnchor.</summary>
		(float2 Origin, float Scale) Placement(float progress)
		{
			var b = RenderBounds;
			var coverScale = Math.Max((float)b.Width / video.Width, (float)b.Height / video.Height);
			var coverOrigin = new float2(b.X + (b.Width - coverScale * video.Width) / 2, b.Y + (b.Height - coverScale * video.Height) / 2);
			if (progress <= 0 || TargetImageSize.X <= 0)
				return (coverOrigin, coverScale);

			var (artOrigin, artSize) = FullscreenImageWidget.CoverRect(TargetImageSize, b, TargetAlign);
			var artScale = artSize.X / TargetImageSize.X;

			// Ease in and out: start once the border has melted, arrive a little before the last tiles are gone
			var t = Math.Clamp((progress - 0.15f) / 0.7f, 0f, 1f);
			t = t * t * (3 - 2 * t);

			var scale = coverScale + (VideoToArtScale * artScale - coverScale) * t;
			var from = coverOrigin + coverScale * VideoAnchor;
			var to = artOrigin + artScale * TargetAnchor;
			var anchor = from + t * (to - from);
			return (anchor - scale * VideoAnchor, scale);
		}

		void AdvanceVideo()
		{
			int nextFrame;
			if (video.HasAudio && !Game.Sound.DummyEngine && !Transitioning)
				nextFrame = (int)(Game.Sound.VideoSeekPosition * invLength * video.FrameCount);
			else
				nextFrame = (int)((float)playTime.Elapsed.TotalSeconds * invLength * video.FrameCount);

			// Hold the last frame if the transition outlasts the video
			nextFrame = Math.Min(nextFrame, video.FrameCount - 1);
			var advanced = false;
			while (nextFrame > video.CurrentFrameIndex)
			{
				video.AdvanceFrame();
				advanced = true;
			}

			if (advanced)
				sheet.GetTexture().SetData(video.CurrentFrameData, textureWidth, textureHeight);
		}

		void EmitSpark(Particle p)
		{
			if (sparkCount < sparks.Length && p.Life > 0)
				sparks[sparkCount++] = p;
		}

		void EmitPuff(Particle p)
		{
			if (puffCount < puffs.Length && p.Life > 0)
				puffs[puffCount++] = p;
		}

		/// <summary>Additive particles burn out from full brightness; alpha ones (smoke) fade in quickly and thin away.</summary>
		static void DrawParticles(Particle[] particles, ref int count, Sprite sprite, float dt, bool additive)
		{
			for (var i = 0; i < count; i++)
			{
				ref var p = ref particles[i];
				p.Age += dt;
				if (p.Age >= p.Life)
				{
					particles[i--] = particles[--count];
					continue;
				}

				p.Vel = MathF.Exp(-p.Drag * dt) * p.Vel + new float2(0, p.Gravity * dt);
				p.Pos += dt * p.Vel;
				var f = p.Age / p.Life;
				var h = p.Size * (1 + p.Grow * p.Age) / 2;
				var a = new float3(p.Pos.X - h, p.Pos.Y - h, 0);
				var c = new float3(p.Pos.X + h, p.Pos.Y + h, 0);
				if (additive)
				{
					Game.Renderer.RgbaSpriteRenderer.DrawSprite(sprite, a, new float3(c.X, a.Y, 0), c, new float3(a.X, c.Y, 0), (1 - f) * (1 - f) * p.Color, 1f);
				}
				else
				{
					var alpha = p.Alpha * Math.Min(1f, p.Age / 0.12f) * (1 - f);
					Game.Renderer.RgbaSpriteRenderer.DrawSprite(sprite, a, new float3(c.X, a.Y, 0), c, new float3(a.X, c.Y, 0), alpha * p.Color, alpha);
				}
			}
		}

		/// <summary>Additive soft dot; intensities above 1 are drawn as stacked copies.</summary>
		void DrawGlow(float2 center, float size, float3 color)
		{
			var h = size / 2;
			var a = new float3(center.X - h, center.Y - h, 0);
			var c = new float3(center.X + h, center.Y + h, 0);
			var peak = Math.Max(color.X, Math.Max(color.Y, color.Z));
			for (; peak > 0.01f; peak--)
			{
				var part = Math.Min(peak, 1f) / Math.Max(color.X, Math.Max(color.Y, color.Z));
				Game.Renderer.RgbaSpriteRenderer.DrawSprite(spark, a, new float3(c.X, a.Y, 0), c, new float3(a.X, c.Y, 0), part * color, 1f);
			}
		}

		/// <summary>The soft dot stretched into a tracer between two points.</summary>
		void DrawStreak(float2 from, float2 to, float width, float3 color)
		{
			var d = to - from;
			var len = d.Length;
			if (len < 1)
				return;

			var side = width / len * new float2(-d.Y, d.X);
			Game.Renderer.RgbaSpriteRenderer.DrawSprite(spark,
				new float3(from.X + side.X, from.Y + side.Y, 0), new float3(to.X + side.X, to.Y + side.Y, 0),
				new float3(to.X - side.X, to.Y - side.Y, 0), new float3(from.X - side.X, from.Y - side.Y, 0), color, 1f);
		}

		void Finish()
		{
			if (finished)
				return;

			finished = true;
			Game.Sound.StopVideo();
			Game.Sound.VideoVolume = videoVolume;
			Game.RunAfterTick(() => onComplete?.Invoke());
		}

		public override bool HandleKeyPress(KeyInput e)
		{
			if (Hotkey.FromKeyInput(e) != CancelKey || e.Event != KeyInputEvent.Down)
				return false;

			Skip();
			return true;
		}

		public override bool HandleMouseInput(MouseInput mi)
		{
			if (mi.Event == MouseInputEvent.Down)
				Skip();

			return true;
		}

		public override string GetCursor(int2 pos) { return null; }

		static float Noise2(float x, float y)
		{
			var ix = MathF.Floor(x);
			var iy = MathF.Floor(y);
			var fx = x - ix;
			var fy = y - iy;
			fx = fx * fx * (3 - 2 * fx);
			fy = fy * fy * (3 - 2 * fy);
			var a = Hash((int)ix, (int)iy);
			var b = Hash((int)ix + 1, (int)iy);
			var c = Hash((int)ix, (int)iy + 1);
			var d = Hash((int)ix + 1, (int)iy + 1);
			return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
		}

		static float Hash(int x, int y)
		{
			var h = (uint)(x * 374761393 + y * 668265263);
			h = (h ^ (h >> 13)) * 1274126177u;
			return (h ^ (h >> 16)) / (float)uint.MaxValue;
		}

		public override void Removed()
		{
			base.Removed();
			if (!finished && video != null)
			{
				Game.Sound.StopVideo();
				Game.Sound.VideoVolume = videoVolume;
			}

			sheet?.Dispose();
			sparkSheet?.Dispose();
			smokeSheet?.Dispose();
		}
	}
}
