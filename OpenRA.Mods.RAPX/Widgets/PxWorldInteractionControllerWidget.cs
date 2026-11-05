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

using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Orders;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// The stock world interaction controller plus RA2's "double-click a factory to make it primary" (IDEA-11).
	/// Double-clicking anything else still selects every unit of that type on screen.
	/// </summary>
	public class PxWorldInteractionControllerWidget : WorldInteractionControllerWidget
	{
		readonly WorldRenderer worldRenderer;

		[ObjectCreator.UseCtor]
		public PxWorldInteractionControllerWidget(World world, WorldRenderer worldRenderer)
			: base(world, worldRenderer)
		{
			this.worldRenderer = worldRenderer;
		}

		public override bool HandleMouseInput(MouseInput mi)
		{
			var factory = mi.Button == MouseButton.Left && mi.Event == MouseInputEvent.Up && mi.MultiTapCount >= 2 &&
				World.OrderGenerator is UnitOrderGenerator ? FactoryAt(mi.Location) : null;

			var handled = base.HandleMouseInput(mi);
			if (factory == null)
				return handled;

			// Keep just the factory selected instead of every building of its type
			World.Selection.Combine(World, new[] { factory }, false, true);
			if (!factory.Trait<PrimaryBuilding>().IsPrimary)
				World.IssueOrder(new Order("PrimaryProducer", factory, false));

			return handled;
		}

		Actor FactoryAt(int2 screenPos)
		{
			var worldPx = worldRenderer.Viewport.ViewToWorldPx(screenPos);
			return World.ScreenMap.ActorsAtMouse(worldPx)
				.Select(p => p.Actor)
				.FirstOrDefault(a => !a.IsDead && a.Owner == World.LocalPlayer &&
					a.TraitOrDefault<PrimaryBuilding>() is { IsTraitDisabled: false });
		}
	}
}
