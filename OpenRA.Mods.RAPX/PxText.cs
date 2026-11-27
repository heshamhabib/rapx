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
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace OpenRA.Mods.RAPX
{
	/// <summary>
	/// Translatable text written in C#: PxText.T("NO SELECTION") looks the English text up as a Fluent message whose
	/// key is derived from the text, so code keeps reading naturally. tools/lang/l10n.py texts collects every call
	/// into fluent/px-text.ftl; translations go in fluent/lang/&lt;id&gt;/. Only plain string literals are collected:
	/// use F("{0} AVAILABLE", count) for values, never an interpolated string.
	/// </summary>
	public static class PxText
	{
		static readonly Dictionary<string, string> Cache = new();
		static readonly Regex NonSlug = new("[^a-z0-9]+");
		static ModData cacheOwner;

		/// <summary>Must match slug() in tools/lang/l10n.py.</summary>
		public static string Key(string text)
		{
			var s = NonSlug.Replace(text.ToLowerInvariant(), "-").Trim('-');
			if (s.Length > 48)
				s = s[..48].Trim('-');

			uint h = 0;
			foreach (var b in Encoding.UTF8.GetBytes(text))
				h = h * 31 + b;

			var hash = (h % 46656).ToString("x", CultureInfo.InvariantCulture);
			return s.Length > 0 ? $"px-text-{s}-{hash}" : $"px-text-{hash}";
		}

		public static string T(string text)
		{
			lock (Cache)
			{
				// The language (and so the messages) changes when the mod reloads
				if (cacheOwner != Game.ModData)
				{
					Cache.Clear();
					cacheOwner = Game.ModData;
				}

				if (!Cache.TryGetValue(text, out var message))
					Cache[text] = message = FluentProvider.TryGetMessage(Key(text), out var m) ? m : text;

				return message;
			}
		}

		/// <summary>Marks English text kept in data (static tables, ids that double as labels) for collection. Translate it with T where it is drawn.</summary>
		public static string N(string text) => text;

		public static string F(string text, params object[] args)
		{
			var fluentArgs = new object[args.Length * 2];
			for (var i = 0; i < args.Length; i++)
			{
				fluentArgs[2 * i] = "p" + i.ToString(CultureInfo.InvariantCulture);
				fluentArgs[2 * i + 1] = args[i] is string s ? s : (object)System.Convert.ToString(args[i], CultureInfo.InvariantCulture);
			}

			return FluentProvider.TryGetMessage(Key(text), out var message, fluentArgs)
				? message : string.Format(CultureInfo.InvariantCulture, text, args);
		}
	}
}
