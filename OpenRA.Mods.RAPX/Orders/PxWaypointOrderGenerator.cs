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
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Graphics;
using OpenRA.Mods.Common.Orders;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Orders
{
	/// <summary>
	/// RA2-style waypoint mode (IDEA-11). Each left click adds a numbered waypoint; right click removes the last one
	/// (or leaves the mode when there are none). Double-clicking or pressing the waypoint key again sends the route
	/// to the selected units as one move followed by queued moves.
	/// </summary>
	public class PxWaypointOrderGenerator : OrderGenerator
	{
		static readonly Color RouteColor = Color.FromArgb(255, 120, 230, 90);
		static readonly Color PreviewColor = Color.FromArgb(150, 120, 230, 90);

		readonly List<(WPos Pos, Order[] Orders)> waypoints = new();

		public int Count => waypoints.Count;

		public static bool CanMove(Actor a)
		{
			return a.IsInWorld && !a.IsDead && a.Owner == a.World.LocalPlayer && a.Info.HasTraitInfo<IMoveInfo>();
		}

		protected override IEnumerable<Order> OrderInner(World world, CPos cell, int2 worldPixel, MouseInput mi)
		{
			if (mi.Button == MouseButton.Right)
			{
				if (waypoints.Count > 0)
					waypoints.RemoveAt(waypoints.Count - 1);
				else
					world.CancelInputMode();

				return Enumerable.Empty<Order>();
			}

			if (mi.Button != MouseButton.Left || !world.Map.Contains(cell))
				return Enumerable.Empty<Order>();

			if (mi.MultiTapCount >= 2 && waypoints.Count > 0)
				return SendRoute(world);

			// Build the orders now, while the mouse is over the clicked spot: force-move (Alt), queued (Shift) after the first point
			var moveInput = new MouseInput
			{
				Location = mi.Location,
				Button = Game.Settings.Game.MouseButtonPreference.Action,
				Event = MouseInputEvent.Down,
				Modifiers = Modifiers.Alt | (waypoints.Count > 0 ? Modifiers.Shift : Modifiers.None)
			};

			var orders = new UnitOrderGenerator().Order(world, cell, worldPixel, moveInput)
				.Where(o => o != null && (waypoints.Count == 0 || o.OrderString != "CreateGroup"))
				.ToArray();

			if (orders.Any(o => o.OrderString != "CreateGroup"))
				waypoints.Add((world.Map.CenterOfCell(cell), orders));

			return Enumerable.Empty<Order>();
		}

		/// <summary>Leaves waypoint mode and returns the route's orders, ready to be issued.</summary>
		public Order[] SendRoute(World world)
		{
			world.CancelInputMode();
			return waypoints
				.SelectMany(w => w.Orders)
				.Where(o => o.Subject == null || (!o.Subject.IsDead && o.Subject.IsInWorld))
				.ToArray();
		}

		protected override void Tick(World world)
		{
			if (!world.Selection.Actors.Any(CanMove))
			{
				Log.Write("debug", "PxWaypointOrderGenerator: nothing selected can move, leaving waypoint mode");
				world.CancelInputMode();
			}
		}

		protected override IEnumerable<IRenderable> Render(WorldRenderer wr, World world) { yield break; }
		protected override IEnumerable<IRenderable> RenderAboveShroud(WorldRenderer wr, World world) { yield break; }

		protected override IEnumerable<IRenderable> RenderAnnotations(WorldRenderer wr, World world)
		{
			var movers = world.Selection.Actors.Where(CanMove).ToList();
			if (movers.Count == 0)
				yield break;

			// The route starts at the middle of the selected group
			var start = WPos.Zero + movers.Select(a => a.CenterPosition - WPos.Zero).Aggregate((a, b) => a + b) / movers.Count;
			var font = Game.Renderer.Fonts["Bold"];
			var last = start;
			for (var i = 0; i < waypoints.Count; i++)
			{
				var pos = waypoints[i].Pos;
				yield return new LineAnnotationRenderable(last, pos, 2, RouteColor);
				yield return new CircleAnnotationRenderable(pos, new WDist(300), 2, RouteColor);
				yield return new CircleAnnotationRenderable(pos, new WDist(90), 1, RouteColor, true);
				yield return new TextAnnotationRenderable(font, pos + new WVec(0, -560, 0), 0, RouteColor,
					(i + 1).ToString(CultureInfo.CurrentCulture));
				last = pos;
			}

			// Preview of the next leg under the cursor
			var cursorCell = wr.Viewport.ViewToWorld(Viewport.LastMousePos);
			if (world.Map.Contains(cursorCell))
				yield return new LineAnnotationRenderable(last, world.Map.CenterOfCell(cursorCell), 1, PreviewColor);
		}

		protected override string GetCursor(World world, CPos cell, int2 worldPixel, MouseInput mi)
		{
			return world.Map.Contains(cell) ? "move" : "move-blocked";
		}
	}
}
