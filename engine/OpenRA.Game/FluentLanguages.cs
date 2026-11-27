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

namespace OpenRA
{
	public class FluentLanguage
	{
		public readonly string Id;

		[Desc("English name of the language.")]
		public readonly string Name;

		[Desc("Name of the language in itself.")]
		public readonly string NativeName;

		[Desc("Fluent files loaded on top of the mod's FluentMessages. Missing keys fall back to the defaults.")]
		public readonly string[] Messages = Array.Empty<string>();

		[Desc("Font files replaced while this language is active (default font -> replacement).")]
		public readonly Dictionary<string, string> Fonts = new();

		public FluentLanguage(string id, MiniYaml yaml)
		{
			Id = id;
			FieldLoader.Load(this, yaml);
		}
	}

	/// <summary>Interface languages, picked with Game.Settings.Player.Language.</summary>
	public class FluentLanguages : IGlobalModData
	{
		public const string DefaultLanguage = "en";

		public readonly IReadOnlyList<FluentLanguage> Languages;

		[Desc("Fonts tried, in order, for characters the main font does not have.")]
		public readonly string[] FallbackFonts = Array.Empty<string>();

		public FluentLanguages(MiniYaml yaml)
		{
			var languages = new List<FluentLanguage>();
			foreach (var node in yaml.Nodes)
			{
				if (node.Key == "FallbackFonts")
					FallbackFonts = FieldLoader.GetValue<string[]>(node.Key, node.Value.Value);
				else
					languages.Add(new FluentLanguage(node.Key, node.Value));
			}

			Languages = languages;
		}

		public static string SelectedId => Game.Settings?.Player.Language ?? DefaultLanguage;

		public static FluentLanguages For(Manifest manifest)
		{
			return manifest.Contains<FluentLanguages>() ? manifest.Get<FluentLanguages>() : null;
		}

		public FluentLanguage Active => Languages.FirstOrDefault(l => l.Id == SelectedId);

		public string FontFor(string font)
		{
			var active = Active;
			return active != null && active.Fonts.TryGetValue(font, out var replacement) ? replacement : font;
		}
	}
}
