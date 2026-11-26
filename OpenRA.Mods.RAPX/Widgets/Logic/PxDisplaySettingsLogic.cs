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
using System.Text.RegularExpressions;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Support;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Binds the mod's graphics quality checkboxes on the Display settings panel (listed after DisplaySettingsLogic).
	/// Both settings apply immediately; the stock settings panel saves them when it closes.
	/// Also shows which graphics card the game draws with and, on Windows PCs with more than one, which card Windows
	/// should start the game on.
	/// </summary>
	public class PxDisplaySettingsLogic : ChromeLogic
	{
		[FluentReference]
		const string WeatherDetailHigh = "dropdown-px-weather-detail.high";

		[FluentReference]
		const string WeatherDetailMedium = "dropdown-px-weather-detail.medium";

		[FluentReference]
		const string WeatherDetailLow = "dropdown-px-weather-detail.low";

		[FluentReference]
		const string HighPerformance = "dropdown-px-gpu-preference.high";

		[FluentReference]
		const string PowerSaving = "dropdown-px-gpu-preference.saving";

		[FluentReference]
		const string WindowsDecides = "dropdown-px-gpu-preference.windows";

		[FluentReference("name")]
		const string CardInUse = "label-px-gpu-in-use";

		[FluentReference]
		const string CardUnknown = "label-px-gpu-unknown";

		[FluentReference("version")]
		const string Direct3DVersion = "label-px-gpu-direct3d";

		[FluentReference("version")]
		const string OpenGLVersion = "label-px-gpu-opengl";

		[FluentReference("api", "version")]
		const string DriverVersion = "label-px-gpu-driver";

		[FluentReference("api", "names")]
		const string OtherCards = "label-px-gpu-others";

		[FluentReference("api", "names")]
		const string AllCards = "label-px-gpu-all";

		[FluentReference]
		const string HintIntegrated = "label-px-gpu-hint-integrated";

		[FluentReference]
		const string HintSoftware = "label-px-gpu-hint-software";

		[FluentReference]
		const string HintNoDriver = "label-px-gpu-hint-no-driver";

		[FluentReference]
		const string HintRestart = "label-px-gpu-hint-restart";

		// "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Laptop GPU (0x00002560) Direct3D11 vs_5_0 ps_5_0, D3D11-31.0.15.3623)";
		// older ANGLE builds leave out the vendor, the device id and the driver version
		static readonly Regex AngleRenderer = new(
			@"^ANGLE \((?:(?<vendor>[^,()]*), )?(?<name>.*?)(?: \(0x[0-9A-Fa-f]+\))? Direct3D(?<d3d>\d+)[^,)]*(?:, D3D\d+-(?<driver>[0-9.]+))?",
			RegexOptions.CultureInvariant);

		static readonly string[] SoftwareRenderers = { "llvmpipe", "softpipe", "lavapipe", "swrast", "SwiftShader", "Basic Render", "GDI Generic" };

		// The choice Windows held for the game when it started: a different one applies after a restart
		static readonly WindowsGpu.Preference? StartupPreference = WindowsGpu.GetPreference(WindowsGpu.GameExecutable);

		// Listing the cards takes a few milliseconds, and they do not change while the game runs
		static IReadOnlyList<WindowsGpu.Adapter> adapters;

		[ObjectCreator.UseCtor]
		public PxDisplaySettingsLogic(Widget widget)
		{
			var ds = Game.Settings.Graphics;

			var hdWorld = widget.Get<CheckboxWidget>("PX_HD_WORLD_CHECKBOX");
			hdWorld.IsChecked = () => ds.NativeResolutionWorld;
			hdWorld.OnClick = () =>
			{
				ds.NativeResolutionWorld ^= true;
				Game.Renderer.RefreshWorldBuffer();
			};

			var smoothMotion = widget.Get<CheckboxWidget>("PX_SMOOTH_MOTION_CHECKBOX");
			smoothMotion.IsChecked = () => ds.SmoothMotion;
			smoothMotion.OnClick = () => ds.SmoothMotion ^= true;

			// The passes these two switch off are built when a world loads, so the change lands on the next
			// match rather than the one being played. Both are the difference between a slideshow and a
			// playable frame rate on an integrated GPU.
			var groundEffects = widget.Get<CheckboxWidget>("PX_GROUND_EFFECTS_CHECKBOX");
			groundEffects.IsChecked = () => ds.GroundEffects;
			groundEffects.OnClick = () => ds.GroundEffects ^= true;

			var weatherEffects = widget.Get<CheckboxWidget>("PX_WEATHER_EFFECTS_CHECKBOX");
			weatherEffects.IsChecked = () => ds.WeatherEffects;
			weatherEffects.OnClick = () => ds.WeatherEffects ^= true;

			BindWeatherDetail(widget, ds);
			BindGraphicsCard(widget);
		}

		/// <summary>
		/// Unlike the two checkboxes above, this one lands on the frame after it is picked: the passes are already
		/// built and only read the tier per frame. A storm is the most expensive thing drawn, so it is the dial that
		/// buys frames back without giving up the weather.
		/// </summary>
		static void BindWeatherDetail(Widget widget, GraphicSettings ds)
		{
			var labels = new Dictionary<int, string>
			{
				{ 2, FluentProvider.GetMessage(WeatherDetailHigh) },
				{ 1, FluentProvider.GetMessage(WeatherDetailMedium) },
				{ 0, FluentProvider.GetMessage(WeatherDetailLow) },
			};

			var dropdown = widget.Get<DropDownButtonWidget>("PX_WEATHER_DETAIL_DROPDOWN");
			dropdown.GetText = () => labels[Math.Clamp(ds.WeatherDetail, 0, 2)];
			dropdown.OnMouseDown = _ =>
			{
				ScrollItemWidget SetupItem(int option, ScrollItemWidget template)
				{
					var item = ScrollItemWidget.Setup(template,
						() => Math.Clamp(ds.WeatherDetail, 0, 2) == option,
						() => ds.WeatherDetail = option);

					item.Get<LabelWidget>("LABEL").GetText = () => labels[option];
					return item;
				}

				dropdown.ShowDropDown("LABEL_DROPDOWN_TEMPLATE", 500, labels.Keys, SetupItem);
			};
		}

		static void BindGraphicsCard(Widget widget)
		{
			var executable = WindowsGpu.GameExecutable;
			adapters ??= WindowsGpu.Adapters();

			var card = new CardInfo(GraphicsCard.Renderer, Game.Renderer.GLVersion);
			var inUse = adapters.FirstOrDefault(a => card.Matches(a.Name));

			var preference = WindowsGpu.GetPreference(executable) ?? WindowsGpu.Preference.WindowsDecides;
			var startup = StartupPreference ?? WindowsGpu.Preference.WindowsDecides;

			// The choice only means something to Windows, for the game's own executable, with more than one card to choose from
			var preferenceContainer = widget.Get("PX_GPU_PREFERENCE_CONTAINER");
			preferenceContainer.IsVisible = () => executable != null && adapters.Count > 1;

			var labels = new Dictionary<WindowsGpu.Preference, string>
			{
				{ WindowsGpu.Preference.HighPerformance, FluentProvider.GetMessage(HighPerformance) },
				{ WindowsGpu.Preference.PowerSaving, FluentProvider.GetMessage(PowerSaving) },
				{ WindowsGpu.Preference.WindowsDecides, FluentProvider.GetMessage(WindowsDecides) },
			};

			var dropdown = preferenceContainer.Get<DropDownButtonWidget>("PX_GPU_PREFERENCE_DROPDOWN");
			dropdown.GetText = () => labels[preference];
			dropdown.OnMouseDown = _ =>
			{
				ScrollItemWidget SetupItem(WindowsGpu.Preference option, ScrollItemWidget template)
				{
					var item = ScrollItemWidget.Setup(template,
						() => preference == option,
						() =>
						{
							if (WindowsGpu.SetPreference(executable, option))
								preference = option;
						});

					item.Get<LabelWidget>("LABEL").GetText = () => labels[option];
					return item;
				}

				dropdown.ShowDropDown("LABEL_DROPDOWN_TEMPLATE", 500, labels.Keys, SetupItem);
			};

			var name = FluentProvider.GetMessage(CardInUse, "name", card.Name ?? FluentProvider.GetMessage(CardUnknown));
			SetFittedText(widget.Get<LabelWidget>("PX_GPU_NAME"), name);

			var api = card.Driver != null ? FluentProvider.GetMessage(DriverVersion, "api", card.Api, "version", card.Driver) : card.Api;
			var others = adapters.Where(a => a != inUse).Select(a => CardInfo.Tidy(a.Name)).ToList();
			var detail = others.Count == 0 ? api
				: FluentProvider.GetMessage(inUse != null ? OtherCards : AllCards, "api", api, "names", string.Join(", ", others));
			SetFittedText(widget.Get<LabelWidget>("PX_GPU_DETAIL"), detail);

			// One hint at most, the most useful first
			var restart = FluentProvider.GetMessage(HintRestart);
			string hint = null;
			if (card.Software)
				hint = FluentProvider.GetMessage(HintSoftware);
			else if (adapters.Any(a => a.NoDriver))
				hint = FluentProvider.GetMessage(HintNoDriver);
			else if (executable != null && inUse != null && inUse.Integrated && startup != WindowsGpu.Preference.HighPerformance &&
					adapters.Any(a => !a.Integrated && !a.NoDriver))
				hint = FluentProvider.GetMessage(HintIntegrated);

			widget.Get<LabelWidget>("PX_GPU_HINT").GetText = () => preference != startup ? restart : hint;
		}

		static void SetFittedText(LabelWidget label, string text)
		{
			var fitted = WidgetUtils.TruncateText(text, label.Bounds.Width, Game.Renderer.Fonts[label.Font]);
			label.GetText = () => fitted;
		}

		/// <summary>The graphics card in use as the player knows it, from the names its driver reports.</summary>
		sealed class CardInfo
		{
			public readonly string Name;
			public readonly string Api;
			public readonly string Driver;
			public readonly bool Software;

			public CardInfo(string renderer, string version)
			{
				version ??= "";
				Api = version.StartsWith("OpenGL", StringComparison.Ordinal) ? version : FluentProvider.GetMessage(OpenGLVersion, "version", version);
				if (string.IsNullOrEmpty(renderer))
					return;

				Software = SoftwareRenderers.Any(s => renderer.Contains(s, StringComparison.OrdinalIgnoreCase));

				var angle = AngleRenderer.Match(renderer);
				if (angle.Success)
				{
					Name = TidyOrNull(angle.Groups["name"].Value);
					Api = FluentProvider.GetMessage(Direct3DVersion, "version", angle.Groups["d3d"].Value);
					if (angle.Groups["driver"].Success)
						Driver = angle.Groups["driver"].Value;

					return;
				}

				var name = renderer;
				if (name.StartsWith("ANGLE (", StringComparison.Ordinal) && name.EndsWith(')'))
					name = name[7..^1];

				// "NVIDIA GeForce RTX 3060/PCIe/SSE2", and macOS's "AMD Radeon Pro 5500M OpenGL Engine"
				name = Regex.Replace(name, "/(?:PCIe|PCI|AGP)(?:/SSE2?)?$| OpenGL Engine$", "");

				// Mesa: "Mesa Intel(R) UHD Graphics 620 (KBL GT2)", "AMD Radeon RX 6700 XT (navi22, LLVM 15.0.7, DRM 3.49, 6.1.0)"
				if (version.Contains("Mesa", StringComparison.Ordinal))
					name = Regex.Replace(name, @"^Mesa (?:DRI )?| \([^()]*\)$", "");

				Name = TidyOrNull(name);
			}

			/// <summary>Without the trademark marks: "Intel(R) Iris(R) Xe Graphics" reads "Intel Iris Xe Graphics".</summary>
			public static string Tidy(string name)
			{
				return Regex.Replace(Regex.Replace(name, @"\((?:R|TM)\)", "", RegexOptions.IgnoreCase), @"\s+", " ").Trim();
			}

			static string TidyOrNull(string name)
			{
				var tidy = Tidy(name);
				return tidy.Length > 0 ? tidy : null;
			}

			/// <summary>Whether a card Windows lists is this one (OpenGL drivers may shorten or extend its name).</summary>
			public bool Matches(string adapterName)
			{
				var other = Tidy(adapterName ?? "");
				return Name != null && other.Length > 0 &&
					(other.Contains(Name, StringComparison.OrdinalIgnoreCase) || Name.Contains(other, StringComparison.OrdinalIgnoreCase));
			}
		}
	}
}
