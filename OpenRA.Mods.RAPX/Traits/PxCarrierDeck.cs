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
using OpenRA.Graphics;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Activities;
using OpenRA.Mods.Common.Effects;
using OpenRA.Mods.Common.Orders;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Activities;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Mods.RAPX.Traits.Render;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	public enum PxDeckMode { Launch, Recover, Mixed }

	[Desc("Flight deck of an aircraft carrier (IDEA-08 2c, A1 launch and recovery cycles). Jets with a matching",
		"PxCarrierJet.DeckTypes are based here: they land on the deck (stored on board, drawn parked, rearmed and",
		"repaired) and take off again from the catapult. The deck is in one of three modes, cycled with the deploy key:",
		"Launch (every ready jet takes off, one per LaunchInterval; landing closed, returning jets hold overhead),",
		"Recover (no take-offs; jets land one per RecoveryInterval) and Mixed (both, MixedSlowdown % slower; jets only",
		"take off for a strike order). Right-click an enemy with the carrier selected to send its parked jets at it.")]
	public class PxCarrierDeckInfo : TraitInfo, Requires<BodyOrientationInfo>, Requires<IFacingInfo>
	{
		[Desc("How much the hull art shortens the north-south axis, in 1/1000 (the renders use a tilted camera).",
			"Deck offsets are true ship coordinates; they are squashed by this on screen, whatever the heading.")]
		public readonly int Foreshortening = 780;

		[Desc("How many jets can be based on this carrier (parked or in the air).")]
		public readonly int Slots = 6;

		[FieldLoader.Require]
		[Desc("Which jets may land here: jets whose PxCarrierJet.DeckTypes share a type with this list.",
			"Types used: Catapult, SkiJump, STOVL.")]
		public readonly HashSet<string> DeckTypes = new();

		[Desc("Mode when the carrier is built.")]
		public readonly PxDeckMode InitialMode = PxDeckMode.Mixed;

		[Desc("Ticks between two catapult launches.")]
		public readonly int LaunchInterval = 50;

		[Desc("Ticks a landed jet needs to taxi clear of the wires before the next one can land.")]
		public readonly int RecoveryInterval = 38;

		[Desc("Launch and recovery intervals in Mixed mode, in percent of the normal ones.")]
		public readonly int MixedSlowdown = 200;

		[Desc("Every RearmInterval ticks each parked jet gets one round per ammo pool and RepairPercent of its HP back.")]
		public readonly int RearmInterval = 15;

		public readonly int RepairPercent = 2;

		[Desc("Start of the catapult track (forward, right, up), relative to the ship centre: jets taxi here, line up",
			"with the ship's heading and are shot along the track.")]
		public readonly WVec CatapultStart = new(512, 0, 0);

		[Desc("End of the catapult track (the bow), where jets leave the deck.")]
		public readonly WVec LaunchOffset = new(1536, 0, 0);

		[Desc("Height above the water a launched jet has reached when it leaves the bow.")]
		public readonly WDist LaunchHeight = new(384);

		[Desc("Ticks of the catapult shot (the jet accelerates along the track).")]
		public readonly int ShotTicks = 14;

		[Desc("Point (forward, right, up) where jets touch down (the arresting wires on the angled deck).")]
		public readonly WVec RecoveryOffset = new(-1024, 0, 0);

		[Desc("Where a landed jet has rolled out to (along the landing strip), before it taxis to its parking spot.")]
		public readonly WVec RolloutOffset = new(-512, 0, 0);

		[Desc("Ticks of the roll-out after touch-down (the jet decelerates on the wires).")]
		public readonly int RolloutTicks = 14;

		[Desc("Taxi speed on deck, in world units per tick.")]
		public readonly int TaxiSpeed = 48;

		[Desc("Parking spots (forward, right, up), one per slot: every jet based here is drawn parked on deck.")]
		public readonly WVec[] ParkOffsets = Array.Empty<WVec>();

		[Desc("Facing of the parked jets relative to the ship, one per ParkOffsets entry (default: nose forward).")]
		public readonly WAngle[] ParkFacings = Array.Empty<WAngle>();

		[Desc("Sprite scale of jets on deck, on top of their own landed scale (decks are small). Jets shrink to it on",
			"final approach and grow back to full size after the catapult shot.")]
		public readonly float ParkedScale = 0.45f;

		[Desc("Radius of the holding pattern flown by jets waiting to land.")]
		public readonly WDist HoldingRadius = WDist.FromCells(9);

		[Desc("Jets holding over the carrier fly in V (arrow) formations of FormationSize jets (leader + wingmen),",
			"the Vs spaced evenly around the holding circle. Distance back and to the side per rank within a V.")]
		public readonly int FormationSize = 5;

		public readonly WDist FormationSpacing = new(2560);

		public readonly WDist FormationWidth = new(2816);

		[Desc("Length of the final approach: cleared jets turn onto the landing line this far astern of the wires,",
			"then glide in.")]
		public readonly WDist FinalLength = WDist.FromCells(6);

		[Desc("Height of the landing pattern (percent of cruise altitude) at the start of the final approach.")]
		public readonly int PatternAltitude = 55;

		[Desc("Speed at touch-down, in percent of the jet's speed (it slows down over the final approach).")]
		public readonly int TouchdownSpeed = 55;

		[Desc("Tyre smoke at touch-down.")]
		public readonly string TouchdownEffectImage = "smokey";

		[SequenceReference(nameof(TouchdownEffectImage), allowNullImage: true)]
		public readonly string TouchdownEffectSequence = "idle";

		[Desc("Distance from which a jet cleared to land starts its final approach.")]
		public readonly WDist ApproachRange = WDist.FromCells(6);

		[Desc("Catapult steam effect.")]
		public readonly string LaunchEffectImage = "smoke_m";

		[SequenceReference(nameof(LaunchEffectImage), allowNullImage: true)]
		public readonly string LaunchEffectSequence = "idle";

		[PaletteReference]
		public readonly string LaunchEffectPalette = "effect";

		public readonly string LaunchSound = null;
		public readonly string LandSound = null;

		[Desc("Fonts of the flight-deck HUD above the selected carrier: mode name and small print.")]
		public readonly string Font = "PXDeck";

		public readonly string SmallFont = "TinyBold";

		[VoiceReference]
		public readonly string Voice = "Action";

		public override object Create(ActorInitializer init) { return new PxCarrierDeck(init.Self, this); }
	}

	public class PxCarrierDeck : ITick, IRender, IRenderAnnotationsWhenSelected, IIssueOrder, IResolveOrder,
		IIssueDeployOrder, IOrderVoice, INotifyKilled, INotifyOwnerChanged, INotifyActorDisposing
	{
		const string ModeChanged = "notification-carrier-deck-mode";
		const string Title = "label-carrier-deck-title";
		static readonly string[] ModeLabels = { "label-carrier-deck-launch", "label-carrier-deck-recover", "label-carrier-deck-mixed" };
		static readonly Color[] ModeColors = { Color.FromArgb(255, 255, 128, 32), Color.FromArgb(255, 64, 230, 140), Color.FromArgb(255, 64, 200, 255) };

		public readonly PxCarrierDeckInfo Info;
		readonly Actor self;
		readonly IFacing facing;
		readonly Interactable interactable;
		int modeChangedTick = -100;

		// Jets based here (parked, on deck or in the air), jets stored on board, jets landing on deck (rolling out or
		// taxiing to their spot), each jet's parking spot, and the jets waiting for the catapult.
		readonly HashSet<Actor> based = new();
		readonly List<Actor> parked = new();
		readonly HashSet<Actor> landing = new();
		readonly Dictionary<Actor, int> spotOf = new();
		readonly List<Actor> launchQueue = new();
		readonly Dictionary<Actor, Target> strikeTargets = new();

		// Jets holding overhead, in the order they joined: the first leads the formation.
		readonly List<Actor> formation = new();

		// The jet cleared to land (one at a time).
		Actor cleared;
		int clearedTick;

		// The jet taxiing to / waiting on the catapult; the next one starts when it has been shot off.
		Actor onCatapult;

		int launchCooldown;
		int recoveryCooldown;
		int rearmTicks;

		public PxDeckMode Mode { get; private set; }

		public PxCarrierDeck(Actor self, PxCarrierDeckInfo info)
		{
			this.self = self;
			Info = info;
			facing = self.Trait<IFacing>();
			interactable = self.Trait<Interactable>();
			Mode = info.InitialMode;
		}

		public int Holding => based.Count(a => !a.IsDead && a.IsInWorld && a.TraitOrDefault<PxCarrierJet>()?.Holding == true);

		/// <summary>
		/// This holding jet's place in the formations: the V it flies in (0 = the lead V, which sets the circle), its
		/// place in that V (0 = the V's leader, then wingmen left/right by rank), the V's leader, the lead V's leader
		/// and the number of Vs.
		/// </summary>
		public (int Group, int Index, Actor GroupLeader, Actor Lead, int Groups) FormationSlot(Actor jet)
		{
			formation.RemoveAll(a => a.IsDead || !a.IsInWorld || !based.Contains(a) || a.TraitOrDefault<PxCarrierJet>()?.Holding != true);
			var position = formation.IndexOf(jet);
			if (position < 0)
			{
				formation.Add(jet);
				position = formation.Count - 1;
			}

			var size = Math.Max(1, Info.FormationSize);
			var group = position / size;
			var groups = (formation.Count + size - 1) / size;
			return (group, position % size, formation[group * size], formation[0], groups);
		}

		public bool Accepts(Actor jet)
		{
			var info = jet.Info.TraitInfoOrDefault<PxCarrierJetInfo>();
			return info != null && info.DeckTypes.Overlaps(Info.DeckTypes);
		}

		/// <summary>Whether the jet is based here or there is a free slot for it.</summary>
		public bool HasRoomFor(Actor jet)
		{
			return based.Contains(jet) || based.Count < Info.Slots;
		}

		/// <summary>Makes this carrier the jet's home. False if the deck is full or the jet doesn't fit.</summary>
		public bool Assign(Actor jet)
		{
			if (!Accepts(jet) || !HasRoomFor(jet))
				return false;

			based.Add(jet);
			return true;
		}

		public void Release(Actor jet)
		{
			based.Remove(jet);
			landing.Remove(jet);
			spotOf.Remove(jet);
			launchQueue.Remove(jet);
			strikeTargets.Remove(jet);
		}

		WVec ToWorld(WVec local)
		{
			// Deck coordinates are true ship coordinates. The HD hulls are rendered with a tilted camera that shortens
			// the north-south axis by Foreshortening (measured from the art); rotate, then squash that axis.
			var v = local.Rotate(WRot.FromYaw(facing.Facing));
			return new WVec(v.Y, -v.X * Info.Foreshortening / 1000, v.Z);
		}

		/// <summary>A deck point (forward, right, up) in the world, at deck level.</summary>
		public WPos DeckPos(WVec local)
		{
			var p = self.CenterPosition + ToWorld(local);
			return new WPos(p.X, p.Y, self.CenterPosition.Z);
		}

		/// <summary>World facing of a direction given in deck coordinates.</summary>
		public WAngle DeckYaw(WVec localDirection)
		{
			return ToWorld(localDirection).Yaw;
		}

		public WAngle ShipFacing => facing.Facing;

		/// <summary>A world position in deck coordinates (forward, right, up) relative to the ship's centre.</summary>
		public WVec DeckLocal(WPos pos)
		{
			// Inverse of ToWorld.
			var d = pos - self.CenterPosition;
			return new WVec(-d.Y * 1000 / Math.Max(1, Info.Foreshortening), d.X, d.Z).Rotate(WRot.FromYaw(-facing.Facing));
		}

		/// <summary>On-screen size of a parked jet (deck scale times its landed altitude scale).</summary>
		public float ParkedSize(PxAltitudeScale altitudeScale)
		{
			return Info.ParkedScale * (altitudeScale?.LandedScale ?? 1f);
		}

		public void TouchdownEffects(WPos pos)
		{
			if (Info.TouchdownEffectImage == null || Info.TouchdownEffectSequence == null)
				return;

			self.World.AddFrameEndTask(w =>
			{
				w.Add(new SpriteEffect(pos, w, Info.TouchdownEffectImage, Info.TouchdownEffectSequence, Info.LaunchEffectPalette));
				w.Add(new SpriteEffect(pos + ToWorld(new WVec(-160, 120, 0)), w, Info.TouchdownEffectImage, Info.TouchdownEffectSequence, Info.LaunchEffectPalette));
				w.Add(new SpriteEffect(pos + ToWorld(new WVec(-160, -120, 0)), w, Info.TouchdownEffectImage, Info.TouchdownEffectSequence, Info.LaunchEffectPalette));
			});
		}

		public WVec SpotOffset(Actor jet)
		{
			return spotOf.TryGetValue(jet, out var i) && i < Info.ParkOffsets.Length ? Info.ParkOffsets[i] : WVec.Zero;
		}

		public WAngle SpotFacing(Actor jet)
		{
			var relative = spotOf.TryGetValue(jet, out var i) && i < Info.ParkFacings.Length ? Info.ParkFacings[i] : WAngle.Zero;
			return facing.Facing + relative;
		}

		public WPos RecoveryPoint => DeckPos(Info.RecoveryOffset);

		/// <summary>
		/// Landing clearance: one jet at a time is cleared to leave the holding pattern and land, once the deck takes
		/// landings and the wires are clear. Keeps its clearance until it traps (or gives up / takes too long).
		/// </summary>
		public bool CanRecover(Actor jet)
		{
			if (Mode == PxDeckMode.Launch || !based.Contains(jet) || self.IsDead)
				return false;

			if (cleared != null && (cleared.IsDead || !cleared.IsInWorld || !based.Contains(cleared)
				|| landing.Contains(cleared) || self.World.WorldTick - clearedTick > 300))
				cleared = null;

			// Jets coming straight in land first; from the formation, the last jet peels off (so the leaders keep leading
			// and nobody changes place).
			formation.RemoveAll(a => a.IsDead || !a.IsInWorld || !based.Contains(a) || a.TraitOrDefault<PxCarrierJet>()?.Holding != true);
			var inFormation = formation.Contains(jet);
			if (cleared == null && recoveryCooldown <= 0 && (!inFormation || formation[^1] == jet))
			{
				cleared = jet;
				clearedTick = self.World.WorldTick;
				formation.Remove(jet);
			}

			return cleared == jet;
		}

		/// <summary>Touch-down on the wires: the jet gets its parking spot and rolls out (PxReturnToCarrier).</summary>
		public void BeginRecovery(Actor jet)
		{
			recoveryCooldown = Interval(Info.RecoveryInterval);
			if (cleared == jet)
				cleared = null;

			landing.Add(jet);
			if (!spotOf.ContainsKey(jet))
			{
				var free = 0;
				while (spotOf.ContainsValue(free))
					free++;

				spotOf[jet] = free;
			}

			if (Info.LandSound != null)
				Game.Sound.Play(SoundType.World, Info.LandSound, jet.CenterPosition);
		}

		/// <summary>The jet has taxied onto its spot: it leaves the map and is stored on deck (drawn by the carrier).</summary>
		public void CompleteRecovery(Actor jet)
		{
			landing.Remove(jet);
			parked.Add(jet);
			self.World.AddFrameEndTask(w =>
			{
				// The landing activity is done; drop whatever the jet was doing before it came home.
				jet.CancelActivity();
				w.Remove(jet);
				UpdateParkedPositions();
			});
		}

		/// <summary>Called by PxCatapultLaunch when the jet is shot off: steam, sound, and the catapult cycles.</summary>
		public void CatapultFired(Actor jet, WPos pos)
		{
			launchCooldown = Interval(Info.LaunchInterval);
			if (onCatapult == jet)
				onCatapult = null;

			if (Info.LaunchEffectImage != null && Info.LaunchEffectSequence != null)
				self.World.AddFrameEndTask(w => w.Add(new SpriteEffect(pos, w, Info.LaunchEffectImage, Info.LaunchEffectSequence, Info.LaunchEffectPalette)));

			if (Info.LaunchSound != null)
				Game.Sound.Play(SoundType.World, Info.LaunchSound, pos);
		}

		int Interval(int ticks)
		{
			return Mode == PxDeckMode.Mixed ? ticks * Info.MixedSlowdown / 100 : ticks;
		}

		static bool IsReady(Actor jet)
		{
			return jet.TraitsImplementing<AmmoPool>().All(p => p.HasFullAmmo);
		}

		static bool HasAmmo(Actor jet)
		{
			var pools = jet.TraitsImplementing<AmmoPool>().ToList();
			return pools.Count == 0 || pools.Any(p => p.HasAmmo);
		}

		void ITick.Tick(Actor self)
		{
			if (launchCooldown > 0)
				launchCooldown--;

			if (recoveryCooldown > 0)
				recoveryCooldown--;

			// Forget jets that died, changed hands or were rebased somewhere else.
			based.RemoveWhere(a => a.IsDead || a.Disposed || a.Owner != self.Owner
				|| (!parked.Contains(a) && a.TraitOrDefault<PxCarrierJet>()?.Home != self));
			parked.RemoveAll(a => !based.Contains(a));
			landing.RemoveWhere(a => !based.Contains(a));
			foreach (var a in spotOf.Keys.Where(a => !parked.Contains(a) && !landing.Contains(a)).ToList())
				spotOf.Remove(a);

			launchQueue.RemoveAll(a => !parked.Contains(a));
			if (onCatapult != null && (onCatapult.IsDead || !onCatapult.IsInWorld || onCatapult.TraitOrDefault<PxCarrierJet>()?.OnDeck != true))
				onCatapult = null;

			RearmParked();
			UpdateParkedPositions();

			// Launch mode: every ready jet goes up.
			if (Mode == PxDeckMode.Launch)
				foreach (var jet in parked)
					if (!launchQueue.Contains(jet) && IsReady(jet))
						launchQueue.Add(jet);

			if (Mode != PxDeckMode.Recover && onCatapult == null && launchCooldown <= 0 && launchQueue.Count > 0)
			{
				var jet = launchQueue[0];
				launchQueue.RemoveAt(0);
				Launch(jet);
			}
		}

		void RearmParked()
		{
			if (++rearmTicks < Info.RearmInterval)
				return;

			rearmTicks = 0;
			foreach (var jet in parked)
			{
				foreach (var pool in jet.TraitsImplementing<AmmoPool>())
					if (!pool.HasFullAmmo)
						pool.GiveAmmo(jet, 1);

				var health = jet.TraitOrDefault<Health>();
				if (health != null && health.HP < health.MaxHP)
					health.InflictDamage(jet, self, new Damage(-Math.Max(1, health.MaxHP * Info.RepairPercent / 100)), true);
			}
		}

		void UpdateParkedPositions()
		{
			foreach (var jet in parked)
			{
				var aircraft = jet.TraitOrDefault<Aircraft>();
				if (aircraft == null)
					continue;

				aircraft.SetPosition(jet, DeckPos(SpotOffset(jet)));
				aircraft.Facing = SpotFacing(jet);
			}
		}

		void Launch(Actor jet)
		{
			var spot = SpotOffset(jet);
			var spotFacing = SpotFacing(jet);
			parked.Remove(jet);
			spotOf.Remove(jet);
			onCatapult = jet;
			strikeTargets.TryGetValue(jet, out var target);
			strikeTargets.Remove(jet);

			var pos = DeckPos(spot);
			var climbOut = DeckPos(Info.LaunchOffset) + ToWorld(new WVec(WDist.FromCells(5).Length, 0, 0));
			var carrier = self;

			self.World.AddFrameEndTask(w =>
			{
				if (jet.IsDead || jet.Disposed)
					return;

				var aircraft = jet.Trait<Aircraft>();
				aircraft.SetPosition(jet, pos);
				aircraft.Facing = spotFacing;
				w.Add(jet);

				// Taxi to the catapult and get shot off the bow, then attack or climb out.
				jet.QueueActivity(false, new PxCatapultLaunch(jet, carrier, spot));
				if (target.Type != TargetType.Invalid && target.IsValidFor(jet))
					jet.ResolveOrder(new Order("Attack", jet, target, true));
				else
					jet.QueueActivity(new Fly(jet, Target.FromPos(climbOut)));
			});
		}

		void Strike(in Target target)
		{
			foreach (var jet in parked)
			{
				if (!HasAmmo(jet))
					continue;

				strikeTargets[jet] = target;
				if (!launchQueue.Contains(jet))
					launchQueue.Add(jet);
			}
		}

		void SetMode(PxDeckMode mode)
		{
			Mode = mode;
			modeChangedTick = self.World.WorldTick;
			if (mode == PxDeckMode.Recover)
			{
				// Strike orders wait in the queue; plain Launch-mode take-offs are dropped.
				launchQueue.RemoveAll(a => !strikeTargets.ContainsKey(a));
			}

			if (self.Owner == self.World.LocalPlayer)
				TextNotificationsManager.AddFeedbackLine(ModeChanged, "mode", FluentProvider.GetMessage(ModeLabels[(int)mode]));
		}

		IEnumerable<IOrderTargeter> IIssueOrder.Orders
		{
			get { yield return new DeckStrikeOrderTargeter(this); }
		}

		Order IIssueOrder.IssueOrder(Actor self, IOrderTargeter order, in Target target, bool queued)
		{
			return order.OrderID == DeckStrikeOrderTargeter.Id ? new Order(order.OrderID, self, target, queued) : null;
		}

		Order IIssueDeployOrder.IssueDeployOrder(Actor self, bool queued)
		{
			return new Order("PxDeckMode", self, queued);
		}

		bool IIssueDeployOrder.CanIssueDeployOrder(Actor self, bool queued) { return true; }

		void IResolveOrder.ResolveOrder(Actor self, Order order)
		{
			if (order.OrderString == "PxDeckMode")
				SetMode((PxDeckMode)(((int)Mode + 1) % 3));
			else if (order.OrderString == DeckStrikeOrderTargeter.Id && order.Target.Type != TargetType.Invalid)
				Strike(order.Target);
		}

		string IOrderVoice.VoicePhraseForOrder(Actor self, Order order)
		{
			return order.OrderString == "PxDeckMode" || order.OrderString == DeckStrikeOrderTargeter.Id ? Info.Voice : null;
		}

		void ReleaseAll(AttackInfo e)
		{
			foreach (var jet in based.ToList())
			{
				// When the whole game shuts down, the jets may be disposed before the ship.
				if (jet.Disposed)
					continue;

				if (parked.Contains(jet))
				{
					if (!jet.Disposed)
						jet.Dispose();
				}
				else
				{
					// Jets on deck (landing or on the catapult) go down with the ship; jets in the air lose their home.
					var carrierJet = jet.TraitOrDefault<PxCarrierJet>();
					var onDeck = carrierJet?.OnDeck == true;
					carrierJet?.ClearHome();
					if (onDeck && e != null && !jet.IsDead)
						jet.Kill(e.Attacker);
				}
			}

			based.Clear();
			parked.Clear();
			landing.Clear();
			spotOf.Clear();
			launchQueue.Clear();
			strikeTargets.Clear();
			onCatapult = null;
		}

		// Jets parked on deck go down with the ship.
		void INotifyKilled.Killed(Actor self, AttackInfo e) { ReleaseAll(e); }
		void INotifyActorDisposing.Disposing(Actor self) { ReleaseAll(null); }

		void INotifyOwnerChanged.OnOwnerChanged(Actor self, Player oldOwner, Player newOwner)
		{
			// Jets on deck change hands with the ship; jets in the air stay with their old owner and lose their home.
			foreach (var jet in parked)
				jet.ChangeOwner(newOwner);

			foreach (var jet in based)
			{
				if (parked.Contains(jet))
					continue;

				if (jet.TraitOrDefault<PxCarrierJet>()?.OnDeck == true)
					jet.ChangeOwner(newOwner);
				else
					jet.TraitOrDefault<PxCarrierJet>()?.ClearHome();
			}

			based.RemoveWhere(a => !parked.Contains(a) && a.TraitOrDefault<PxCarrierJet>()?.OnDeck != true);
			launchQueue.Clear();
			strikeTargets.Clear();
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			// Parked jets are off the map; draw them here. PxCarrierJet scales them to deck size and sorts them above the hull.
			foreach (var jet in parked)
				if (!jet.Disposed)
					foreach (var r in jet.Render(wr))
						yield return r;
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			yield break;
		}

		IEnumerable<IRenderable> IRenderAnnotationsWhenSelected.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			if (self.World.RenderPlayer != null && !self.Owner.IsAlliedWith(self.World.RenderPlayer))
				yield break;

			// Catapult cycle while launching, wire cycle while recovering.
			var cooldown = Mode == PxDeckMode.Recover ? recoveryCooldown : launchCooldown;
			var interval = Interval(Mode == PxDeckMode.Recover ? Info.RecoveryInterval : Info.LaunchInterval);
			var readiness = interval > 0 ? 1f - (float)cooldown / interval : 1f;
			var flash = Math.Clamp(1f - (self.World.WorldTick - modeChangedTick) / 20f, 0f, 1f);

			var status = new PxDeckStatus((int)Mode, FluentProvider.GetMessage(ModeLabels[(int)Mode]),
				FluentProvider.GetMessage(Title), ModeColors[(int)Mode], Info.Slots, parked.Count,
				based.Count - parked.Count, Holding, launchQueue.Count, readiness, flash);

			yield return new PxDeckStatusRenderable(self.CenterPosition, interactable.DecorationBounds(self, wr), status,
				Game.Renderer.Fonts[Info.Font], Game.Renderer.Fonts[Info.SmallFont]);
		}

		bool IRenderAnnotationsWhenSelected.SpatiallyPartitionable => true;

		sealed class DeckStrikeOrderTargeter : UnitOrderTargeter
		{
			public const string Id = "PxDeckStrike";
			readonly PxCarrierDeck deck;

			public DeckStrikeOrderTargeter(PxCarrierDeck deck)
				: base(Id, 5, "attack", true, false)
			{
				this.deck = deck;
			}

			public override bool CanTargetActor(Actor self, Actor target, TargetModifiers modifiers, ref string cursor)
			{
				// Jets on deck attack ground and naval targets; the carrier's own SAMs deal with aircraft.
				return deck.parked.Count > 0 && !(target.Info.HasTraitInfo<AircraftInfo>() && !target.IsAtGroundLevel());
			}

			public override bool CanTargetFrozenActor(Actor self, FrozenActor target, TargetModifiers modifiers, ref string cursor)
			{
				return deck.parked.Count > 0 && !target.Info.HasTraitInfo<AircraftInfo>();
			}
		}
	}
}
