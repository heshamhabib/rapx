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
using System.Linq;
using OpenRA.Mods.RAPX.Traits;

namespace OpenRA.Mods.RAPX.UtilityCommands
{
	/// <summary>
	/// Developer check of PxSpriteLoadPolicy: lists the images a match between the given nations leaves unloaded until
	/// first used, and how many images only some nations can field.
	/// </summary>
	public class SpriteScopeCommand : IUtilityCommand
	{
		string IUtilityCommand.Name => "--sprite-scope";

		bool IUtilityCommand.ValidateArguments(string[] args) => args.Length == 2;

		[Desc("NATION[,NATION...]", "List the images a match between these nations loads only on first use.")]
		void IUtilityCommand.Run(Utility utility, string[] args)
		{
			// HACK: The engine code assumes that Game.ModData is set.
			var modData = Game.ModData = utility.ModData;
			var rules = modData.DefaultRules;
			var present = args[1].Split(',', StringSplitOptions.RemoveEmptyEntries).ToHashSet();
			var scope = PxSpriteScope.For(rules, "fact");
			var deferred = scope.Restricted.Where(kv => !kv.Value.Overlaps(present)).Select(kv => kv.Key).OrderBy(k => k).ToList();

			Console.WriteLine($"{scope.Restricted.Count} images belong to some nations only; " +
				$"{deferred.Count} of them are left out of a match between {string.Join(", ", present)}:");
			foreach (var image in deferred)
				Console.WriteLine($"  {image} ({string.Join(" ", scope.Restricted[image].OrderBy(n => n))})");
		}
	}
}
