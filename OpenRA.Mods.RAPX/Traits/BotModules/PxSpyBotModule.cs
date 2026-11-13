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
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.Player)]
	[Desc("Bot module: sends the bot's idle spies to infiltrate enemy buildings, the most useful ones first",
		"(refineries steal cash, tech centres and superweapons reset their powers, power plants black out the base).")]
	public class PxSpyBotModuleInfo : ConditionalTraitInfo
	{
		[Desc("Actor types of the spies.")]
		public readonly HashSet<string> SpyTypes = new();

		[Desc("Buildings to infiltrate, best first. Others that spies can enter come after these.")]
		public readonly string[] PreferredTargets =
		{
			"mslo", "iron", "bmbf", "sbmb", "atek", "stek", "proc", "dome", "apwr", "powr", "weap", "barr", "tent"
		};

		[Desc("Target type spies infiltrate (Infiltrates.Types).")]
		public readonly BitSet<TargetableType> InfiltrateTargetType = new("SpyInfiltrate");

		[Desc("Ticks between two looks for idle spies.")]
		public readonly int ScanInterval = 100;

		public override object Create(ActorInitializer init) { return new PxSpyBotModule(init.Self, this); }
	}

	public class PxSpyBotModule : ConditionalTrait<PxSpyBotModuleInfo>, IBotTick
	{
		readonly World world;
		readonly Player player;
		int ticks;

		public PxSpyBotModule(Actor self, PxSpyBotModuleInfo info)
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

			var spies = world.Actors
				.Where(a => a.Owner == player && !a.IsDead && a.IsInWorld && a.IsIdle && Info.SpyTypes.Contains(a.Info.Name))
				.ToList();

			if (spies.Count == 0)
				return;

			var targets = world.ActorsHavingTrait<Building>()
				.Where(a => !a.IsDead && a.IsInWorld && player.RelationshipWith(a.Owner) == PlayerRelationship.Enemy
					&& a.CanBeViewedByPlayer(player) && a.GetEnabledTargetTypes().Overlaps(Info.InfiltrateTargetType))
				.ToList();

			if (targets.Count == 0)
				return;

			foreach (var spy in spies)
			{
				// Best kind of building first, the closest of that kind
				var target = targets
					.OrderBy(t => Rank(t.Info.Name))
					.ThenBy(t => (t.CenterPosition - spy.CenterPosition).HorizontalLengthSquared)
					.First();

				AIUtils.BotDebug($"{player.ResolvedPlayerName} sends {spy.Info.Name} to infiltrate {target.Info.Name}.");
				bot.QueueOrder(new Order("Infiltrate", spy, Target.FromActor(target), false));
			}
		}

		int Rank(string name)
		{
			var i = Array.IndexOf(Info.PreferredTargets, name);
			return i < 0 ? Info.PreferredTargets.Length : i;
		}
	}
}
