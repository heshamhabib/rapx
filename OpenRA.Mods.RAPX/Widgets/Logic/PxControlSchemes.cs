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
using System.Linq;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// Control scheme presets (IDEA-11): each one sets the mouse settings and the whole hotkey set at once.
	/// The RA2 hotkeys live in controls/ra2-hotkeys.yaml; every key not listed there uses its default.
	/// </summary>
	public static class PxControlSchemes
	{
		public const string RA2 = "ra2";
		public const string RA2RightClick = "ra2-right";
		public const string OpenRA = "openra";
		public const string Custom = "custom";

		public static readonly string[] Presets = { RA2, RA2RightClick, OpenRA };

		[FluentReference]
		const string NameRA2 = "options-px-control-scheme.ra2";

		[FluentReference]
		const string NameRA2RightClick = "options-px-control-scheme.ra2-right";

		[FluentReference]
		const string NameOpenRA = "options-px-control-scheme.openra";

		[FluentReference]
		const string NameCustom = "options-px-control-scheme.custom";

		[FluentReference]
		const string DescRA2 = "label-px-control-scheme-desc.ra2";

		[FluentReference]
		const string DescRA2RightClick = "label-px-control-scheme-desc.ra2-right";

		[FluentReference]
		const string DescOpenRA = "label-px-control-scheme-desc.openra";

		[FluentReference]
		const string DescCustom = "label-px-control-scheme-desc.custom";

		const string RA2HotkeysFile = "ra|controls/ra2-hotkeys.yaml";

		static Dictionary<string, Hotkey> ra2Hotkeys;

		public static string Name(string scheme)
		{
			return FluentProvider.GetMessage(scheme switch
			{
				RA2 => NameRA2,
				RA2RightClick => NameRA2RightClick,
				OpenRA => NameOpenRA,
				_ => NameCustom,
			});
		}

		public static string Description(string scheme)
		{
			return FluentProvider.GetMessage(scheme switch
			{
				RA2 => DescRA2,
				RA2RightClick => DescRA2RightClick,
				OpenRA => DescOpenRA,
				_ => DescCustom,
			});
		}

		sealed class MouseSetup
		{
			public bool ClassicMouseStyle;
			public bool AlternateScrollButton;
			public MouseScrollType MouseScroll;
		}

		static MouseSetup MouseFor(string scheme)
		{
			var defaults = new GameSettings();
			return scheme switch
			{
				// Left click selects and gives orders, right click deselects, hold right and drag to scroll
				RA2 => new MouseSetup { ClassicMouseStyle = true, AlternateScrollButton = false, MouseScroll = MouseScrollType.Joystick },

				// Right click gives orders; right drag still scrolls (a drag never issues an order)
				RA2RightClick => new MouseSetup { ClassicMouseStyle = false, AlternateScrollButton = true, MouseScroll = MouseScrollType.Joystick },

				_ => new MouseSetup
				{
					ClassicMouseStyle = defaults.UseClassicMouseStyle,
					AlternateScrollButton = defaults.UseAlternateScrollButton,
					MouseScroll = defaults.MouseScroll
				},
			};
		}

		static Dictionary<string, Hotkey> HotkeysFor(ModData modData, string scheme)
		{
			if (scheme == OpenRA)
				return new Dictionary<string, Hotkey>();

			if (ra2Hotkeys == null)
			{
				ra2Hotkeys = new Dictionary<string, Hotkey>();
				using (var stream = modData.DefaultFileSystem.Open(RA2HotkeysFile))
				{
					foreach (var node in MiniYaml.FromStream(stream, RA2HotkeysFile))
					{
						Hotkey.TryParse(node.Value.Value, out var key);
						ra2Hotkeys[node.Key] = key;
					}
				}
			}

			return ra2Hotkeys;
		}

		// Hotkey == treats two unbound keys as different; for schemes they are the same
		static bool SameKey(Hotkey a, Hotkey b)
		{
			return a.IsValid() ? a == b : !b.IsValid();
		}

		static Hotkey KeyFor(HotkeyDefinition definition, Dictionary<string, Hotkey> overrides)
		{
			return overrides.TryGetValue(definition.Name, out var key) ? key : definition.Default;
		}

		public static void Apply(ModData modData, string scheme)
		{
			var gs = Game.Settings.Game;
			var mouse = MouseFor(scheme);
			gs.UseClassicMouseStyle = mouse.ClassicMouseStyle;
			gs.UseAlternateScrollButton = mouse.AlternateScrollButton;
			gs.MouseScroll = mouse.MouseScroll;

			var overrides = HotkeysFor(modData, scheme);
			foreach (var definition in modData.Hotkeys.Definitions.ToList())
				modData.Hotkeys.Set(definition.Name, KeyFor(definition, overrides));

			Game.Settings.Save();
		}

		/// <summary>Settings that differ from the scheme, for debugging.</summary>
		public static IEnumerable<string> Differences(ModData modData, string scheme)
		{
			var gs = Game.Settings.Game;
			var mouse = MouseFor(scheme);
			if (gs.UseClassicMouseStyle != mouse.ClassicMouseStyle)
				yield return "UseClassicMouseStyle";
			if (gs.UseAlternateScrollButton != mouse.AlternateScrollButton)
				yield return "UseAlternateScrollButton";
			if (gs.MouseScroll != mouse.MouseScroll)
				yield return "MouseScroll";

			var overrides = HotkeysFor(modData, scheme);
			foreach (var d in modData.Hotkeys.Definitions)
				if (!d.Readonly && !SameKey(modData.Hotkeys[d.Name].GetValue(), KeyFor(d, overrides)))
					yield return $"{d.Name}={modData.Hotkeys[d.Name].GetValue().DisplayString()} (want {KeyFor(d, overrides).DisplayString()})";
		}

		/// <summary>Returns the preset that matches the current settings exactly, or <see cref="Custom"/>.</summary>
		public static string Current(ModData modData)
		{
			var gs = Game.Settings.Game;
			foreach (var scheme in Presets)
			{
				var mouse = MouseFor(scheme);
				if (gs.UseClassicMouseStyle != mouse.ClassicMouseStyle ||
					gs.UseAlternateScrollButton != mouse.AlternateScrollButton ||
					gs.MouseScroll != mouse.MouseScroll)
					continue;

				var overrides = HotkeysFor(modData, scheme);
				if (modData.Hotkeys.Definitions.All(d => d.Readonly || SameKey(modData.Hotkeys[d.Name].GetValue(), KeyFor(d, overrides))))
					return scheme;
			}

			return Custom;
		}
	}
}
