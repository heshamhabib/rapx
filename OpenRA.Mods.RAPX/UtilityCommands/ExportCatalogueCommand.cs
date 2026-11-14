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

using System.IO;
using System.Linq;
using System.Text.Json;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.RAPX.Widgets;

namespace OpenRA.Mods.RAPX.UtilityCommands
{
	/// <summary>
	/// Writes the Extras catalogue (nations, units, stats, weapons, features) as JSON for the website (tools/make_site.py),
	/// using the same PxCatalogueData the in-game catalogue reads, so both always agree.
	/// </summary>
	public class ExportCatalogueCommand : IUtilityCommand
	{
		string IUtilityCommand.Name => "--export-catalogue";

		bool IUtilityCommand.ValidateArguments(string[] args) => args.Length == 2;

		[Desc("OUTPUT.json", "Export the Extras catalogue as JSON for the website.")]
		void IUtilityCommand.Run(Utility utility, string[] args)
		{
			// HACK: The engine code assumes that Game.ModData is set.
			var modData = Game.ModData = utility.ModData;
			var data = new PxCatalogueData(modData.DefaultRules, "fact");

			var export = new
			{
				classes = PxCatalogueData.Classes.Select(c => c.Label),
				nations = data.Nations.Select(n => new
				{
					id = n.Id,
					name = n.Name,
					side = n.Side,
					motto = n.Motto,
					specials = n.Specials,
					lore = n.Lore,
				}),
				entries = data.Entries.Select(e =>
				{
					var rs = e.Actor.TraitInfoOrDefault<RenderSpritesInfo>();
					return new
					{
						id = e.Actor.Name,
						name = e.Name,
						category = e.Category,
						role = e.Role,
						lore = e.Lore,
						notes = e.Notes,
						cost = e.Cost,
						buildSeconds = e.BuildTicks / (float)PxCatalogueData.Ticks,
						power = e.Power,
						hp = e.HP,
						armor = e.Armor,
						speed = e.Speed,
						sight = e.Sight,
						range = e.Range,
						dps = e.Dps,
						weapons = e.Weapons.Select(w => new
						{
							name = w.Name,
							kind = w.Kind,
							damage = w.Damage,
							burst = w.Burst,
							range = w.Range,
							reload = w.Reload,
							dps = w.Dps,
							air = w.Air,
							ground = w.Ground,
							naval = w.Naval,
							support = w.Support,
						}),
						features = e.Features,
						grades = e.Effect.Select(PxCatalogueData.GradeLetter),
						nations = e.Nations.OrderBy(n => n),
						requires = data.Nations.Where(n => e.Nations.Contains(n.Id)).Take(1)
							.SelectMany(n => data.Requires(e, n)),

						// Picture candidates per nation, in the order PxCatalogueWidget tries them
						images = data.Nations.Where(n => e.Nations.Contains(n.Id)).ToDictionary(n => n.Id, n =>
							new[] { rs?.GetImage(e.Actor, n.Id), rs?.Image, e.Actor.Name }
								.Where(s => s != null).Select(s => s.ToLowerInvariant()).Distinct()),
					};
				}),
			};

			File.WriteAllText(args[1], JsonSerializer.Serialize(export, new JsonSerializerOptions { WriteIndented = true }));
			System.Console.WriteLine($"Wrote {data.Nations.Count} nations and {data.Entries.Count} entries to {args[1]}");
		}
	}
}
