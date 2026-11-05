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
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	public enum PxWeatherType { Clear, Rain, Thunderstorm, Snow, Blizzard, Fog, Sandstorm, StrongWind, HeatHaze }

	[TraitLocation(SystemActors.World)]
	[Desc("Dynamic weather (IDEA-20): picks the weather from the map's climate with the synced random generator,",
		"announces each change and fades between them. Drawn by PxWeatherGround and PxWeatherSky.",
		"Map makers can set Fixed or Allowed in the map's rules. RAPX_WEATHER=<type>[,<type>...] forces the weather",
		"(dev screenshots: each one lasts RAPX_WEATHER_TICKS ticks, ground effects start fully grown).")]
	public class PxWeatherManagerInfo : TraitInfo, ILobbyOptions
	{
		[FluentReference]
		public readonly string Label = "dropdown-weather.label";

		[FluentReference]
		public readonly string Description = "dropdown-weather.description";

		[FluentReference]
		public readonly string ChangesLabel = "dropdown-weather-changes.label";

		[FluentReference]
		public readonly string ChangesDescription = "dropdown-weather-changes.description";

		public readonly string Default = "visual";
		public readonly string ChangesDefault = "normal";
		public readonly bool Locked = false;
		public readonly bool Visible = true;
		public readonly int DisplayOrder = 4;

		[Desc("Climate of each tileset (temperate, snow, desert). Tilesets not listed have no weather.")]
		public readonly Dictionary<string, string> Climates = new()
		{
			{ "TEMPERAT", "temperate" }, { "SNOW", "snow" }, { "DESERT", "desert" }
		};

		[Desc("Map override: always this weather.")]
		public readonly PxWeatherType? Fixed = null;

		[Desc("Map override: the weather that can happen (Clear is always possible unless Fixed is set).")]
		public readonly PxWeatherType[] Allowed = null;

		[Desc("Chance (percent) that the next weather is clear skies.")]
		public readonly int ClearChance = 30;

		[Desc("Minutes between changes for Rare, Normal and Frequent (min, max).")]
		public readonly int2 RareMinutes = new(8, 12);
		public readonly int2 NormalMinutes = new(4, 8);
		public readonly int2 FrequentMinutes = new(2, 4);

		[Desc("Seconds a change takes to fade in.")]
		public readonly int TransitionSeconds = 20;

		[Desc("Seconds of warning before a change.")]
		public readonly int WarningSeconds = 30;

		[Desc("Looping ambience. Volume follows the weather.")]
		public readonly string RainSound = "ra|audio/weather/rain.wav";
		public readonly string HeavyRainSound = "ra|audio/weather/rain-heavy.wav";
		public readonly string WindSound = "ra|audio/weather/wind.wav";
		public readonly string SandSound = "ra|audio/weather/sand.wav";
		public readonly string[] ThunderSounds = { "ra|audio/weather/thunder1.wav", "ra|audio/weather/thunder2.wav", "ra|audio/weather/thunder3.wav" };

		public readonly float AmbienceVolume = 0.55f;
		public readonly float ThunderVolume = 0.9f;

		[FluentReference]
		const string Off = "options-weather.off";

		[FluentReference]
		const string Visual = "options-weather.visual";

		[FluentReference]
		const string Rare = "options-weather-changes.rare";

		[FluentReference]
		const string Normal = "options-weather-changes.normal";

		[FluentReference]
		const string Frequent = "options-weather-changes.frequent";

		IEnumerable<LobbyOption> ILobbyOptions.LobbyOptions(MapPreview map)
		{
			var modes = new Dictionary<string, string>
			{
				{ "off", FluentProvider.GetMessage(Off) },
				{ "visual", FluentProvider.GetMessage(Visual) },
			};

			yield return new LobbyOption(map, "weather", Label, Description, Visible, DisplayOrder, modes, Default, Locked);

			var changes = new Dictionary<string, string>
			{
				{ "rare", FluentProvider.GetMessage(Rare) },
				{ "normal", FluentProvider.GetMessage(Normal) },
				{ "frequent", FluentProvider.GetMessage(Frequent) },
			};

			yield return new LobbyOption(map, "weatherchanges", ChangesLabel, ChangesDescription, Visible, DisplayOrder + 1,
				changes, ChangesDefault, Locked);
		}

		public override object Create(ActorInitializer init) { return new PxWeatherManager(init.Self, this); }
	}

	/// <summary>What the weather looks like this frame. Channels are 0..1 unless noted.</summary>
	public sealed class PxWeatherFrame
	{
		public float Rain, Snow, Sand, Fog, Storm, Haze, Wind, Dark, Cloud, Dust;

		// Slow ground build-up
		public float Wetness, SnowCover, SandCover;

		// Wind direction (unit vector, world space) and integrated drift offsets (world pixels)
		public float2 WindDir = new(1, 0.3f);
		public float2 CloudOffset, FogOffset, DustOffset;
		public float Time;

		// Lightning: whole-sky flash and up to two visible bolts (start/end in world pixels)
		public float Flash;
		public readonly PxLightningBolt[] Bolts = { new(), new() };

		public float3 FogColor = new(0.72f, 0.75f, 0.78f);
		public float3 SandColor = new(0.78f, 0.6f, 0.4f);
		public float3 SnowColor = new(0.93f, 0.96f, 1f);
		public float3 DebrisColor = new(0.34f, 0.37f, 0.16f);
	}

	public sealed class PxLightningBolt
	{
		public float2 Start, End;
		public float Intensity, Seed, Age = 99, Branches;
	}

	public sealed class PxWeatherManager : ITick, IWorldLoaded, INotifyActorDisposing
	{
		[FluentReference("weather", "seconds")]
		const string Forecast = "notification-weather-forecast";

		[FluentReference("weather")]
		const string Arrived = "notification-weather-arrived";

		[FluentReference]
		const string NameClear = "label-weather.clear";

		[FluentReference]
		const string NameRain = "label-weather.rain";

		[FluentReference]
		const string NameThunderstorm = "label-weather.thunderstorm";

		[FluentReference]
		const string NameSnow = "label-weather.snow";

		[FluentReference]
		const string NameBlizzard = "label-weather.blizzard";

		[FluentReference]
		const string NameFog = "label-weather.fog";

		[FluentReference]
		const string NameSandstorm = "label-weather.sandstorm";

		[FluentReference]
		const string NameStrongWind = "label-weather.strongwind";

		[FluentReference]
		const string NameHeatHaze = "label-weather.heathaze";

		// Rain, Snow, Sand, Fog, Storm, Haze, Wind, Dark, Cloud, Dust
		static readonly Dictionary<PxWeatherType, float[]> Profiles = new()
		{
			{ PxWeatherType.Clear,        new[] { 0f,    0f,   0f,   0f,    0f,   0f,   0.15f, 0f,    0.35f, 0f } },
			{ PxWeatherType.Rain,         new[] { 0.6f,  0f,   0f,   0.15f, 0f,   0f,   0.35f, 0.25f, 0.8f,  0f } },
			{ PxWeatherType.Thunderstorm, new[] { 1f,    0f,   0f,   0.25f, 1f,   0f,   0.7f,  0.45f, 1f,    0f } },
			{ PxWeatherType.Snow,         new[] { 0f,    0.6f, 0f,   0.15f, 0f,   0f,   0.25f, 0.12f, 0.75f, 0f } },
			{ PxWeatherType.Blizzard,     new[] { 0f,    1f,   0f,   0.55f, 0f,   0f,   1f,    0.3f,  1f,    0f } },
			{ PxWeatherType.Fog,          new[] { 0f,    0f,   0f,   1f,    0f,   0f,   0.08f, 0.15f, 0.6f,  0f } },
			{ PxWeatherType.Sandstorm,    new[] { 0f,    0f,   1f,   0.3f,  0f,   0f,   1f,    0.25f, 0.5f,  1f } },
			{ PxWeatherType.StrongWind,   new[] { 0f,    0f,   0f,   0f,    0f,   0f,   1f,    0.05f, 0.55f, 0.35f } },
			{ PxWeatherType.HeatHaze,     new[] { 0f,    0f,   0f,   0f,    0f,   1f,   0.1f,  -0.08f, 0.1f, 0.1f } },
		};

		static readonly Dictionary<string, PxWeatherType[]> ClimateWeather = new()
		{
			{ "temperate", new[] { PxWeatherType.Rain, PxWeatherType.Thunderstorm, PxWeatherType.Fog, PxWeatherType.StrongWind } },
			{ "snow", new[] { PxWeatherType.Snow, PxWeatherType.Blizzard, PxWeatherType.Fog, PxWeatherType.StrongWind } },
			{ "desert", new[] { PxWeatherType.Sandstorm, PxWeatherType.StrongWind, PxWeatherType.HeatHaze } },
		};

		readonly PxWeatherManagerInfo info;
		readonly World world;
		readonly PxWeatherType[] allowed;
		readonly int2 changeMinutes;
		readonly PxWeatherFrame frame = new();
		readonly MersenneTwister localRandom = new();

		// Dev override
		readonly PxWeatherType[] devWeather;
		readonly int devTicks;
		readonly float devLightningEvery;
		readonly bool devLightningHold;

		int transitionStart = -100000, nextChange, scheduledAt, announced = -1;
		float windAngleFrom, windAngleTo, windAngle;

		WorldRenderer worldRenderer;
		long lastFrameTime = -1;
		double clock;
		float lightningTimer = 2;
		readonly List<(double Due, float Volume)> pendingThunder = new();
		ISound rainLoop, heavyRainLoop, windLoop, sandLoop;
		bool disposed;

		public bool Enabled { get; }
		public string Climate { get; }
		public PxWeatherType Current { get; private set; } = PxWeatherType.Clear;
		public PxWeatherType Next { get; private set; }

		/// <summary>False when the weather never changes (map override or dev weather): no forecast to show.</summary>
		public bool HasForecast => Enabled && devWeather == null && !(allowed.Length == 1 && info.Fixed != null);
		public int TicksUntilChange => Math.Max(0, nextChange - world.WorldTick);
		public int ForecastTotalTicks => Math.Max(1, nextChange - scheduledAt);
		public int TicksPerSecond { get; }
		public int WarningTicks => info.WarningSeconds * TicksPerSecond;
		public bool ChangeAnnounced => announced == nextChange;

		/// <summary>0..1 progress of the fade into the current weather (1 when settled).</summary>
		public float Transition => TransitionProgress();
		public PxWeatherType Previous { get; private set; } = PxWeatherType.Clear;

		public PxWeatherManager(Actor self, PxWeatherManagerInfo info)
		{
			this.info = info;
			world = self.World;
			TicksPerSecond = 1000 / world.Timestep;

			info.Climates.TryGetValue(world.Map.Tileset, out var climate);
			Climate = climate;

			var mode = world.LobbyInfo.GlobalSettings.OptionOrDefault("weather", info.Default);
			changeMinutes = world.LobbyInfo.GlobalSettings.OptionOrDefault("weatherchanges", info.ChangesDefault) switch
			{
				"rare" => info.RareMinutes,
				"frequent" => info.FrequentMinutes,
				_ => info.NormalMinutes,
			};

			var dev = Environment.GetEnvironmentVariable("RAPX_WEATHER");
			if (!string.IsNullOrEmpty(dev))
			{
				devWeather = dev.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
					.Select(s => FieldLoader.GetValue<PxWeatherType>("RAPX_WEATHER", s)).ToArray();
				devTicks = int.TryParse(Environment.GetEnvironmentVariable("RAPX_WEATHER_TICKS"), out var t) ? t : 50;
				devLightningHold = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RAPX_LIGHTNING_HOLD"));
				float.TryParse(Environment.GetEnvironmentVariable("RAPX_LIGHTNING_EVERY"), System.Globalization.NumberStyles.Float,
					System.Globalization.CultureInfo.InvariantCulture, out devLightningEvery);
			}

			if (info.Fixed != null)
				allowed = new[] { info.Fixed.Value };
			else if (info.Allowed != null)
				allowed = info.Allowed;
			else if (climate != null && ClimateWeather.TryGetValue(climate, out var list))
				allowed = list;
			else
				allowed = Array.Empty<PxWeatherType>();

			Enabled = world.Type == WorldType.Regular && (devWeather != null || (mode != "off" && allowed.Length > 0));

			switch (climate)
			{
				case "snow":
					frame.FogColor = new float3(0.82f, 0.86f, 0.9f);
					frame.DebrisColor = new float3(0.95f, 0.97f, 1f);
					break;
				case "desert":
					frame.FogColor = new float3(0.8f, 0.7f, 0.56f);
					frame.DebrisColor = new float3(0.72f, 0.56f, 0.38f);
					break;
			}
		}

		public static string WeatherName(PxWeatherType type)
		{
			return FluentProvider.GetMessage(type switch
			{
				PxWeatherType.Rain => NameRain,
				PxWeatherType.Thunderstorm => NameThunderstorm,
				PxWeatherType.Snow => NameSnow,
				PxWeatherType.Blizzard => NameBlizzard,
				PxWeatherType.Fog => NameFog,
				PxWeatherType.Sandstorm => NameSandstorm,
				PxWeatherType.StrongWind => NameStrongWind,
				PxWeatherType.HeatHaze => NameHeatHaze,
				_ => NameClear,
			});
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			worldRenderer = wr;
			if (!Enabled || devWeather != null)
				return;

			// The match starts with settled weather (no fade), so the first minutes are not always clear
			Previous = Current = PickWeather(PxWeatherType.Clear);
			if (Current == PxWeatherType.Rain || Current == PxWeatherType.Thunderstorm)
				frame.Wetness = 0.6f;
			if (Current == PxWeatherType.Snow || Current == PxWeatherType.Blizzard)
				frame.SnowCover = 0.6f;
			if (Current == PxWeatherType.Sandstorm)
				frame.SandCover = 0.5f;

			windAngleFrom = windAngleTo = windAngle = NextAngle();
			ScheduleNext();
		}

		PxWeatherType PickWeather(PxWeatherType current)
		{
			if (allowed.Length == 1 && info.Fixed != null)
				return allowed[0];

			if (current != PxWeatherType.Clear && world.SharedRandom.Next(100) < info.ClearChance)
				return PxWeatherType.Clear;

			// Never the same weather twice in a row, and storms build from clear or rain only rarely skip
			var options = allowed.Where(a => a != current).ToArray();
			return options.Length == 0 ? current : options[world.SharedRandom.Next(options.Length)];
		}

		float NextAngle()
		{
			// Mostly from the west, like real prevailing winds, with some spread
			return (world.SharedRandom.Next(-70, 70) + (world.SharedRandom.Next(100) < 25 ? 180 : 0)) * MathF.PI / 180f;
		}

		void ScheduleNext()
		{
			var seconds = world.SharedRandom.Next(changeMinutes.X * 60, changeMinutes.Y * 60 + 1);

			// RAPX_WEATHER_CHANGE_SECONDS: dev override so changes, forecasts and fades can be tested quickly
			if (int.TryParse(Environment.GetEnvironmentVariable("RAPX_WEATHER_CHANGE_SECONDS"), out var devSeconds) && devSeconds > 0)
				seconds = devSeconds;

			scheduledAt = world.WorldTick;
			nextChange = scheduledAt + seconds * TicksPerSecond;
			Next = PickWeather(Current);
		}

		void ITick.Tick(Actor self)
		{
			if (!Enabled)
				return;

			var tick = world.WorldTick;
			if (devWeather != null)
			{
				var i = Math.Clamp((tick - 60) / Math.Max(1, devTicks), 0, devWeather.Length - 1);
				if (devWeather[i] != Current || tick == 1)
				{
					Previous = Current = devWeather[i];
					transitionStart = -100000;
					var p = Profiles[Current];
					frame.Wetness = p[0] > 0 ? 1 : 0;
					frame.SnowCover = p[1] > 0 ? 1 : 0;
					frame.SandCover = p[2] > 0 ? 1 : 0;
					windAngle = windAngleFrom = windAngleTo = 0.35f;
				}

				return;
			}

			if (allowed.Length == 1 && info.Fixed != null)
				return;

			var warning = info.WarningSeconds * TicksPerSecond;
			if (announced != nextChange && tick >= nextChange - warning && Next != Current)
			{
				announced = nextChange;
				TextNotificationsManager.AddSystemLine(Forecast, "weather", WeatherName(Next), "seconds", info.WarningSeconds);
			}

			if (tick >= nextChange)
			{
				if (Next != Current)
				{
					Previous = BlendedType();
					Current = Next;
					transitionStart = tick;
					windAngleFrom = windAngle;
					windAngleTo = NextAngle();
					TextNotificationsManager.AddSystemLine(Arrived, "weather", WeatherName(Current));
				}

				ScheduleNext();
			}
		}

		// A change that interrupts another fade starts from whichever weather was further along
		PxWeatherType BlendedType()
		{
			return TransitionProgress() < 0.5f ? Previous : Current;
		}

		float TransitionProgress()
		{
			var t = (world.WorldTick - transitionStart) / (float)(info.TransitionSeconds * TicksPerSecond);
			t = Math.Clamp(t, 0, 1);
			return t * t * (3 - 2 * t);
		}

		/// <summary>Visual state for this frame. Cheap to call several times per frame.</summary>
		public PxWeatherFrame Frame()
		{
			var now = Game.RunTime;
			if (now == lastFrameTime || worldRenderer == null)
				return frame;

			var dt = lastFrameTime < 0 ? 0 : Math.Min((now - lastFrameTime) / 1000f, 0.1f);
			lastFrameTime = now;
			var paused = world.Paused;
			if (paused)
				dt = 0;

			clock += dt;
			frame.Time = (float)(clock % 3600);

			var k = TransitionProgress();
			var a = Profiles[Previous];
			var b = Profiles[Current];
			float Mix(int i) => a[i] + (b[i] - a[i]) * k;
			frame.Rain = Mix(0);
			frame.Snow = Mix(1);
			frame.Sand = Mix(2);
			frame.Fog = Mix(3);
			frame.Storm = Mix(4);
			frame.Haze = Mix(5);
			frame.Wind = Mix(6);
			frame.Dark = Mix(7);
			frame.Cloud = Mix(8);
			frame.Dust = Mix(9);

			// Gusts: the wind breathes on a ~10 s cycle
			var gust = 0.8f + 0.2f * MathF.Sin(frame.Time * 0.6f) * MathF.Sin(frame.Time * 0.23f + 1.3f);
			var wind = frame.Wind * gust;

			var angleK = Math.Clamp((world.WorldTick - transitionStart) / (float)(info.TransitionSeconds * 2 * TicksPerSecond), 0, 1);
			windAngle = windAngleFrom + (windAngleTo - windAngleFrom) * angleK;
			frame.WindDir = new float2(MathF.Cos(windAngle), MathF.Sin(windAngle) * 0.6f);
			var speed = 8f + 160f * wind;
			frame.CloudOffset += frame.WindDir * (speed * 0.35f * dt);
			frame.FogOffset += frame.WindDir * ((6f + 40f * wind) * dt);
			frame.DustOffset += frame.WindDir * (speed * 2.2f * dt);

			// Ground build-up: rain soaks in fast and dries slowly, snow settles over a couple of minutes
			frame.Wetness = Approach(frame.Wetness, frame.Rain > 0.05f ? Math.Min(1, frame.Rain * 1.6f) : 0, dt / 35f, dt / 110f);
			frame.SnowCover = Approach(frame.SnowCover, frame.Snow > 0.05f ? Math.Min(1, 0.5f + frame.Snow) : 0, dt / 80f, dt / 200f);
			frame.SandCover = Approach(frame.SandCover, frame.Sand > 0.05f ? frame.Sand : 0, dt / 50f, dt / 150f);

			UpdateLightning(worldRenderer, dt);
			UpdateSound();
			return frame;
		}

		static float Approach(float value, float target, float up, float down)
		{
			return value < target ? Math.Min(target, value + up) : Math.Max(target, value - down);
		}

		void UpdateLightning(WorldRenderer wr, float dt)
		{
			foreach (var bolt in frame.Bolts)
			{
				bolt.Age += dt;

				// A main stroke and two return strokes, each a sharp flicker
				var t = bolt.Age;
				bolt.Intensity = t > 0.9f ? 0 : Stroke(t, 0f, 1f) + Stroke(t, 0.11f, 0.7f) + Stroke(t, 0.26f, 0.85f) + Stroke(t, 0.5f, 0.35f);

				// Dev screenshots: keep the newest bolt lit so a shot can catch it
				if (devLightningHold && t < 99)
					bolt.Intensity = t < devLightningEvery ? 0.9f : 0;
			}

			frame.Flash = Math.Max(0, frame.Flash - dt * 3.5f);
			for (var i = pendingThunder.Count - 1; i >= 0; i--)
			{
				var (due, volume) = pendingThunder[i];
				if (clock < due)
					continue;

				pendingThunder.RemoveAt(i);
				Game.Sound.Play(SoundType.World, info.ThunderSounds.Random(localRandom), volume * info.ThunderVolume);
			}

			if (frame.Storm < 0.3f)
				return;

			lightningTimer -= dt;
			if (lightningTimer > 0)
				return;

			lightningTimer = devLightningEvery > 0 ? devLightningEvery
				: (2.5f + localRandom.NextFloat() * 9f) / Math.Max(frame.Storm, 0.3f);

			// Strikes land around the view (purely cosmetic, so a local random is fine);
			// a third are hidden in the clouds and only light the sky
			var vp = wr.Viewport;
			var tl = vp.TopLeft;
			var br = vp.BottomRight;
			var size = new float2(br.X - tl.X, br.Y - tl.Y);
			var end = new float2(tl.X + size.X * (-0.2f + 1.4f * localRandom.NextFloat()),
				tl.Y + size.Y * (0.1f + 1.0f * localRandom.NextFloat()));
			if (devLightningEvery > 0)
				end = new float2(tl.X + size.X * (0.35f + 0.3f * localRandom.NextFloat()), tl.Y + size.Y * 0.62f);

			var hidden = devLightningEvery <= 0 && localRandom.Next(100) < 33;
			if (!hidden)
			{
				var bolt = frame.Bolts[0].Age < frame.Bolts[1].Age ? frame.Bolts[1] : frame.Bolts[0];
				bolt.End = end;
				bolt.Start = new float2(end.X - frame.WindDir.X * 260 + localRandom.NextFloat() * 300 - 150, end.Y - 1300);
				bolt.Seed = localRandom.NextFloat() * 100;
				bolt.Branches = 1 + localRandom.Next(3);
				bolt.Age = 0;
			}

			frame.Flash = Math.Min(1f, frame.Flash + (hidden ? 0.4f : 0.8f));

			// Thunder follows the flash; farther strikes rumble later and quieter
			var center = vp.CenterLocation;
			var dist = (new float2(center.X, center.Y) - end).Length / Math.Max(size.X, 1);
			var delay = 0.15f + dist * 1.6f + (hidden ? 0.8f : 0);
			pendingThunder.Add((clock + delay, Math.Clamp(1.1f - dist * 0.5f, 0.35f, 1f) * (hidden ? 0.6f : 1f)));
		}

		static float Stroke(float t, float at, float strength)
		{
			var x = t - at;
			if (x < 0)
				return 0;

			return strength * MathF.Exp(-x * 14f) * (0.75f + 0.25f * MathF.Sin(x * 90f));
		}

		void UpdateSound()
		{
			if (disposed || Game.Sound == null)
				return;

			var master = Game.Sound.SoundVolume * info.AmbienceVolume;
			var light = frame.Rain * Math.Clamp(1.4f - frame.Storm, 0, 1);
			var heavy = frame.Rain * frame.Storm;
			var wind = Math.Max(0, frame.Wind - 0.3f) * 1.3f * (1 - frame.Sand * 0.6f);
			UpdateLoop(ref rainLoop, info.RainSound, master * light);
			UpdateLoop(ref heavyRainLoop, info.HeavyRainSound, master * heavy);
			UpdateLoop(ref windLoop, info.WindSound, master * Math.Min(1, wind + frame.Snow * frame.Wind * 0.5f));
			UpdateLoop(ref sandLoop, info.SandSound, master * frame.Sand);
		}

		static void UpdateLoop(ref ISound loop, string sound, float volume)
		{
			if (volume < 0.005f)
			{
				if (loop != null)
				{
					Game.Sound.StopSound(loop);
					loop = null;
				}

				return;
			}

			loop ??= Game.Sound.PlayLooped(SoundType.World, sound);
			if (loop != null)
				loop.Volume = volume;
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			disposed = true;
			foreach (var loop in new[] { rainLoop, heavyRainLoop, windLoop, sandLoop })
				if (loop != null)
					Game.Sound.StopSound(loop);
		}
	}
}
