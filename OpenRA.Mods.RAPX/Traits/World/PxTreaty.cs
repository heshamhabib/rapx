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
using OpenRA.Mods.Common.Commands;
using OpenRA.Mods.Common.Traits;
using OpenRA.Network;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Peace treaty lobby option (IDEA-10): until the chosen time has passed, players cannot attack, damage, capture or",
		"infiltrate each other, or fire the listed support powers. Players can vote to end it early with /endtreaty.",
		"Needs PxTreatyProtection on actors and PxTreatyPlayer on the player actor.")]
	public class PxTreatyManagerInfo : TraitInfo, ILobbyOptions, IRulesetLoaded
	{
		[FluentReference]
		public readonly string Label = "dropdown-peace-treaty.label";

		[FluentReference]
		public readonly string Description = "dropdown-peace-treaty.description";

		[Desc("Treaty lengths offered in the lobby, in minutes. 0 = no treaty.")]
		public readonly int[] Options = { 0, 5, 10, 15, 20, 30, 45, 60, 90, 120 };

		public readonly int Default = 0;
		public readonly bool Locked = false;
		public readonly bool Visible = true;
		public readonly int DisplayOrder = 3;

		[Desc("Minutes left at which a warning is shown.")]
		public readonly int[] WarningMinutes = { 10, 5, 1 };

		[Desc("Seconds left at which the final countdown is shown.")]
		public readonly int CountdownSeconds = 10;

		[Desc("Order strings refused while the treaty is active when they target another player's actor.")]
		public readonly HashSet<string> BlockedTargetOrders = new() { "Attack", "ForceAttack", "CaptureActor", "Infiltrate", "C4", "DetonateAttack" };

		[Desc("Support power order names that cannot be used at all while the treaty is active.")]
		public readonly HashSet<string> BlockedSupportPowers = new() { "NukePowerInfoOrder", "UkraineParabombs" };

		[Desc("Seconds until the treaty ends once every human player has voted to end it early.")]
		public readonly int VoteEndDelay = 30;

		[Desc("Seconds the WAR badge stays on screen after the treaty ends.")]
		public readonly int WarBadgeSeconds = 6;

		[NotificationReference("Speech")]
		[Desc("Optional speech notification played when the treaty ends.")]
		public readonly string EndSpeechNotification = null;

		[FluentReference]
		const string NoTreaty = "options-peace-treaty.no-treaty";

		[FluentReference("minutes")]
		const string TreatyOption = "options-peace-treaty.options";

		void IRulesetLoaded<ActorInfo>.RulesetLoaded(Ruleset rules, ActorInfo info)
		{
			if (!Options.Contains(Default))
				throw new YamlException("PxTreatyManager Default must be one of its Options");
		}

		IEnumerable<LobbyOption> ILobbyOptions.LobbyOptions(MapPreview map)
		{
			var values = Options.ToDictionary(m => m.ToStringInvariant(), m => m == 0
				? FluentProvider.GetMessage(NoTreaty)
				: FluentProvider.GetMessage(TreatyOption, "minutes", m));

			yield return new LobbyOption(map, "peacetreaty", Label, Description, Visible, DisplayOrder,
				values, Default.ToStringInvariant(), Locked);
		}

		public override object Create(ActorInitializer init) { return new PxTreatyManager(init.Self, this); }
	}

	public class PxTreatyManager : ITick, IWorldLoaded, IValidateOrder, IChatCommand
	{
		[FluentReference("minutes")]
		const string Started = "notification-peace-treaty-started";

		[FluentReference("minutes")]
		const string MinutesLeft = "notification-peace-treaty-minutes-left";

		[FluentReference("seconds")]
		const string SecondsLeft = "notification-peace-treaty-seconds-left";

		[FluentReference]
		const string Ended = "notification-peace-treaty-ended";

		[FluentReference]
		const string Blocked = "notification-peace-treaty-blocked";

		[FluentReference("player", "votes", "needed")]
		const string Voted = "notification-peace-treaty-voted";

		[FluentReference("seconds")]
		const string VotePassed = "notification-peace-treaty-vote-passed";

		[FluentReference]
		const string NotActive = "notification-peace-treaty-not-active";

		[FluentReference]
		const string CommandDescription = "description-end-treaty";

		const string VoteOrder = "PxTreatyVote";

		readonly World world;
		readonly HashSet<Player> votes = new();
		readonly int minutes;
		int endTick;
		int endedAtTick = -1;
		int lastBlockedNotice = -1000;

		public bool IsActive => endedAtTick < 0 && endTick > 0;
		public PxTreatyManagerInfo Info { get; }
		public int TotalTicks => minutes * 60 * TicksPerSecond;
		public int TicksLeft => System.Math.Max(0, endTick - world.WorldTick);
		public int TicksSinceEnd => endedAtTick < 0 ? -1 : world.WorldTick - endedAtTick;
		public int TicksPerSecond { get; }
		public int VoteCount => votes.Count;
		public int VotersNeeded => Voters().Count;

		public PxTreatyManager(Actor self, PxTreatyManagerInfo info)
		{
			Info = info;
			world = self.World;
			TicksPerSecond = 1000 / world.Timestep;

			var value = world.LobbyInfo.GlobalSettings.OptionOrDefault("peacetreaty", Info.Default.ToStringInvariant());
			if (!int.TryParse(value, out minutes))
				minutes = Info.Default;

			endTick = minutes * 60 * TicksPerSecond;
		}

		/// <summary>True when the treaty forbids actors owned by these players from harming each other.</summary>
		public bool Protects(Player a, Player b)
		{
			return IsActive && a != null && b != null && a != b
				&& a.Playable && b.Playable && !a.NonCombatant && !b.NonCombatant;
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			if (minutes <= 0)
				return;

			var console = w.WorldActor.TraitOrDefault<ChatCommands>();
			var help = w.WorldActor.TraitOrDefault<HelpCommand>();
			if (console != null && help != null)
			{
				console.RegisterCommand("endtreaty", this);
				help.RegisterHelp("endtreaty", CommandDescription);
			}
		}

		void ITick.Tick(Actor self)
		{
			if (!IsActive)
				return;

			var tick = self.World.WorldTick;
			if (tick == 1)
				TextNotificationsManager.AddSystemLine(Started, "minutes", minutes);

			var left = endTick - tick;
			if (left <= 0)
			{
				EndTreaty(self.World);
				return;
			}

			if (left % TicksPerSecond != 0)
				return;

			var secondsLeft = left / TicksPerSecond;
			if (secondsLeft <= Info.CountdownSeconds)
				TextNotificationsManager.AddSystemLine(SecondsLeft, "seconds", secondsLeft);
			else if (secondsLeft % 60 == 0 && Info.WarningMinutes.Contains(secondsLeft / 60) && secondsLeft / 60 < minutes)
				TextNotificationsManager.AddSystemLine(MinutesLeft, "minutes", secondsLeft / 60);
		}

		void EndTreaty(World w)
		{
			endedAtTick = w.WorldTick;
			foreach (var p in w.ActorsWithTrait<PxTreatyProtection>())
				p.Trait.TreatyEnded(p.Actor);

			foreach (var p in w.ActorsWithTrait<PxTreatyPlayer>())
				p.Trait.TreatyEnded(p.Actor);

			TextNotificationsManager.AddSystemLine(Ended);
			if (Info.EndSpeechNotification != null && w.LocalPlayer != null)
				Game.Sound.PlayNotification(w.Map.Rules, w.LocalPlayer, "Speech", Info.EndSpeechNotification, w.LocalPlayer.Faction.InternalName);
		}

		static Player TargetOwner(in Target target)
		{
			return target.Type switch
			{
				TargetType.Actor => target.Actor.Owner,
				TargetType.FrozenActor => target.FrozenActor.Owner,
				_ => null,
			};
		}

		bool IValidateOrder.OrderValidation(OrderManager orderManager, World w, int clientId, Order order)
		{
			if (!IsActive || order.Subject == null)
				return true;

			var blocked = Info.BlockedSupportPowers.Contains(order.OrderString)
				|| (Info.BlockedTargetOrders.Contains(order.OrderString) && Protects(order.Subject.Owner, TargetOwner(order.Target)));

			if (blocked && order.Subject.Owner == w.LocalPlayer && w.WorldTick - lastBlockedNotice > 2 * TicksPerSecond)
			{
				lastBlockedNotice = w.WorldTick;
				TextNotificationsManager.AddFeedbackLine(Blocked);
			}

			return !blocked;
		}

		void IChatCommand.InvokeCommand(string name, string arg)
		{
			if (!IsActive)
			{
				TextNotificationsManager.AddFeedbackLine(NotActive);
				return;
			}

			var player = world.LocalPlayer;
			if (player != null && player.Playable && !player.NonCombatant && player.WinState == WinState.Undefined)
				world.IssueOrder(new Order(VoteOrder, player.PlayerActor, false));
		}

		/// <summary>Called on every client when a player's end-treaty vote order is resolved.</summary>
		public void Vote(Player player)
		{
			if (!IsActive || !votes.Add(player))
				return;

			var voters = Voters();
			var agreed = voters.Count(votes.Contains);
			TextNotificationsManager.AddSystemLine(Voted, "player", player.ResolvedPlayerName, "votes", agreed, "needed", voters.Count);

			if (agreed < voters.Count)
				return;

			var newEnd = world.WorldTick + Info.VoteEndDelay * TicksPerSecond;
			if (newEnd < endTick)
			{
				endTick = newEnd;
				TextNotificationsManager.AddSystemLine(VotePassed, "seconds", Info.VoteEndDelay);
			}
		}

		List<Player> Voters()
		{
			return world.Players.Where(p => p.Playable && !p.NonCombatant && !p.IsBot && p.WinState == WinState.Undefined).ToList();
		}

		public static bool IsVoteOrder(Order order) => order.OrderString == VoteOrder;
	}

	[Desc("Protects this actor while a peace treaty (PxTreatyManager) is active: no damage from other players, no enemy",
		"auto-targeting, and grants a condition (e.g. to disable Crushable) until the treaty ends.")]
	public class PxTreatyProtectionInfo : TraitInfo
	{
		[GrantedConditionReference]
		[Desc("Condition granted while the treaty is active (e.g. `treaty` on actors whose Crushable must be disabled).")]
		public readonly string Condition = null;

		public override object Create(ActorInitializer init) { return new PxTreatyProtection(init.Self, this); }
	}

	public class PxTreatyProtection : INotifyCreated, IDamageModifier, IDisableEnemyAutoTarget
	{
		readonly PxTreatyProtectionInfo info;
		readonly Actor self;
		PxTreatyManager manager;
		int token = Actor.InvalidConditionToken;

		public PxTreatyProtection(Actor self, PxTreatyProtectionInfo info)
		{
			this.self = self;
			this.info = info;
		}

		void INotifyCreated.Created(Actor self)
		{
			manager = self.World.WorldActor.TraitOrDefault<PxTreatyManager>();
			if (manager != null && manager.IsActive && !string.IsNullOrEmpty(info.Condition))
				token = self.GrantCondition(info.Condition);
		}

		public void TreatyEnded(Actor self)
		{
			if (token != Actor.InvalidConditionToken)
				token = self.RevokeCondition(token);
		}

		int IDamageModifier.GetDamageModifier(Actor attacker, Damage damage)
		{
			return attacker != null && manager != null && manager.Protects(attacker.Owner, self.Owner) ? 0 : 100;
		}

		bool IDisableEnemyAutoTarget.DisableEnemyAutoTarget(Actor self, Actor attacker)
		{
			return manager != null && manager.Protects(attacker.Owner, self.Owner);
		}
	}

	[TraitLocation(SystemActors.Player)]
	[Desc("Grants a condition on the player actor while a peace treaty is active (used to pause bot attack modules)",
		"and resolves the /endtreaty vote order.")]
	public class PxTreatyPlayerInfo : TraitInfo
	{
		[GrantedConditionReference]
		public readonly string Condition = "treaty";

		public override object Create(ActorInitializer init) { return new PxTreatyPlayer(this); }
	}

	public class PxTreatyPlayer : INotifyCreated, IResolveOrder
	{
		readonly PxTreatyPlayerInfo info;
		PxTreatyManager manager;
		int token = Actor.InvalidConditionToken;

		public PxTreatyPlayer(PxTreatyPlayerInfo info)
		{
			this.info = info;
		}

		void INotifyCreated.Created(Actor self)
		{
			manager = self.World.WorldActor.TraitOrDefault<PxTreatyManager>();
			if (manager != null && manager.IsActive && !string.IsNullOrEmpty(info.Condition))
				token = self.GrantCondition(info.Condition);
		}

		public void TreatyEnded(Actor self)
		{
			if (token != Actor.InvalidConditionToken)
				token = self.RevokeCondition(token);
		}

		void IResolveOrder.ResolveOrder(Actor self, Order order)
		{
			if (manager != null && PxTreatyManager.IsVoteOrder(order))
				manager.Vote(self.Owner);
		}
	}
}
