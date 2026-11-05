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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Orders;
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Orders
{
	/// <summary>Sets the rally point of every selected friendly production structure to the clicked cell.</summary>
	public class PxRallyPointOrderGenerator : OrderGenerator
	{
		readonly Actor[] structures;

		public PxRallyPointOrderGenerator(IEnumerable<Actor> structures)
		{
			this.structures = structures.ToArray();
		}

		protected override IEnumerable<Order> OrderInner(World world, CPos cell, int2 worldPixel, MouseInput mi)
		{
			if (mi.Button == MouseButton.Right)
			{
				world.CancelInputMode();
				yield break;
			}

			if (mi.Button != MouseButton.Left || !world.Map.Contains(cell))
				yield break;

			world.CancelInputMode();
			var queued = mi.Modifiers.HasModifier(Modifiers.Shift);
			foreach (var a in structures.Where(a => a.IsInWorld && !a.IsDead && a.Owner == world.LocalPlayer))
				yield return new Order("SetRallyPoint", a, Target.FromCell(world, cell), queued) { SuppressVisualFeedback = true };
		}

		protected override void Tick(World world)
		{
			if (structures.All(a => !a.IsInWorld || a.IsDead))
				world.CancelInputMode();
		}

		protected override IEnumerable<IRenderable> Render(WorldRenderer wr, World world) { yield break; }
		protected override IEnumerable<IRenderable> RenderAboveShroud(WorldRenderer wr, World world) { yield break; }
		protected override IEnumerable<IRenderable> RenderAnnotations(WorldRenderer wr, World world) { yield break; }

		protected override string GetCursor(World world, CPos cell, int2 worldPixel, MouseInput mi)
		{
			return world.Map.Contains(cell) ? structures.FirstOrDefault()?.Info.TraitInfoOrDefault<RallyPointInfo>()?.Cursor ?? "ability" : "generic-blocked";
		}
	}
}
