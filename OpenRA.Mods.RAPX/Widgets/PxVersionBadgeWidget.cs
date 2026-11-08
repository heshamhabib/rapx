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
using System.IO;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Main menu version plate: the mod version from mod.yaml (e.g. 0.1.0-pilot) drawn as a large
	/// "v0.1.0" with a channel pill (PILOT), plus the engine version and, when run from a git checkout,
	/// the commit it was built from. A slow sheen sweeps across the plate and the pill lamp pulses.
	/// </summary>
	public class PxVersionBadgeWidget : Widget
	{
		public readonly string KickerFont = "PXHeader";
		public readonly string VersionFont = "PXDigits";
		public readonly string PillFont = "PXSidebarSmall";
		public readonly string InfoFont = "PXDigitsSmall";
		public readonly Color Accent = Color.FromArgb(255, 92, 70);
		public readonly Color TextColor = Color.FromArgb(242, 236, 234);
		public readonly Color LabelColor = Color.FromArgb(157, 158, 166);

		[Desc("Seconds between two sheen sweeps across the plate.")]
		public readonly float SheenInterval = 7f;

		[FluentReference]
		const string Kicker = "label-px-version-kicker";

		[FluentReference("engine")]
		const string EngineLine = "label-px-version-engine";

		[FluentReference("engine", "build")]
		const string BuildLine = "label-px-version-build";

		readonly string number;
		readonly string channel;
		readonly string info;

		SpriteFont kickerFont, versionFont, pillFont, infoFont;

		[ObjectCreator.UseCtor]
		public PxVersionBadgeWidget(ModData modData)
		{
			(number, channel) = SplitVersion(modData.Manifest.Metadata.Version);
			var build = GitCommit(modData.Manifest.Package?.Name);
			info = build != null
				? FluentProvider.GetMessage(BuildLine, "engine", Game.EngineVersion, "build", build)
				: FluentProvider.GetMessage(EngineLine, "engine", Game.EngineVersion);
		}

		/// <summary>"0.1.0-pilot" -> ("v0.1.0", "PILOT"); the unreplaced SDK placeholder reads as a dev build.</summary>
		static (string Number, string Channel) SplitVersion(string version)
		{
			if (string.IsNullOrEmpty(version) || version.StartsWith('{'))
				return ("DEV", "SOURCE");

			version = version.Split('+')[0];
			var dash = version.IndexOf('-');
			var core = dash < 0 ? version : version[..dash];
			var pre = dash < 0 ? "release" : version[(dash + 1)..];
			if (core.Length > 0 && char.IsDigit(core[0]))
				core = "v" + core;

			return (core, pre.Replace('.', ' ').ToUpperInvariant());
		}

		/// <summary>Short hash of the checked-out commit, read straight from .git next to the mods folder; null outside a checkout.</summary>
		static string GitCommit(string modPath)
		{
			try
			{
				if (string.IsNullOrEmpty(modPath))
					return null;

				var gitDir = Path.GetFullPath(Path.Combine(modPath, "..", "..", ".git"));
				var headPath = Path.Combine(gitDir, "HEAD");
				if (!File.Exists(headPath))
					return null;

				var head = File.ReadAllText(headPath).Trim();
				if (head.StartsWith("ref: ", StringComparison.Ordinal))
				{
					var name = head[5..];
					var refPath = Path.Combine(gitDir, name);
					if (File.Exists(refPath))
						head = File.ReadAllText(refPath).Trim();
					else
					{
						var packed = Path.Combine(gitDir, "packed-refs");
						head = File.Exists(packed)
							? File.ReadLines(packed).Where(l => l.EndsWith(" " + name, StringComparison.Ordinal))
								.Select(l => l.Split(' ')[0]).FirstOrDefault()
							: null;
					}
				}

				return head != null && head.Length >= 7 ? head[..7] : null;
			}
			catch (Exception)
			{
				return null;
			}
		}

		static Color Alpha(Color c, float a) => Color.FromArgb((int)(Math.Clamp(a, 0f, 1f) * 255), c.R, c.G, c.B);

		public override void Draw()
		{
			kickerFont ??= Game.Renderer.Fonts[KickerFont];
			versionFont ??= Game.Renderer.Fonts[VersionFont];
			pillFont ??= Game.Renderer.Fonts[PillFont];
			infoFont ??= Game.Renderer.Fonts[InfoFont];

			var t = Game.RunTime / 1000f;
			var kicker = FluentProvider.GetMessage(Kicker);
			var versionSize = versionFont.Measure(number);
			var pillText = pillFont.Measure(channel);
			var pillW = pillText.X + 22;
			var width = Math.Max(Math.Max(versionSize.X + pillW + 40, infoFont.Measure(info).X + 30), kickerFont.Measure(kicker).X + 30);
			var r = new Rectangle(RenderBounds.X, RenderBounds.Bottom - Bounds.Height, width, Bounds.Height);

			// Plate: dark glass, accent bar on the left, hairlines top and bottom fading out to the right.
			WidgetUtils.FillRectWithColor(r, Color.FromArgb(170, 8, 9, 12));
			WidgetUtils.FillRectWithColor(new Rectangle(r.X, r.Y, 3, r.Height), Accent);
			WidgetUtils.FillRectWithColor(new Rectangle(r.X + 3, r.Y, 6, r.Height), Alpha(Accent, 0.18f));
			for (var i = 0; i < 8; i++)
			{
				var seg = (r.Width - 3) / 8;
				var a = 0.55f * (1f - i / 8f);
				WidgetUtils.FillRectWithColor(new Rectangle(r.X + 3 + i * seg, r.Y, seg, 1), Alpha(Accent, a));
				WidgetUtils.FillRectWithColor(new Rectangle(r.X + 3 + i * seg, r.Bottom - 1, seg, 1), Color.FromArgb((int)(255 * a * 0.3f), 255, 255, 255));
			}

			// Sheen: a soft diagonal-looking band of 1px columns crossing the plate once per interval.
			var phase = t % SheenInterval / 1.4f;
			if (phase < 1f)
			{
				var cx = r.X - 40 + (int)((r.Width + 80) * phase);
				for (var dx = -20; dx <= 20; dx++)
				{
					var x = cx + dx;
					if (x <= r.X + 3 || x >= r.Right)
						continue;

					var a = 0.09f * (1f - Math.Abs(dx) / 20f);
					WidgetUtils.FillRectWithColor(new Rectangle(x, r.Y + 1, 1, r.Height - 2), Alpha(Color.White, a));
				}
			}

			var x0 = r.X + 16;
			kickerFont.DrawText(kicker, new float2(x0, r.Y + 9), Accent);

			var vy = r.Y + 25;
			versionFont.DrawTextWithShadow(number, new float2(x0, vy), TextColor, Color.FromArgb(180, 0, 0, 0), 1);

			// Channel pill with a pulsing status lamp.
			var pill = new Rectangle(x0 + versionSize.X + 12, vy + 6, pillW, 18);
			WidgetUtils.FillRectWithColor(pill, Alpha(Accent, 0.22f));
			WidgetUtils.FillRectWithColor(new Rectangle(pill.X, pill.Y, pill.Width, 1), Alpha(Accent, 0.9f));
			WidgetUtils.FillRectWithColor(new Rectangle(pill.X, pill.Bottom - 1, pill.Width, 1), Alpha(Accent, 0.9f));
			WidgetUtils.FillRectWithColor(new Rectangle(pill.X, pill.Y, 1, pill.Height), Alpha(Accent, 0.9f));
			WidgetUtils.FillRectWithColor(new Rectangle(pill.Right - 1, pill.Y, 1, pill.Height), Alpha(Accent, 0.9f));
			var pulse = 0.5f + 0.5f * MathF.Sin(t * 3.2f);
			WidgetUtils.FillRectWithColor(new Rectangle(pill.X + 5, pill.Y + 6, 6, 6), Alpha(Accent, 0.25f * pulse));
			WidgetUtils.FillRectWithColor(new Rectangle(pill.X + 6, pill.Y + 7, 4, 4), Alpha(Accent, 0.45f + 0.55f * pulse));
			pillFont.DrawText(channel, new float2(pill.X + 15, pill.Y + (pill.Height - pillText.Y) / 2), TextColor);

			infoFont.DrawText(info, new float2(x0, r.Bottom - 20), LabelColor);
		}
	}
}
