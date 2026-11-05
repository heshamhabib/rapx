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
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.Player)]
	[Desc("One sidebar category chip (IDEA-05): groups the listed actors of a production queue under an icon.",
		"Add one instance per category (PxBuildCategory@army...). Actors not in any category of their queue",
		"appear under an automatic \"Other\" chip. Read by PxCategoryBarWidget.")]
	public class PxBuildCategoryInfo : TraitInfo<PxBuildCategory>
	{
		[FieldLoader.Require]
		[Desc("Production queue type the category belongs to (e.g. Building, Defense).")]
		public readonly string Queue = null;

		[FluentReference]
		[FieldLoader.Require]
		[Desc("Category name shown when hovering the chip and in the queue title.")]
		public readonly string Name = null;

		[Desc("Image name in the `px-category-icons` chrome collection (`<Icon>` and `<Icon>-off`).")]
		public readonly string Icon = null;

		[Desc("Chip order, lowest first.")]
		public readonly int Order = 0;

		[Desc("Actor types in this category (lower case).")]
		public readonly HashSet<string> Actors = new();
	}

	public class PxBuildCategory { }
}
