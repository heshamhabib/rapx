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
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>The production tooltip's description, made easy to scan: the plain lines as body text, and the
	/// "Strong vs ..." / "Weak vs ..." lines as green and red tag rows with a chevron and an icon per target class.
	/// Laid out by PxProductionTooltipWeaponsLogic in place of the stock DESC label.</summary>
	public class PxTooltipDescWidget : Widget
	{
		const int TagHeight = 18;
		const int TagGap = 3;
		const int Icon = 13;

		static readonly Color StrongColor = Color.FromArgb(120, 214, 96);
		static readonly Color WeakColor = Color.FromArgb(255, 92, 72);
		static readonly string[] Separators = { ", and ", " and ", ", ", " & " };

		sealed class Line
		{
			public string Text;
			public bool? Strong;
			public List<(string Icon, string Text)> Terms;
		}

		readonly List<Line> lines = new();
		string shown;

		public string BodyFont = "Small";
		public string LabelFont = "PXSidebarSmall";
		public string TermFont = "TinyBold";
		public Color BodyColor = Color.FromArgb(236, 230, 214);

		public int ContentWidth { get; private set; }

		/// <summary>Chevron, the wider of the two labels and a gap: where the first target starts.</summary>
		int LabelWidth() => 21 + Math.Max(Game.Renderer.Fonts[LabelFont].Measure("STRONG").X, Game.Renderer.Fonts[LabelFont].Measure("WEAK").X) + 10;
		public int ContentHeight { get; private set; }

		public void SetText(string text)
		{
			if (text == shown)
				return;

			shown = text;
			lines.Clear();
			var body = Game.Renderer.Fonts[BodyFont];
			var term = Game.Renderer.Fonts[TermFont];
			foreach (var raw in (text ?? "").Split('\n'))
			{
				var s = raw.Trim();
				if (s.Length == 0)
					continue;

				bool? strong = s.StartsWith("Strong vs ", StringComparison.Ordinal) ? true
					: s.StartsWith("Weak vs ", StringComparison.Ordinal) ? false : null;
				if (strong == null)
				{
					lines.Add(new Line { Text = s });
					continue;
				}

				var rest = s[(strong.Value ? 10 : 8)..].TrimEnd('.');
				var terms = rest.Split(Separators, StringSplitOptions.RemoveEmptyEntries)
					.Select(t => t.Trim()).Where(t => t.Length > 0)
					.Select(t => (PxTooltipIcons.ForTerm(t), char.ToUpperInvariant(t[0]) + t[1..])).ToList();
				lines.Add(new Line { Strong = strong, Terms = terms });
			}

			ContentWidth = 0;
			ContentHeight = 0;
			var lastWasTag = false;
			foreach (var l in lines)
			{
				if (l.Strong == null)
				{
					var size = body.Measure(l.Text);
					ContentWidth = Math.Max(ContentWidth, size.X);
					ContentHeight += size.Y + 2;
					lastWasTag = false;
					continue;
				}

				if (!lastWasTag)
					ContentHeight += 4;

				var w = LabelWidth() + l.Terms.Sum(t => (t.Icon != null ? Icon + 3 : 0) + term.Measure(t.Text).X + 12);
				ContentWidth = Math.Max(ContentWidth, w + 6);
				ContentHeight += TagHeight + TagGap;
				lastWasTag = true;
			}
		}

		public override void Draw()
		{
			if (lines.Count == 0)
				return;

			var rb = RenderBounds;
			var cr = Game.Renderer.RgbaColorRenderer;
			var body = Game.Renderer.Fonts[BodyFont];
			var label = Game.Renderer.Fonts[LabelFont];
			var term = Game.Renderer.Fonts[TermFont];
			var y = rb.Y;
			var lastWasTag = false;
			foreach (var l in lines)
			{
				if (l.Strong == null)
				{
					body.DrawTextWithShadow(l.Text, new float2(rb.X, y), BodyColor, Color.Black, 1);
					y += body.Measure(l.Text).Y + 2;
					lastWasTag = false;
					continue;
				}

				if (!lastWasTag)
					y += 4;

				var strong = l.Strong.Value;
				var color = strong ? StrongColor : WeakColor;
				var row = new Rectangle(rb.X, y, rb.Width, TagHeight);

				// Tinted strip that fades out to the right, with a solid spine
				cr.FillRect(new float3(row.X, row.Y, 0), new float3(row.Right, row.Y, 0), new float3(row.Right, row.Bottom, 0), new float3(row.X, row.Bottom, 0),
					Color.FromArgb(70, color), Color.FromArgb(0, color), Color.FromArgb(0, color), Color.FromArgb(70, color));
				cr.FillRect(new float3(row.X, row.Y, 0), new float3(row.X + 2, row.Y, 0), new float3(row.X + 2, row.Bottom, 0), new float3(row.X, row.Bottom, 0), color);

				PxTooltipIcons.Draw(strong ? "strong" : "weak", new float2(row.X + 6, row.Y + 3), 12, color);
				var text = strong ? "STRONG" : "WEAK";
				label.DrawTextWithShadow(text, new float2(row.X + 21, row.Y + 3), color, Color.Black, 1);

				var x = row.X + LabelWidth();
				foreach (var (icon, name) in l.Terms)
				{
					if (icon != null)
					{
						PxTooltipIcons.Draw(icon, new float2(x, row.Y + 2), Icon, Color.White);
						x += Icon + 3;
					}

					term.DrawTextWithShadow(name, new float2(x, row.Y + 3), Color.White, Color.Black, 1);
					x += term.Measure(name).X + 12;
				}

				y += TagHeight + TagGap;
				lastWasTag = true;
			}
		}
	}
}
