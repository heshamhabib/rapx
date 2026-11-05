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
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>Horizontal segmented meter of the local player's power drain against capacity.</summary>
	public class PxPowerBarWidget : Widget
	{
		public readonly int Segments = 20;
		public readonly int Gap = 2;
		public readonly Color NormalColor = Color.FromArgb(79, 197, 102);
		public readonly Color WarningColor = Color.FromArgb(255, 176, 32);
		public readonly Color CriticalColor = Color.FromArgb(255, 70, 60);
		public readonly Color EmptyColor = Color.FromArgb(36, 53, 42);

		[Desc("Fraction of capacity in use above which the meter turns to the warning color.")]
		public readonly float WarningThreshold = 0.9f;

		readonly PowerManager powerManager;

		[ObjectCreator.UseCtor]
		public PxPowerBarWidget(World world)
		{
			powerManager = world.LocalPlayer?.PlayerActor.TraitOrDefault<PowerManager>();
		}

		public override void Draw()
		{
			if (powerManager == null)
				return;

			var rb = RenderBounds;
			var provided = powerManager.PowerProvided;
			var drained = powerManager.PowerDrained;
			var usage = provided > 0 ? (float)drained / provided : drained > 0 ? 1 : 0;
			var lit = (int)Math.Ceiling(Math.Min(1, usage) * Segments);
			var color = powerManager.ExcessPower < 0 ? CriticalColor : usage > WarningThreshold ? WarningColor : NormalColor;
			if (powerManager.ExcessPower < 0)
				lit = Segments;

			var w = (rb.Width - (Segments - 1) * Gap) / (float)Segments;
			for (var i = 0; i < Segments; i++)
			{
				var x = (int)(rb.X + i * (w + Gap));
				var r = new Rectangle(x, rb.Y, (int)(rb.X + (i + 1) * (w + Gap) - Gap) - x, rb.Height);
				if (i < lit)
				{
					WidgetUtils.FillRectWithColor(r.InflateBy(1, 1, 1, 1), Color.FromArgb(70, color));
					WidgetUtils.FillRectWithColor(r, color);
				}
				else
					WidgetUtils.FillRectWithColor(r, EmptyColor);
			}
		}
	}
}
