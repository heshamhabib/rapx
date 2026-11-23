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

namespace OpenRA.Mods.RAPX.Effects
{
	/// <summary>Plays a filmed clip (a sequence of image pxvideofx, artsrc/fx/make_video_fx.py) once at a spot, then lets
	/// its last frame linger: thinning out and spreading a little. Purely cosmetic.</summary>
	public class PxVideoEffect : IEffect
	{
		public const string Image = "pxvideofx";

		readonly World world;
		readonly WPos pos;
		readonly ISpriteSequence clip;
		readonly float scale;
		readonly int linger;
		readonly int zOffset;
		float time;
		long lastTime = -1;

		public PxVideoEffect(World world, WPos pos, ISpriteSequence clip, float scale, int linger, int zOffset)
		{
			this.world = world;
			this.pos = pos;
			this.clip = clip;
			this.scale = scale;
			this.linger = Math.Max(1, linger);
			this.zOffset = zOffset;
		}

		/// <summary>The clip of that name, or null when the name is empty or the clip is missing.</summary>
		public static ISpriteSequence Find(World world, string name)
		{
			var sequences = world.Map.Sequences;
			return !string.IsNullOrEmpty(name) && sequences.HasSequence(Image, name) ? sequences.GetSequence(Image, name) : null;
		}

		/// <summary>Ticks until the last frame (40 ms game ticks, so the clip keeps pace with the game speed).</summary>
		float End => clip.Length * clip.Tick / 40f;

		public void Tick(World world)
		{
			if (time > End + linger)
				world.AddFrameEndTask(w => w.Remove(this));
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			var now = Game.RunTime;
			if (lastTime >= 0 && !world.Paused)
				time += Math.Min(now - lastTime, 200) / (float)world.Timestep;
			lastTime = now;

			if (world.FogObscures(pos))
				yield break;

			var frame = Math.Min((int)(time * 40 / clip.Tick), clip.Length - 1);
			var t = Math.Clamp((time - End) / linger, 0, 1);
			yield return new SpriteRenderable(clip.GetSprite(frame), pos, WVec.Zero, zOffset, null, scale * (1 + 0.15f * t),
				1 - t * t * (3 - 2 * t), new float3(1, 1, 1), TintModifiers.None, false);
		}
	}
}
