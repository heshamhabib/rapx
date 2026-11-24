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
using OpenRA.Effects;
using OpenRA.Graphics;
using OpenRA.Support;

namespace OpenRA.Mods.RAPX.Effects
{
	/// <summary>Plays a filmed clip (a sequence of image pxvideofx, artsrc/fx/make_video_fx.py) once at a spot, to its last
	/// frame (the clips play their whole life on screen and end empty). Purely cosmetic.</summary>
	public class PxVideoEffect : IEffect
	{
		public const string Image = "pxvideofx";

		/// <summary>RAPX_CLASSIC_FX=1: play the game as it looked before the filmed effects and HD ruins (no clips, the
		/// particle explosions and plain scorch marks instead), e.g. to record the "before" half of a comparison.</summary>
		public static readonly bool Classic = Environment.GetEnvironmentVariable("RAPX_CLASSIC_FX") == "1";

		static readonly float3 White = new(1, 1, 1);

		readonly World world;
		readonly WPos pos;
		readonly ISpriteSequence clip;
		readonly float scale;
		readonly int zOffset;
		readonly float3 tint;
		float time;
		long lastTime = -1;

		public PxVideoEffect(World world, WPos pos, ISpriteSequence clip, float scale, int zOffset, float3? tint = null)
		{
			this.world = world;
			this.pos = pos;
			this.clip = clip;
			this.scale = scale;
			this.zOffset = zOffset;
			this.tint = tint ?? White;
		}

		/// <summary>The clip of that name, or null when the name is empty or the clip is missing.</summary>
		public static ISpriteSequence Find(World world, string name)
		{
			var sequences = world.Map.Sequences;
			return !Classic && !string.IsNullOrEmpty(name) && sequences.HasSequence(Image, name) ? sequences.GetSequence(Image, name) : null;
		}

		/// <summary>One clip picked at random from a list of names (missing ones skipped), or null.</summary>
		public static ISpriteSequence Pick(World world, string[] names, MersenneTwister random)
		{
			if (names == null || names.Length == 0)
				return null;

			var start = random.Next(names.Length);
			for (var i = 0; i < names.Length; i++)
			{
				var clip = Find(world, names[(start + i) % names.Length]);
				if (clip != null)
					return clip;
			}

			return null;
		}

		/// <summary>The clip's mirrored twin ("&lt;name&gt;-m", FlipX), or the clip itself when it has none.</summary>
		public static ISpriteSequence Mirrored(World world, ISpriteSequence clip)
		{
			return clip == null ? null : Find(world, clip.Name + "-m") ?? clip;
		}

		/// <summary>Ticks from the first to the last frame (40 ms game ticks, so clips keep pace with the game speed).</summary>
		public static float Duration(ISpriteSequence clip) { return (clip.Length - 1) * clip.Tick / 40f; }

		/// <summary>The clip at a fractional frame. blend: each frame crossfades into the next (one-shot explosions kept at
		/// a few frames per second); fires and smoke loops are kept at a higher rate and drawn frame by frame, since
		/// crossfading their see-through flames makes them pulse.</summary>
		public static IEnumerable<IRenderable> Draw(ISpriteSequence clip, float frame, WPos pos, int zOffset, float scale,
			float alpha, float3 tint, bool wrap = false, bool blend = true)
		{
			if (alpha <= 0.001f)
				yield break;

			var n = clip.Length;
			if (wrap)
				frame = (frame % n + n) % n;
			else
				frame = Math.Clamp(frame, 0, n - 1);

			var i = (int)frame;
			var f = blend ? frame - i : 0;
			var next = wrap ? (i + 1) % n : i + 1;
			if (f < 0.04f || next >= n)
			{
				yield return new SpriteRenderable(clip.GetSprite(i), pos, WVec.Zero, zOffset, null, scale, alpha, tint, TintModifiers.None, false);
				yield break;
			}

			// True crossfade: each frame at its own share, so see-through smoke never gets denser and jumps back
			yield return new SpriteRenderable(clip.GetSprite(i), pos, WVec.Zero, zOffset, null, scale, alpha * (1 - f), tint,
				TintModifiers.None, false);
			yield return new SpriteRenderable(clip.GetSprite(next), pos, WVec.Zero, zOffset + 1, null, scale, alpha * f, tint,
				TintModifiers.None, false);
		}

		public void Tick(World world)
		{
			if (time > Duration(clip) + 1)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			var now = Game.RunTime;
			if (lastTime >= 0 && !world.Paused)
				time += Math.Min(now - lastTime, 200) / (float)world.Timestep;
			lastTime = now;

			if (world.FogObscures(pos))
				return SpriteRenderable.None;

			return Draw(clip, time * 40 / clip.Tick, pos, zOffset, scale, 1f, tint);
		}
	}

	/// <summary>A fire or smoke column filmed in parts (artsrc/fx/video-prompts-v2.md): it catches (Start), burns as long
	/// as needed (Loop) and burns out (End). Each part hands over to the next on the spot with a short dissolve, so a
	/// fire never pops in or fades out. Advance it with Update, draw it with Render.</summary>
	public class PxClipCycle
	{
		/// <summary>Ticks over which one part dissolves into the next.</summary>
		const float Handover = 8;

		enum State { Off, Starting, Looping, Ending, Done }

		readonly ISpriteSequence start, loop, end;
		State state;
		float time;

		// The part being handed over from, its frame and how long it has left
		ISpriteSequence fromClip;
		float fromFrame;
		bool fromWrap;
		float fromLeft;

		public PxClipCycle(ISpriteSequence start, ISpriteSequence loop, ISpriteSequence end, float phase = 0)
		{
			this.start = start;
			this.loop = loop;
			this.end = end;
			time = phase;
		}

		/// <summary>A cycle from clip names (loops: one picked at random); null when the loop is missing.</summary>
		public static PxClipCycle Create(World world, string start, string[] loops, string end, MersenneTwister random)
		{
			var loop = PxVideoEffect.Pick(world, loops, random);
			if (loop == null)
				return null;

			return new PxClipCycle(PxVideoEffect.Find(world, start), loop, PxVideoEffect.Find(world, end), random.Next(loop.Length) * loop.Tick / 40f);
		}

		public bool Burning => state is State.Starting or State.Looping;

		/// <summary>True until the fire has burnt out (or was never lit).</summary>
		public bool Active => state is State.Starting or State.Looping or State.Ending || fromLeft > 0;

		public bool Done => state == State.Done && fromLeft <= 0;

		public void Ignite(bool withStart = true)
		{
			if (state is State.Starting or State.Looping)
				return;

			if (withStart && start != null)
			{
				state = State.Starting;
				time = 0;
			}
			else
				state = State.Looping;
		}

		public void Extinguish()
		{
			if (state == State.Starting || state == State.Looping)
			{
				HandFrom(state == State.Starting ? start : loop, Frame(state == State.Starting ? start : loop), state == State.Looping);
				if (end != null)
				{
					state = State.Ending;
					time = 0;
				}
				else
					state = State.Done;
			}
		}

		void HandFrom(ISpriteSequence clip, float frame, bool wrap)
		{
			fromClip = clip;
			fromFrame = frame;
			fromWrap = wrap;
			fromLeft = Handover;
		}

		float Frame(ISpriteSequence clip) { return time * 40 / clip.Tick; }

		public void Update(float dt)
		{
			time += dt;
			if (fromLeft > 0)
			{
				fromLeft -= dt;
				fromFrame += dt * 40 / fromClip.Tick;
			}

			if (state == State.Starting && time >= PxVideoEffect.Duration(start))
			{
				HandFrom(start, start.Length - 1, false);
				state = State.Looping;
				time = 0;
			}
			else if (state == State.Ending && time >= PxVideoEffect.Duration(end) + 1)
				state = State.Done;
		}

		/// <summary>Draw the fire; scale multiplies the clips' own sequence Scale.</summary>
		public IEnumerable<IRenderable> Render(WPos pos, int zOffset, float scale, float alpha, float3 tint)
		{
			var k = fromLeft > 0 ? Math.Clamp(fromLeft / Handover, 0, 1) : 0;
			var current = state switch
			{
				State.Starting => PxVideoEffect.Draw(start, Frame(start), pos, zOffset, scale * start.Scale, alpha, tint, false, false),
				State.Looping => PxVideoEffect.Draw(loop, Frame(loop), pos, zOffset, scale * loop.Scale, alpha, tint, true, false),
				State.Ending => PxVideoEffect.Draw(end, Frame(end), pos, zOffset, scale * end.Scale, alpha, tint, false, false),
				_ => SpriteRenderable.None,
			};

			foreach (var r in current)
				yield return r;

			if (k > 0)
				foreach (var r in PxVideoEffect.Draw(fromClip, fromFrame, pos, zOffset + 2, scale * fromClip.Scale, alpha * k, tint, fromWrap, false))
					yield return r;
		}
	}
}
