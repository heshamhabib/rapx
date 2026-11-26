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
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Plays a one-off sequence on a sprite body when this trait's condition switches on, e.g. Godzilla wading into",
		"the water (dive) or out of it (emerge) while his bodies swap. Afterwards the body goes back to its idle sequence,",
		"or to its move sequence when the actor is still walking. Not played for the condition the actor is created with.")]
	public class PxTransitionAnimationInfo : ConditionalTraitInfo, Requires<WithSpriteBodyInfo>
	{
		[Desc("Name of the WithSpriteBody that plays it.")]
		public readonly string Body = "body";

		[SequenceReference]
		[FieldLoader.Require]
		public readonly string Sequence = null;

		[SequenceReference]
		[Desc("Played (looping) afterwards while the actor moves. Empty: back to the body's idle sequence.")]
		public readonly string MoveSequence = null;

		public override object Create(ActorInitializer init) { return new PxTransitionAnimation(init.Self, this); }
	}

	public class PxTransitionAnimation : ConditionalTrait<PxTransitionAnimationInfo>, INotifyAddedToWorld
	{
		readonly IMove move;
		WithSpriteBody body;
		bool inWorld;

		public PxTransitionAnimation(Actor self, PxTransitionAnimationInfo info)
			: base(info)
		{
			move = self.TraitOrDefault<IMove>();
		}

		protected override void Created(Actor self)
		{
			body = self.TraitsImplementing<WithSpriteBody>().First(b => b.Info.Name == Info.Body);
			base.Created(self);
		}

		void INotifyAddedToWorld.AddedToWorld(Actor self)
		{
			// Conditions granted while the actor is being set up (spawned in or out of the water) play nothing
			self.World.AddFrameEndTask(_ => inWorld = true);
		}

		protected override void TraitEnabled(Actor self)
		{
			if (!inWorld || body == null)
				return;

			body.PlayCustomAnimation(self, Info.Sequence, () =>
			{
				if (!string.IsNullOrEmpty(Info.MoveSequence) && move != null && move.CurrentMovementTypes.HasMovementType(MovementType.Horizontal))
					body.PlayCustomAnimationRepeating(self, Info.MoveSequence);
			});
		}
	}
}
