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
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.Player)]
	[Desc("Bot module: fills the bot's aircraft carriers (PxCarrierDeck) with its jets that can use their deck (PxCarrierJet),",
		"like a player right-clicking the carrier with them. The jets then fly from the carrier and come back to it,",
		"and the airfield slots they leave free let the bot build more planes.")]
	public class PxCarrierBotModuleInfo : ConditionalTraitInfo
	{
		[Desc("Ticks between two looks for free deck room.")]
		public readonly int ScanInterval = 200;

		[Desc("Most jets sent to one carrier per look (a deck lands them one at a time).")]
		public readonly int JetsPerScan = 2;

		public override object Create(ActorInitializer init) { return new PxCarrierBotModule(init.Self, this); }
	}

	public class PxCarrierBotModule : ConditionalTrait<PxCarrierBotModuleInfo>, IBotTick
	{
		readonly World world;
		readonly Player player;
		int ticks;

		public PxCarrierBotModule(Actor self, PxCarrierBotModuleInfo info)
			: base(info)
		{
			world = self.World;
			player = self.Owner;
		}

		protected override void TraitEnabled(Actor self)
		{
			ticks = world.LocalRandom.Next(Info.ScanInterval);
		}

		void IBotTick.BotTick(IBot bot)
		{
			if (--ticks > 0)
				return;

			ticks = Info.ScanInterval;

			var carriers = world.ActorsWithTrait<PxCarrierDeck>()
				.Where(c => c.Actor.Owner == player && !c.Actor.IsDead && c.Actor.IsInWorld)
				.ToList();

			if (carriers.Count == 0)
				return;

			// Jets still based on land; idle ones first so the bot doesn't pull jets out of a fight
			var jets = world.ActorsWithTrait<PxCarrierJet>()
				.Where(j => j.Actor.Owner == player && !j.Actor.IsDead && j.Actor.IsInWorld && j.Trait.Home == null)
				.OrderByDescending(j => j.Actor.IsIdle)
				.Select(j => j.Actor)
				.ToList();

			foreach (var c in carriers)
			{
				var sent = 0;
				foreach (var jet in jets.ToList())
				{
					if (sent >= Info.JetsPerScan)
						break;

					if (!c.Trait.Accepts(jet) || !c.Trait.HasRoomFor(jet))
						continue;

					AIUtils.BotDebug($"{player.ResolvedPlayerName} rebases {jet.Info.Name} on {c.Actor.Info.Name}.");
					bot.QueueOrder(new Order(PxCarrierJet.OrderId, jet, Target.FromActor(c.Actor), false));
					jets.Remove(jet);
					sent++;
				}
			}
		}
	}
}
