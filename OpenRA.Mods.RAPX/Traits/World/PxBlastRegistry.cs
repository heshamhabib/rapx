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

using System.Collections.Generic;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	/// <summary>Cosmetic notification: an HD explosion went off within its blast radius of this actor. Implementations
	/// may only change how the actor is drawn, never the simulation.</summary>
	public interface INotifyPxBlast
	{
		void OnBlast(Actor self, WPos pos, float size, WDist radius);
	}

	public readonly struct PxBlast
	{
		public readonly WPos Pos;
		public readonly float Size;
		public readonly WDist Radius;
		public readonly int Tick;

		public PxBlast(WPos pos, float size, WDist radius, int tick)
		{
			Pos = pos;
			Size = size;
			Radius = radius;
			Tick = tick;
		}
	}

	[TraitLocation(SystemActors.World)]
	[Desc("Remembers the HD explosions (PxExplosion warheads) of the last few ticks, so soldiers they kill can be thrown by",
		"the blast (WithPxBlastDeath), and tells the actors around each blast about it (INotifyPxBlast, e.g. WithPxBlastShove).")]
	public class PxBlastRegistryInfo : TraitInfo
	{
		public override object Create(ActorInitializer init) { return new PxBlastRegistry(); }
	}

	public class PxBlastRegistry : ITick
	{
		// World units per screen pixel (1024 per 24 pixel cell)
		public const float WorldPerPixel = 1024f / 24f;

		readonly List<PxBlast> blasts = new();
		int tick;

		/// <summary>The radius within which a blast of this size throws and shoves things.</summary>
		public static WDist RadiusFor(float size)
		{
			return new WDist((int)(1024 * (0.55f + 1.15f * size)));
		}

		public void Register(World world, WPos pos, float size)
		{
			var radius = RadiusFor(size);
			blasts.Add(new PxBlast(pos, size, radius, tick));
			foreach (var a in world.FindActorsInCircle(pos, radius))
				foreach (var n in a.TraitsImplementing<INotifyPxBlast>())
					n.OnBlast(a, pos, size, radius);
		}

		/// <summary>The blast of this or the previous tick that hits pos hardest, if any.</summary>
		public bool TryFind(WPos pos, out PxBlast blast)
		{
			blast = default;
			var best = 0f;
			foreach (var b in blasts)
			{
				if (b.Tick < tick - 1)
					continue;

				var d = (pos - b.Pos).HorizontalLength;
				if (d > b.Radius.Length)
					continue;

				var hit = b.Size * (1.1f - (float)d / b.Radius.Length);
				if (hit > best)
				{
					best = hit;
					blast = b;
				}
			}

			return best > 0;
		}

		void ITick.Tick(Actor self)
		{
			tick++;
			blasts.RemoveAll(b => b.Tick < tick - 2);
		}
	}
}
