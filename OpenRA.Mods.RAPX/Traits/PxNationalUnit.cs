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
	[Desc("Marks a national unit (IDEA-12 jets). Its Buildable prerequisites already limit who can build it;",
		"this also hides it from the sidebar of other nations when the AllTech cheat ignores prerequisites.",
		"Read by PxCategoryBarWidget.")]
	public class PxNationalUnitInfo : TraitInfo<PxNationalUnit>
	{
		[FieldLoader.Require]
		[Desc("Factions whose sidebar shows this unit.")]
		public readonly HashSet<string> Factions = new();

		public static bool ShownTo(ActorInfo actor, Player player)
		{
			var info = actor.TraitInfoOrDefault<PxNationalUnitInfo>();
			return info == null || player == null || info.Factions.Contains(player.Faction.InternalName);
		}
	}

	public class PxNationalUnit { }
}
