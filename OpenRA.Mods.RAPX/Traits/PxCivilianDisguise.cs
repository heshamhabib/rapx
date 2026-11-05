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
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits
{
	[Desc("Makes a unit pass as a civilian to its enemies (the Spy Car): they see it in the neutral player's colours",
		"(pair with Tooltip GenericName + GenericVisibility: Enemy for the name) and their units do not attack it on",
		"their own. Taking damage or firing blows the cover for RevealDuration ticks. Allies and observers see the real unit.")]
	public class PxCivilianDisguiseInfo : TraitInfo
	{
		[Desc("Ticks the disguise stays blown after the unit is damaged or fires.")]
		public readonly int RevealDuration = 250;

		[Desc("Internal name of the player whose colours the disguise wears.")]
		public readonly string DisguiseAs = "Neutral";

		[Desc("Player palette prefix (RenderSprites PlayerPalette).")]
		public readonly string PlayerPalette = "player";

		[GrantedConditionReference]
		[Desc("Condition granted while disguised.")]
		public readonly string DisguisedCondition = null;

		public override object Create(ActorInitializer init) { return new PxCivilianDisguise(this); }
	}

	public class PxCivilianDisguise : IRenderModifier, IDisableEnemyAutoTarget, INotifyDamage, INotifyAttack, ITick, INotifyCreated
	{
		readonly PxCivilianDisguiseInfo info;
		int revealed;
		int token = Actor.InvalidConditionToken;
		Actor self;

		public PxCivilianDisguise(PxCivilianDisguiseInfo info) { this.info = info; }

		public bool Disguised => revealed <= 0;

		void INotifyCreated.Created(Actor self)
		{
			this.self = self;
			UpdateCondition();
		}

		void UpdateCondition()
		{
			if (string.IsNullOrEmpty(info.DisguisedCondition) || self == null)
				return;

			if (Disguised && token == Actor.InvalidConditionToken)
				token = self.GrantCondition(info.DisguisedCondition);
			else if (!Disguised && token != Actor.InvalidConditionToken)
				token = self.RevokeCondition(token);
		}

		void ITick.Tick(Actor self)
		{
			if (revealed > 0 && --revealed == 0)
				UpdateCondition();
		}

		void INotifyDamage.Damaged(Actor self, AttackInfo e)
		{
			if (e.Damage.Value > 0)
				Reveal();
		}

		void INotifyAttack.Attacking(Actor self, in Target target, Armament a, Barrel barrel)
		{
			Reveal();
		}

		void INotifyAttack.PreparingAttack(Actor self, in Target target, Armament a, Barrel barrel) { }

		void Reveal()
		{
			var wasDisguised = Disguised;
			revealed = info.RevealDuration;
			if (wasDisguised)
				UpdateCondition();
		}

		bool IDisableEnemyAutoTarget.DisableEnemyAutoTarget(Actor self, Actor attacker)
		{
			return Disguised && attacker.Owner.RelationshipWith(self.Owner) == PlayerRelationship.Enemy;
		}

		IEnumerable<IRenderable> IRenderModifier.ModifyRender(Actor self, WorldRenderer wr, IEnumerable<IRenderable> r)
		{
			var viewer = self.World.RenderPlayer;
			if (!Disguised || viewer == null || viewer.RelationshipWith(self.Owner) != PlayerRelationship.Enemy)
				return r;

			PaletteReference civilian;
			try
			{
				civilian = wr.Palette(info.PlayerPalette + info.DisguiseAs);
			}
			catch (Exception)
			{
				return r;
			}

			return r.Select(x => x is IPalettedRenderable p && p.Palette != null && p.Palette.Name.StartsWith(info.PlayerPalette, StringComparison.Ordinal)
				? p.WithPalette(civilian) : x);
		}

		IEnumerable<Rectangle> IRenderModifier.ModifyScreenBounds(Actor self, WorldRenderer wr, IEnumerable<Rectangle> r)
		{
			return r;
		}
	}
}
