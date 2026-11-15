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
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Cosmetic: the pressure wave of a nearby HD explosion (PxExplosion) shoves this actor's sprite away from the",
		"blast for a moment, with a small hop. The actor itself does not move.")]
	public class WithPxBlastShoveInfo : TraitInfo
	{
		[Desc("How far the sprite is pushed by a Size 1 blast right next to it, in screen pixels.")]
		public readonly float Distance = 5f;

		[Desc("How high it hops, in screen pixels.")]
		public readonly float Hop = 2.5f;

		[Desc("How long the shove lasts, in ticks.")]
		public readonly int Ticks = 14;

		public override object Create(ActorInitializer init) { return new WithPxBlastShove(this); }
	}

	public class WithPxBlastShove : IRenderModifier, INotifyPxBlast
	{
		const float WorldPerPixel = 1024f / 24f;

		readonly WithPxBlastShoveInfo info;
		float pushX, pushY, hop, duration;
		long start = -1;

		public WithPxBlastShove(WithPxBlastShoveInfo info)
		{
			this.info = info;
		}

		void INotifyPxBlast.OnBlast(Actor self, WPos pos, float size, WDist radius)
		{
			var d = self.CenterPosition - pos;
			var dx = d.X / WorldPerPixel;
			var dy = d.Y / WorldPerPixel;
			var dist = MathF.Sqrt(dx * dx + dy * dy);
			float ax, ay;
			if (dist < 1)
			{
				var a = Game.CosmeticRandom.NextFloat() * MathF.PI * 2;
				ax = MathF.Cos(a);
				ay = MathF.Sin(a);
				dist = 0;
			}
			else
			{
				ax = dx / dist;
				ay = dy / dist;
			}

			var fall = MathF.Pow(1 - Math.Clamp(dist / (radius.Length / WorldPerPixel), 0, 1), 0.7f);
			var k = Math.Min(size, 2f) * fall;
			var amp = info.Distance * k;
			if (amp < 0.4f)
				return;

			pushX = ax * amp;
			pushY = ay * amp * 0.6f;
			hop = info.Hop * k;
			duration = info.Ticks * (0.8f + 0.4f * Math.Min(size, 2f)) * self.World.Timestep;
			start = Game.RunTime;
		}

		IEnumerable<IRenderable> IRenderModifier.ModifyRender(Actor self, WorldRenderer wr, IEnumerable<IRenderable> r)
		{
			if (start < 0)
				return r;

			var t = (Game.RunTime - start) / duration;
			if (t >= 1)
			{
				start = -1;
				return r;
			}

			// Out fast, back slowly, a hop in between
			var k = MathF.Sin(MathF.PI * t);
			var ease = k * (1 - 0.5f * t);
			var offset = PxParticles.ToWorld(pushX * ease, pushY * ease - hop * k);
			return r.Select(x => x.OffsetBy(offset));
		}

		IEnumerable<Rectangle> IRenderModifier.ModifyScreenBounds(Actor self, WorldRenderer wr, IEnumerable<Rectangle> r)
		{
			return r;
		}
	}
}
