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
using OpenRA.Graphics;

namespace OpenRA.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("RAPX: smooth camera shake. Every shake request adds 'trauma' (0-1) with diminishing returns, so a salvo of",
		"forty blasts cannot stack into forty times the shake; trauma fades away over real time and the camera offset is",
		"trauma squared times smooth noise, so small knocks are barely felt and only big ones really shake. The offset is",
		"updated every render frame and never drifts the camera.")]
	public class ScreenShakerInfo : TraitInfo
	{
		[Desc("Largest camera offset, in screen pixels, at full trauma.")]
		public readonly float MaxOffset = 4f;

		[Desc("How quickly trauma fades, per second (1 = a full-strength shake dies out in a second).")]
		public readonly float Decay = 1f;

		[Desc("Shake energy (intensity x multiplier x duration factor, at the camera) that adds half the remaining trauma.")]
		public readonly float HalfEnergy = 3f;

		[Desc("Distance in cells from the camera at which a shake counts for half; it fades with the square beyond that.")]
		public readonly float FalloffCells = 8f;

		[Desc("Shake frequency in hertz.")]
		public readonly float Frequency = 8f;

		public override object Create(ActorInitializer init) { return new ScreenShaker(this); }
	}

	public class ScreenShaker : IWorldLoaded
	{
		readonly ScreenShakerInfo info;
		WorldRenderer worldRenderer;
		float trauma;
		long lastTime = -1;

		public ScreenShaker(ScreenShakerInfo info)
		{
			this.info = info;
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			worldRenderer = wr;
			wr.Viewport.Shake = Offset;
		}

		public void AddEffect(int time, WPos position, int intensity)
		{
			AddEffect(time, position, intensity, new float2(1, 1));
		}

		public void AddEffect(int time, WPos position, int intensity, float2 multiplier)
		{
			if (worldRenderer == null || intensity <= 0)
				return;

			// Blasts near the camera count fully; far off-screen ones barely
			var d = (position - worldRenderer.Viewport.CenterPosition).HorizontalLength / 1024f / info.FalloffCells;
			var energy = intensity * (Math.Abs(multiplier.X) + Math.Abs(multiplier.Y)) / 2 * (time / 10f) / (1 + d * d);
			var add = energy / (energy + info.HalfEnergy);

			// Diminishing returns: each request fills a share of what is left, so trauma never exceeds 1
			trauma += (1 - trauma) * add;
		}

		int2 Offset()
		{
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min(now - lastTime, 100) / 1000f;
			lastTime = now;
			trauma = Math.Max(0, trauma - info.Decay * dt);
			if (trauma <= 0)
				return int2.Zero;

			// Two incommensurate sines per axis: smooth, non-repeating wobble instead of a per-tick jolt
			var t = now / 1000f * info.Frequency * 2 * MathF.PI;
			var x = 0.6f * MathF.Sin(t) + 0.4f * MathF.Sin(t * 1.73f + 1.1f);
			var y = 0.6f * MathF.Sin(t * 1.17f + 2.3f) + 0.4f * MathF.Sin(t * 2.09f + 0.4f);
			var amplitude = info.MaxOffset * trauma * trauma;
			return new int2((int)MathF.Round(x * amplitude), (int)MathF.Round(y * amplitude));
		}
	}
}
