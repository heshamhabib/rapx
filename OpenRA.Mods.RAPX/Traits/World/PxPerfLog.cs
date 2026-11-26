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
using System.Globalization;
using System.Linq;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Developer tool: when the RAPX_PERFLOG environment variable is set, writes the average frame rate",
		"and render/tick timings to the perf log channel every Interval ticks. Does nothing otherwise.")]
	public class PxPerfLogInfo : TraitInfo
	{
		public readonly int Interval = 50;

		public override object Create(ActorInitializer init) { return new PxPerfLog(this); }
	}

	public sealed class PxPerfLog : ITick
	{
		const int AblateTicks = 250;

		static readonly string[] Items = { "render", "render_prepare", "render_world", "render_widgets", "render_flip", "tick_time", "tick_actors", "batches" };

		readonly PxPerfLogInfo info;
		readonly bool enabled = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_PERFLOG"));

		// RAPX_PERF_ABLATE="Terrain,TerrainDetailTextures,Shroud,..." (WorldRenderer.DevSkip names): from tick
		// RAPX_PERF_ABLATE_START on, skip one step per AblateTicks window, alternating with windows that skip nothing,
		// so each step's frame-time cost can be read off the log (samples are tagged ablate=<step>)
		readonly string[] ablate = (Environment.GetEnvironmentVariable("RAPX_PERF_ABLATE") ?? "")
			.Split(',', StringSplitOptions.RemoveEmptyEntries);
		readonly int ablateStart = Exts.TryParseInt32Invariant(Environment.GetEnvironmentVariable("RAPX_PERF_ABLATE_START") ?? "", out var start) ? start : 2000;
		string ablating = "none";
		int ticks;
		int lastFrame;
		long lastTime;

		public PxPerfLog(PxPerfLogInfo info)
		{
			this.info = info;
		}

		void ITick.Tick(Actor self)
		{
			if (!enabled || self.World.Type == WorldType.Editor)
				return;

			if (ablate.Length > 0 && self.World.Type == WorldType.Regular && self.World.WorldTick >= ablateStart)
			{
				var window = (self.World.WorldTick - ablateStart) / AblateTicks;
				var step = window % 2 == 1 && window / 2 < ablate.Length ? ablate[window / 2] : "none";
				if (step != ablating)
				{
					OpenRA.Graphics.WorldRenderer.DevSkip.Clear();
					if (step != "none")
						OpenRA.Graphics.WorldRenderer.DevSkip.Add(step);

					ablating = step;
				}
			}

			if (++ticks % info.Interval != 0)
				return;

			var frames = Game.RenderFrame - lastFrame;
			var ms = Game.RunTime - lastTime;
			lastFrame = Game.RenderFrame;
			lastTime = Game.RunTime;
			if (ticks == info.Interval)
				return;

			var fps = ms > 0 ? 1000.0 * frames / ms : 0;
			var parts = Items.Where(PerfHistory.Items.ContainsKey)
				.Select(i => $"{i}={PerfHistory.Items[i].Average(Math.Min(frames, 100)).ToString("0.00", CultureInfo.InvariantCulture)}");

			// Weather clock (the shaders' Time), for lining up shader experiments with these samples
			var weather = self.World.WorldActor.TraitOrDefault<PxWeatherManager>();
			var weatherTime = weather != null && weather.Enabled ? weather.Frame().Time : 0f;

			// Full-screen passes drawn this frame (the main GPU cost)
			var passes = string.Join(",", self.World.WorldActor.TraitsImplementing<IRenderPostProcessPass>()
				.Where(p => p.Enabled).Select(p => p.GetType().Name));
			Log.Write("perf", $"PxPerfLog tick {self.World.WorldTick}: fps={fps.ToString("0.0", CultureInfo.InvariantCulture)} " +
				$"tickms={(ms / (double)info.Interval).ToString("0.0", CultureInfo.InvariantCulture)} actors={self.World.Actors.Count()} " +
				$"particles={Graphics.PxParticles.LiveTotal} effects={self.World.Effects.Count()} " +
				$"step={self.World.Timestep} catchup={Game.LogicCatchUpTicks} retries={Game.LogicOrderRetries} " + string.Join(" ", parts) +
				$" ablate={ablating}" +
				$" wtime={weatherTime.ToString("0.0", CultureInfo.InvariantCulture)} downscale={Game.Renderer.WorldDownscaleFactor.ToString("0.###", CultureInfo.InvariantCulture)} passes={passes}");
		}
	}
}
