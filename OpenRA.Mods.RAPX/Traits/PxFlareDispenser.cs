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
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Projectiles;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Countermeasure flares for jets: when a guided PxRocket locked on this actor is about to hit, a salvo of flares is",
		"released (PxFlareBurst) and every missile arriving while it burns rolls DecoyChance: a fooled missile turns away",
		"and bursts among the flares, the others still hit. Salvos are limited and come back one at a time.")]
	public class PxFlareDispenserInfo : ConditionalTraitInfo
	{
		[Desc("Flare salvos carried.")]
		public readonly int Salvos = 3;

		[Desc("Ticks to get one used salvo back.")]
		public readonly int ReloadDelay = 375;

		[Desc("Chance (percent) that a missile is fooled by a burning salvo.")]
		public readonly int DecoyChance = 65;

		[Desc("Flares are released when a missile is this many ticks from impact.")]
		public readonly int ReactionTicks = 14;

		[Desc("Ticks a salvo keeps protecting after release: missiles arriving meanwhile roll against it too.")]
		public readonly int CoverTicks = 24;

		[Desc("Flares in one salvo (cosmetic).")]
		public readonly int FlaresPerSalvo = 12;

		[Desc("Sound played when a salvo is released (one picked at random).")]
		public readonly string[] Sounds = Array.Empty<string>();

		public override object Create(ActorInitializer init) { return new PxFlareDispenser(init.Self, this); }
	}

	public class PxFlareDispenser : ConditionalTrait<PxFlareDispenserInfo>, ITick
	{
		readonly Actor self;

		[Sync]
		int salvos;

		[Sync]
		int reload;

		int cover;
		WPos burstAt;
		WVec burstVelocity;
		WPos lastPos;
		WVec velocity;

		public PxFlareDispenser(Actor self, PxFlareDispenserInfo info)
			: base(info)
		{
			this.self = self;
			salvos = info.Salvos;
		}

		/// <summary>Salvos ready to fire.</summary>
		public int Salvos => salvos;

		void ITick.Tick(Actor self)
		{
			var pos = self.CenterPosition;
			velocity = lastPos == WPos.Zero ? WVec.Zero : pos - lastPos;
			lastPos = pos;

			if (salvos < Info.Salvos && --reload <= 0)
			{
				salvos++;
				reload = Info.ReloadDelay;
			}

			if (cover > 0)
				cover--;

			if (IsTraitDisabled)
				return;

			// Effects are listed in the same order on every client, so the rolls stay in sync
			var threats = self.World.Effects.OfType<PxRocket>()
				.Where(r => r.InFlight && !r.Decoyed && !r.FlaresChecked && r.TargetActor == self && r.TicksLeft <= Info.ReactionTicks)
				.ToList();

			foreach (var rocket in threats)
			{
				rocket.FlaresChecked = true;
				if (cover == 0)
				{
					if (salvos == 0)
						continue;

					Release();
				}

				if (self.World.SharedRandom.Next(100) < Info.DecoyChance)
					rocket.Decoy(DecoyPoint(rocket.TicksLeft));
			}
		}

		void Release()
		{
			salvos--;
			if (reload <= 0)
				reload = Info.ReloadDelay;

			cover = Info.CoverTicks;
			burstAt = self.CenterPosition;
			burstVelocity = velocity;
			Log.Write("debug", $"PxFlareDispenser: {self.Info.Name} ({self.Owner.PlayerName}) released flares, {salvos} salvos left");
			var burst = new PxFlareBurst(self, velocity, Info.FlaresPerSalvo);
			self.World.AddFrameEndTask(w => w.Add(burst));
			if (Info.Sounds.Length > 0)
				Game.Sound.Play(SoundType.World, Info.Sounds.Random(Game.CosmeticRandom), self.CenterPosition);
		}

		/// <summary>Where the flare cloud will be when a missile gets there.</summary>
		WPos DecoyPoint(int ticksLeft)
		{
			return burstAt + PxFlareBurst.Drift(burstVelocity, Info.CoverTicks - cover + ticksLeft);
		}
	}
}
