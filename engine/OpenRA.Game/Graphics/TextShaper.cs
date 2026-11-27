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
using System.Text;

namespace OpenRA.Graphics
{
	/// <summary>
	/// Arabic support for the glyph-by-glyph font renderer: joins letters into their presentation forms and
	/// lays right-to-left lines out in visual order, keeping Latin words and numbers left-to-right.
	/// Text without Arabic letters is returned unchanged.
	/// </summary>
	public static class TextShaper
	{
		// Letter -> its first presentation form (FExx isolated form) and whether it also joins to the next letter.
		// Final, initial and medial forms follow the isolated one; right-joining letters have only isolated + final.
		static readonly Dictionary<char, (int Form, bool Dual)> Letters = new()
		{
			{ 'آ', (0xFE81, false) }, { 'أ', (0xFE83, false) }, { 'ؤ', (0xFE85, false) },
			{ 'إ', (0xFE87, false) }, { 'ئ', (0xFE89, true) }, { 'ا', (0xFE8D, false) },
			{ 'ب', (0xFE8F, true) }, { 'ة', (0xFE93, false) }, { 'ت', (0xFE95, true) },
			{ 'ث', (0xFE99, true) }, { 'ج', (0xFE9D, true) }, { 'ح', (0xFEA1, true) },
			{ 'خ', (0xFEA5, true) }, { 'د', (0xFEA9, false) }, { 'ذ', (0xFEAB, false) },
			{ 'ر', (0xFEAD, false) }, { 'ز', (0xFEAF, false) }, { 'س', (0xFEB1, true) },
			{ 'ش', (0xFEB5, true) }, { 'ص', (0xFEB9, true) }, { 'ض', (0xFEBD, true) },
			{ 'ط', (0xFEC1, true) }, { 'ظ', (0xFEC5, true) }, { 'ع', (0xFEC9, true) },
			{ 'غ', (0xFECD, true) }, { 'ف', (0xFED1, true) }, { 'ق', (0xFED5, true) },
			{ 'ك', (0xFED9, true) }, { 'ل', (0xFEDD, true) }, { 'م', (0xFEE1, true) },
			{ 'ن', (0xFEE5, true) }, { 'ه', (0xFEE9, true) }, { 'و', (0xFEED, false) },
			{ 'ى', (0xFEEF, false) }, { 'ي', (0xFEF1, true) },
		};

		// Alef variant -> isolated lam-alef ligature (the final form follows it)
		static readonly Dictionary<char, int> LamAlef = new()
		{
			{ 'آ', 0xFEF5 }, { 'أ', 0xFEF7 }, { 'إ', 0xFEF9 }, { 'ا', 0xFEFB },
		};

		const char Lam = 'ل';
		const char Tatweel = 'ـ';

		static readonly object SyncObject = new();
		static readonly Dictionary<string, string> Cache = new();

		public static string Shape(string text)
		{
			if (string.IsNullOrEmpty(text) || !HasArabic(text))
				return text;

			lock (SyncObject)
			{
				if (Cache.TryGetValue(text, out var shaped))
					return shaped;

				if (Cache.Count > 4096)
					Cache.Clear();

				var lines = text.Split('\n');
				for (var i = 0; i < lines.Length; i++)
					if (HasArabic(lines[i]))
						lines[i] = Reorder(Join(lines[i]));

				shaped = string.Join('\n', lines);
				Cache[text] = shaped;
				return shaped;
			}
		}

		static bool HasArabic(string text)
		{
			foreach (var c in text)
				if (c >= '؀' && c <= 'ۿ')
					return true;

			return false;
		}

		static bool IsMark(char c) => (c >= 'ً' && c <= 'ٟ') || c == 'ٰ';
		static bool JoinsNext(char c) => c == Tatweel || (Letters.TryGetValue(c, out var l) && l.Dual);
		static bool Joins(char c) => c == Tatweel || Letters.ContainsKey(c);

		/// <summary>Replaces letters with the contextual forms they take inside a word (logical order kept).</summary>
		static string Join(string line)
		{
			// Vowel marks are dropped: the renderer has no mark positioning
			var chars = new List<char>(line.Length);
			foreach (var c in line)
				if (!IsMark(c))
					chars.Add(c);

			var sb = new StringBuilder(chars.Count);
			for (var i = 0; i < chars.Count; i++)
			{
				var c = chars[i];
				var joinPrev = i > 0 && JoinsNext(chars[i - 1]);

				if (c == Lam && i + 1 < chars.Count && LamAlef.TryGetValue(chars[i + 1], out var ligature))
				{
					sb.Append((char)(ligature + (joinPrev ? 1 : 0)));
					i++;
					continue;
				}

				if (!Letters.TryGetValue(c, out var letter))
				{
					sb.Append(c);
					continue;
				}

				var joinNext = letter.Dual && i + 1 < chars.Count && Joins(chars[i + 1]);
				if (joinPrev && joinNext)
					sb.Append((char)(letter.Form + 3));
				else if (joinNext)
					sb.Append((char)(letter.Form + 2));
				else if (joinPrev)
					sb.Append((char)(letter.Form + 1));
				else
					sb.Append(c); // Fonts often map only the base letter for the isolated form
			}

			return sb.ToString();
		}

		static bool IsRtl(char c) => (c >= '؀' && c <= 'ۿ' && !(c >= '٠' && c <= '٩')) || (c >= 'ﭐ' && c <= '﻿');
		static bool IsLtr(char c) => !IsRtl(c) && char.IsLetterOrDigit(c);

		static char Mirror(char c)
		{
			switch (c)
			{
				case '(': return ')';
				case ')': return '(';
				case '[': return ']';
				case ']': return '[';
				case '{': return '}';
				case '}': return '{';
				case '<': return '>';
				case '>': return '<';
				case '«': return '»';
				case '»': return '«';
				default: return c;
			}
		}

		/// <summary>Lays a right-to-left line out left-to-right: runs of Latin/numbers stay in reading order.</summary>
		static string Reorder(string line)
		{
			// Split into left-to-right runs (strong LTR characters and the neutrals between them) and the rest
			var runs = new List<(int Start, int End, bool Ltr)>();
			var i = 0;
			while (i < line.Length)
			{
				if (!IsLtr(line[i]))
				{
					var start = i;
					while (i < line.Length && !IsLtr(line[i]))
						i++;
					runs.Add((start, i, false));
					continue;
				}

				var runStart = i;
				var lastStrong = i;
				while (i < line.Length && !IsRtl(line[i]))
				{
					if (IsLtr(line[i]))
						lastStrong = i;
					i++;
				}

				// Leading signs and trailing percent belong to the number they touch
				var s = runStart;
				while (s > 0 && "$+-#".IndexOf(line[s - 1]) >= 0)
					s--;
				var e = lastStrong + 1;
				while (e < line.Length && line[e] == '%')
					e++;

				if (s < runStart && runs.Count > 0)
				{
					var prev = runs[^1];
					runs[^1] = (prev.Start, s, prev.Ltr);
					if (prev.Start == s)
						runs.RemoveAt(runs.Count - 1);
				}

				runs.Add((s, e, true));
				i = e;
			}

			var sb = new StringBuilder(line.Length);
			for (var r = runs.Count - 1; r >= 0; r--)
			{
				var run = runs[r];
				if (run.Ltr)
					sb.Append(line, run.Start, run.End - run.Start);
				else
					for (var k = run.End - 1; k >= run.Start; k--)
						sb.Append(Mirror(line[k]));
			}

			return sb.ToString();
		}
	}
}
