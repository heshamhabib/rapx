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
using OpenRA.Mods.Common.Widgets;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Sidebar cash label: shows the amount set by IngameCashCounterLogic with thousands separators, and
	/// switches to a short form (123.4M, 1.25B, 1T) once it would no longer fit.
	/// </summary>
	public class PxCashLabelWidget : LabelWithTooltipWidget
	{
		[Desc("Amounts at or above this are shown in the short form.")]
		public readonly long CompactFrom = 100_000_000;

		[ObjectCreator.UseCtor]
		public PxCashLabelWidget(ModData modData)
			: base(modData) { }

		protected PxCashLabelWidget(PxCashLabelWidget other)
			: base(other)
		{
			CompactFrom = other.CompactFrom;
		}

		public override Widget Clone() { return new PxCashLabelWidget(this); }

		public override void Draw()
		{
			var getText = GetText;
			GetText = () => Format(getText(), CompactFrom);
			base.Draw();
			GetText = getText;
		}

		public static string Format(string text, long compactFrom)
		{
			if (!long.TryParse(text, NumberStyles.Integer, CultureInfo.CurrentCulture, out var amount))
				return text;

			if (Math.Abs(amount) < compactFrom)
				return amount.ToString("N0", CultureInfo.CurrentCulture);

			var scales = new (long Value, string Suffix)[] { (1_000_000_000_000_000, "Q"), (1_000_000_000_000, "T"), (1_000_000_000, "B"), (1_000_000, "M") };
			foreach (var (value, suffix) in scales)
				if (Math.Abs(amount) >= value)
				{
					// Truncate rather than round, so the counter never shows more money than the player has
					var digits = amount / value >= 100 ? 10m : 100m;
					var scaled = Math.Truncate(amount / (decimal)value * digits) / digits;
					return scaled.ToString("0.##", CultureInfo.CurrentCulture) + suffix;
				}

			return amount.ToString("N0", CultureInfo.CurrentCulture);
		}
	}
}
