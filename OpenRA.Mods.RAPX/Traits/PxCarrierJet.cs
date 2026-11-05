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
using OpenRA.Activities;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Orders;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Activities;
using OpenRA.Mods.RAPX.Traits.Render;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("A jet that can be based on an aircraft carrier (IDEA-08). Right-click your own carrier to rebase it there.",
		"While based on a carrier it returns to the carrier's deck (not to an airfield) when idle or out of ammo.",
		"Ordering it into an airfield rebases it back to land. On deck it is drawn at the carrier's ParkedScale, shrinking",
		"smoothly on final approach and growing back after the catapult shot.")]
	public class PxCarrierJetInfo : TraitInfo, Requires<AircraftInfo>
	{
		[FieldLoader.Require]
		[Desc("Kinds of deck this jet can use: Catapult, SkiJump, STOVL (matched against PxCarrierDeck.DeckTypes).")]
		public readonly HashSet<string> DeckTypes = new();

		public readonly string Cursor = "enter";
		public readonly string BlockedCursor = "enter-blocked";

		[VoiceReference]
		public readonly string Voice = "Action";

		[Desc("How fast the jet grows back to full size after leaving the deck (scale per tick).")]
		public readonly float GrowRate = 0.022f;

		public override object Create(ActorInitializer init) { return new PxCarrierJet(init.Self, this); }
	}

	public class PxCarrierJet : IIssueOrder, IResolveOrder, IOrderVoice, IReturnToBaseOverride, ITick, IRenderModifier
	{
		public const string OrderId = "PxLandOnCarrier";
		readonly Actor self;
		readonly PxCarrierJetInfo info;

		/// <summary>The carrier this jet is based on, or null when it belongs to the airfields.</summary>
		public Actor Home { get; private set; }

		/// <summary>True while it circles its carrier waiting to land (shown in the deck status).</summary>
		public bool Holding { get; set; }

		/// <summary>Last horizontal step while holding (formation followers match their leader's).</summary>
		public WVec LastMove { get; set; }

		/// <summary>Where this jet's formation slot was last tick (its slot velocity), or null when not following.</summary>
		public WPos? LastSlot { get; set; }

		/// <summary>True while it stands, rolls or taxis on the deck (or is stored there): drawn above the hull.</summary>
		public bool OnDeck { get; set; }

		/// <summary>Render scale for the deck (1 = normal). Deck activities hold it; otherwise it grows back to 1.</summary>
		public float DeckScale { get; private set; } = 1f;

		int holdTicks;

		public void HoldDeckScale(float scale)
		{
			DeckScale = scale;
			holdTicks = 2;
		}

		public PxCarrierJet(Actor self, PxCarrierJetInfo info)
		{
			this.self = self;
			this.info = info;
		}

		public PxCarrierDeck HomeDeck => Home != null && !Home.IsDead && Home.IsInWorld && Home.Owner == self.Owner
			? Home.TraitOrDefault<PxCarrierDeck>() : null;

		public void ClearHome()
		{
			if (Home != null && !Home.IsDead)
				Home.TraitOrDefault<PxCarrierDeck>()?.Release(self);

			Home = null;
			Holding = false;
			LastSlot = null;
			OnDeck = false;
		}

		bool SetHome(Actor carrier)
		{
			if (carrier == Home)
				return HomeDeck != null;

			var deck = carrier.TraitOrDefault<PxCarrierDeck>();
			if (deck == null || !deck.Assign(self))
				return false;

			ClearHome();
			Home = carrier;
			return true;
		}

		Activity IReturnToBaseOverride.ReturnToBase(Actor self, Actor dest)
		{
			if (Home == null)
				return null;

			// An explicit order into an airfield rebases the jet back to land.
			if (HomeDeck == null || (dest != null && dest != Home))
			{
				ClearHome();
				return null;
			}

			return new PxReturnToCarrier(self);
		}

		IEnumerable<IOrderTargeter> IIssueOrder.Orders
		{
			get
			{
				yield return new EnterAlliedActorTargeter<PxCarrierDeckInfo>(OrderId, 7, info.Cursor, info.BlockedCursor,
					(target, modifiers) => target.Owner == self.Owner && (target.TraitOrDefault<PxCarrierDeck>()?.Accepts(self) ?? false),
					target => target.TraitOrDefault<PxCarrierDeck>()?.HasRoomFor(self) ?? false);
			}
		}

		Order IIssueOrder.IssueOrder(Actor self, IOrderTargeter order, in Target target, bool queued)
		{
			return order.OrderID == OrderId ? new Order(order.OrderID, self, target, queued) : null;
		}

		void IResolveOrder.ResolveOrder(Actor self, Order order)
		{
			if (order.OrderString != OrderId)
				return;

			if (order.Target.Type != TargetType.Actor || !SetHome(order.Target.Actor))
				return;

			if (!order.Queued)
				self.Trait<Aircraft>().UnReserve();

			self.QueueActivity(order.Queued, new PxReturnToCarrier(self));
			self.ShowTargetLines();
		}

		void ITick.Tick(Actor self)
		{
			// Safety net: a jet clearly in the air is never "on deck" (it would be sorted under the map).
			if (OnDeck && self.World.Map.DistanceAboveTerrain(self.CenterPosition).Length > 1024)
				OnDeck = false;

			if (holdTicks > 0)
				holdTicks--;
			else if (!OnDeck && DeckScale < 1f)
				DeckScale = Math.Min(1f, DeckScale + info.GrowRate);
		}

		IEnumerable<IRenderable> IRenderModifier.ModifyRender(Actor self, WorldRenderer wr, IEnumerable<IRenderable> r)
		{
			if (!OnDeck && DeckScale > 0.999f)
				return r;

			// On deck, sort just above the hull; between jets, the one lower on screen stays in front. Just off the bow
			// (still small, low over the ship) stay above the hull too.
			var zOffset = 0;
			if (OnDeck && Home != null && !Home.IsDead)
			{
				var dy = Home.CenterPosition.Y - self.CenterPosition.Y;
				zOffset = dy + 512 - dy / 8;
			}
			else if (DeckScale < 1f)
				zOffset = 4096;

			var k = DeckScale;
			return r.Select(x => PxAltitudeScale.Scale(x, k, zOffset));
		}

		IEnumerable<Rectangle> IRenderModifier.ModifyScreenBounds(Actor self, WorldRenderer wr, IEnumerable<Rectangle> r)
		{
			return r;
		}

		string IOrderVoice.VoicePhraseForOrder(Actor self, Order order)
		{
			return order.OrderString == OrderId ? info.Voice : null;
		}
	}
}
