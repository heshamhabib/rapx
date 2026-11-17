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
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;

namespace OpenRA.Mods.RAPX.Effects
{
	/// <summary>
	/// A fast rope cut loose after the last soldier is down (IDEA-47, PxAirAssault): a little verlet chain that falls
	/// from the helicopter's door, slaps onto the ground and piles up in loose loops, lies there for a while and
	/// fades away. Purely cosmetic.
	/// </summary>
	public class PxDroppedRope : IEffect
	{
		const int Links = 12;
		const float Gravity = 36f;
		const int LieTicks = 300;
		const int FadeTicks = 60;

		readonly float3[] pos = new float3[Links];
		readonly float3[] prev = new float3[Links];
		readonly float link;
		readonly float ground;
		readonly WPos anchor;
		readonly Color core, edge, light;
		readonly float width;
		readonly string sound;
		bool landed;
		int ticks;

		public PxDroppedRope(WPos top, WPos bottom, float width, Color core, Color edge, Color light, string sound)
		{
			anchor = bottom;
			ground = bottom.Z;
			this.width = width;
			this.core = core;
			this.edge = edge;
			this.light = light;
			this.sound = sound;

			var random = new MersenneTwister(Game.CosmeticRandom.Next());
			var length = (float)(top - bottom).Length;
			link = length / (Links - 1);
			for (var i = 0; i < Links; i++)
			{
				var t = (float)i / (Links - 1);
				pos[i] = new float3(top.X + (bottom.X - top.X) * t, top.Y + (bottom.Y - top.Y) * t, top.Z + (bottom.Z - top.Z) * t);

				// A sideways flick so the falling rope folds into loops instead of a straight stack
				var kick = (1 - t) * 26f;
				prev[i] = pos[i] - new float3((random.NextFloat() - 0.5f) * kick, (random.NextFloat() - 0.5f) * kick, 0);
			}
		}

		public void Tick(World world)
		{
			ticks++;
			if (ticks > LieTicks + FadeTicks)
			{
				world.AddFrameEndTask(w => w.Remove(this));
				return;
			}

			// Verlet integration with ground friction, then a few passes of the link-length constraint
			for (var i = 0; i < Links; i++)
			{
				var p = pos[i];
				var v = p - prev[i];
				var onGround = p.Z <= ground + 1;
				if (onGround)
					v = new float3(v.X * 0.6f, v.Y * 0.6f, v.Z);

				prev[i] = p;
				pos[i] = p + v - new float3(0, 0, Gravity);
				if (pos[i].Z < ground)
					pos[i] = new float3(pos[i].X, pos[i].Y, ground);
			}

			for (var pass = 0; pass < 4; pass++)
			{
				for (var i = 0; i < Links - 1; i++)
				{
					var d = pos[i + 1] - pos[i];
					var len = MathF.Sqrt(d.X * d.X + d.Y * d.Y + d.Z * d.Z);
					if (len < 1)
						continue;

					var fix = (len - link) / len * 0.5f * d;
					pos[i] += fix;
					pos[i + 1] -= fix;
				}
			}

			if (!landed && pos[0].Z <= ground + 4)
			{
				landed = true;
				Game.Sound.Play(SoundType.World, sound, new WPos((int)pos[0].X, (int)pos[0].Y, (int)ground));
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			var points = new WPos[Links];
			for (var i = 0; i < Links; i++)
				points[i] = new WPos((int)pos[i].X, (int)pos[i].Y, (int)pos[i].Z);

			var alpha = ticks < LieTicks ? 1f : 1f - (float)(ticks - LieTicks) / FadeTicks;
			var zOffset = landed ? -900 : 512;
			yield return new PxRopeRenderable(points, anchor, zOffset, width, core, edge, light, Math.Clamp(alpha, 0, 1));
		}
	}
}
