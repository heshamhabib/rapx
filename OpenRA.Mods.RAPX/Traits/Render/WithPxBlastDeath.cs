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
using OpenRA.Mods.Common.Effects;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Soldiers killed by an HD explosion (PxExplosion, registered in PxBlastRegistry) are thrown by the blast instead",
		"of dying where they stand: the body tumbles through the air away from the explosion, bounces and lies there",
		"(PxThrownBody). Deaths of these types without a blast nearby play the normal death sequence, as WithDeathAnimation",
		"would; keep these death types out of WithDeathAnimation.")]
	public class WithPxBlastDeathInfo : ConditionalTraitInfo, Requires<RenderSpritesInfo>
	{
		[Desc("Death types (from the warheads) handled here, each with the death sequence suffixes to play when no blast",
			"is found (as in WithDeathAnimation).")]
		public readonly Dictionary<string, string[]> DeathTypes = new();

		[Desc("Sequence prefix of the death animations.")]
		public readonly string DeathSequence = "die";

		[Desc("Palette of the body and the death animation.")]
		public readonly string Palette = "player";

		[Desc("Is Palette a player palette base name?")]
		public readonly bool PaletteIsPlayerPalette = true;

		[Desc("Sequence whose last frame is the flying body (turned along the flight); `stand` when the actor has none.")]
		public readonly string BodySequence = "liedown";

		[Desc("Chance (0-1) that a blast death throws the body rather than playing the death sequence.")]
		public readonly float ThrowChance = 1f;

		[Desc("How long the body lies where it fell before it fades, in ticks.")]
		public readonly int CorpseTicks = 300;

		public override object Create(ActorInitializer init) { return new WithPxBlastDeath(init.Self, this); }
	}

	public class WithPxBlastDeath : ConditionalTrait<WithPxBlastDeathInfo>, INotifyKilled, INotifyCrushed
	{
		readonly RenderSprites rs;
		readonly IFacing facing;
		readonly PxBlastRegistry registry;
		bool crushed;

		public WithPxBlastDeath(Actor self, WithPxBlastDeathInfo info)
			: base(info)
		{
			rs = self.Trait<RenderSprites>();
			facing = self.TraitOrDefault<IFacing>();
			registry = self.World.WorldActor.TraitOrDefault<PxBlastRegistry>();
		}

		void INotifyKilled.Killed(Actor self, AttackInfo e)
		{
			if (crushed || IsTraitDisabled || e.Damage.DamageTypes.IsEmpty)
				return;

			var type = Info.DeathTypes.Keys.FirstOrDefault(e.Damage.DamageTypes.Contains);
			if (type == null)
				return;

			var sequence = Info.DeathSequence + Info.DeathTypes[type].Random(self.World.SharedRandom);
			var palette = Info.Palette;
			if (Info.PaletteIsPlayerPalette)
				palette += self.Owner.InternalName;

			var image = rs.GetImage(self);
			var pos = self.CenterPosition;
			var face = facing?.Facing ?? WAngle.Zero;

			// The explosion that killed us registers itself right after the damage, in the same tick: decide at frame end
			self.World.AddFrameEndTask(w =>
			{
				if (registry != null && registry.TryFind(pos, out var blast) && Game.CosmeticRandom.NextFloat() < Info.ThrowChance)
					w.Add(new PxThrownBody(w, pos, blast, image, Info.BodySequence, palette, face, Info.CorpseTicks));
				else
					w.Add(new SpriteEffect(pos, w, image, sequence, palette));
			});
		}

		void INotifyCrushed.OnCrush(Actor self, Actor crusher, BitSet<CrushClass> crushClasses) { crushed = true; }
		void INotifyCrushed.WarnCrush(Actor self, Actor crusher, BitSet<CrushClass> crushClasses) { }
	}
}
