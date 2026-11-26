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
using OpenRA.Mods.Common.Warheads;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Warheads
{
	[Desc("Plays a filmed clip (sequence of image pxvideofx, artsrc/fx/make_video_fx.py) at the impact: water splashes,",
		"electric strikes, a cluster bomb's carpet, a cannon's strafing run. Cosmetic only.")]
	public class PxVideoWarhead : Warhead
	{
		[FieldLoader.Require]
		[Desc("Clips, one picked at random.")]
		public readonly string[] Video = Array.Empty<string>();

		[Desc("Size, as a multiple of the clip's own scale.")]
		public readonly float Scale = 1f;

		[Desc("Play it on the ground under the impact point (an air burst or a raised target).")]
		public readonly bool Ground = true;

		[Desc("The clip runs from left to right: play its mirrored twin (<name>-m) when the shot travels leftwards.")]
		public readonly bool Directional = false;

		[Desc("Ticks after a clip in which the same shooter's next impacts play none (one clip per burst). 0 = every impact.")]
		public readonly int Gap = 0;

		[Desc("Draw order bias.")]
		public readonly int ZOffset = 512;

		static readonly Dictionary<Actor, int> LastPlayed = new();
		readonly MersenneTwister random = new(Game.CosmeticRandom.Next());

		public override void DoImpact(in Target target, WarheadArgs args)
		{
			if (target.Type == TargetType.Invalid)
				return;

			var world = args.SourceActor.World;
			var shooter = args.SourceActor;
			if (Gap > 0)
			{
				if (LastPlayed.TryGetValue(shooter, out var last) && world.WorldTick - last < Gap)
					return;
				if (LastPlayed.Count > 256)
					LastPlayed.Clear();
				LastPlayed[shooter] = world.WorldTick;
			}

			var clip = PxVideoEffect.Pick(world, Video, random);
			if (clip == null)
				return;

			var pos = target.CenterPosition;
			if (Directional && args.Source.HasValue && pos.X < args.Source.Value.X)
				clip = PxVideoEffect.Mirrored(world, clip);
			if (Ground)
				pos -= new WVec(0, 0, world.Map.DistanceAboveTerrain(pos).Length);

			var scale = clip.Scale * Scale;
			world.AddFrameEndTask(w => w.Add(new PxVideoEffect(w, pos, clip, scale, ZOffset, blast: true)));
		}
	}
}
