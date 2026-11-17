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
using OpenRA.Mods.Common.Graphics;
using OpenRA.Mods.Common.Orders;
using OpenRA.Mods.Common.Pathfinder;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Orders
{
	/// <summary>
	/// Fast-rope mode (IDEA-47, G): the next left click picks the landing zone for every selected transport
	/// helicopter with soldiers aboard. Several helicopters keep their spacing around the clicked spot, so a flight
	/// does not stack its ropes on one cell. Shift+click queues the order and stays in the mode; right click leaves it.
	/// </summary>
	public class PxFastRopeOrderGenerator : OrderGenerator
	{
		// Helicopters of a flight keep at most this far from the clicked spot (cells)
		const int MaxSpread = 3;

		static readonly Color ZoneColor = Color.FromArgb(200, 226, 214, 120);

		public static bool CanRope(Actor a)
		{
			return a.IsInWorld && !a.IsDead && a.Owner == a.World.LocalPlayer && a.TraitOrDefault<PxAirAssault>() is { CanRope: true };
		}

		static bool Walkable(World world, CPos cell)
		{
			if (!world.Map.Contains(cell))
				return false;

			var foot = world.WorldActor.TraitsImplementing<Locomotor>().FirstOrDefault(l => l.Info.Name == "foot");
			return foot == null || foot.MovementCostForCell(cell) != PathGraph.MovementCostForUnreachableCell;
		}

		protected override IEnumerable<Order> OrderInner(World world, CPos cell, int2 worldPixel, MouseInput mi)
		{
			if (mi.Button == MouseButton.Right)
			{
				world.CancelInputMode();
				yield break;
			}

			if (mi.Button != MouseButton.Left || !Walkable(world, cell))
				yield break;

			var helis = world.Selection.Actors.Where(CanRope).ToList();
			if (helis.Count == 0)
				yield break;

			var queued = mi.Modifiers.HasModifier(Modifiers.Shift);
			if (!queued)
				world.CancelInputMode();

			// Formation: each helicopter keeps its offset from the flight's centre, squeezed to MaxSpread cells
			var centre = new CPos((int)Math.Round(helis.Average(h => h.Location.X)), (int)Math.Round(helis.Average(h => h.Location.Y)));
			foreach (var h in helis)
			{
				var d = h.Location - centre;
				var len = Math.Max(1, Math.Max(Math.Abs(d.X), Math.Abs(d.Y)));
				var k = Math.Min(len, MaxSpread);
				var target = helis.Count == 1 ? cell : world.Map.Clamp(cell + new CVec(d.X * k / len, d.Y * k / len));
				if (!Walkable(world, target))
					target = cell;

				yield return new Order("PxFastRope", h, Target.FromCell(world, target), queued);
			}
		}

		protected override void Tick(World world)
		{
			if (!world.Selection.Actors.Any(CanRope))
				world.CancelInputMode();
		}

		protected override IEnumerable<IRenderable> Render(WorldRenderer wr, World world) { yield break; }
		protected override IEnumerable<IRenderable> RenderAboveShroud(WorldRenderer wr, World world) { yield break; }

		protected override IEnumerable<IRenderable> RenderAnnotations(WorldRenderer wr, World world)
		{
			// The landing zone under the cursor: a ring the size of the smoke screen around it
			var cell = wr.Viewport.ViewToWorld(Viewport.LastMousePos);
			if (!Walkable(world, cell))
				yield break;

			var pos = world.Map.CenterOfCell(cell);
			yield return new CircleAnnotationRenderable(pos, new WDist(2560), 1, ZoneColor);
			yield return new CircleAnnotationRenderable(pos, new WDist(512), 2, ZoneColor);
		}

		protected override string GetCursor(World world, CPos cell, int2 worldPixel, MouseInput mi)
		{
			return Walkable(world, cell) ? "ability" : "generic-blocked";
		}
	}
}
