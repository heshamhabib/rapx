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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Draws a part of an HD building that floats on its own, e.g. the Prism Tower's crystal crown: it hovers above",
		"its seat with a slow bob and sway, and rises higher and livelier while ChargeCondition is true. While paused",
		"(e.g. low power) it settles onto its seat; it is never hidden by the pause, only by RequiresCondition.",
		"The part's sprite must use the same canvas and Offset as the body (artsrc/buildings/build_all.py FLOAT_TOP).",
		"Purely cosmetic (local clock).")]
	public class WithPxFloatingOverlayInfo : PausableConditionalTraitInfo, IRenderActorPreviewSpritesInfo, Requires<RenderSpritesInfo>
	{
		[SequenceReference]
		[Desc("Sequence of the floating part (a damaged- variant is used when damaged).")]
		public readonly string Sequence = "top";

		[Desc("Height of the hover above the seat, in screen pixels.")]
		public readonly float Hover = 2.5f;

		[Desc("Up-and-down bob amplitude, in screen pixels.")]
		public readonly float Bob = 1f;

		[Desc("Sideways sway amplitude, in screen pixels.")]
		public readonly float Sway = 0.4f;

		[Desc("Seconds per bob.")]
		public readonly float Period = 2.6f;

		[ConsumedConditionReference]
		[Desc("While true, the part rises by ChargeLift and bobs ChargeSpeed times faster.")]
		public readonly BooleanExpression ChargeCondition = null;

		public readonly float ChargeLift = 3f;
		public readonly float ChargeSpeed = 3f;

		[Desc("How fast the part moves to a new height (per second, 0-1 of the way per 1/Ease seconds).")]
		public readonly float Ease = 4f;

		public override object Create(ActorInitializer init) { return new WithPxFloatingOverlay(init.Self, this); }

		// Previews (placement ghost, map editor, catalogue) draw the part resting at its hover height, so the body
		// never shows without it
		public IEnumerable<IActorPreview> RenderPreviewSprites(ActorPreviewInitializer init, string image, int facings, PaletteReference p)
		{
			var anim = new Animation(init.World, image);
			anim.PlayRepeating(RenderSprites.NormalizeSequence(anim, init.GetDamageState(), Sequence));
			var lift = new WVec(0, 0, (int)(Hover * 1024f / 24f));
			yield return new SpriteActorPreview(anim, () => lift, () => lift.Z + 2, p);
		}
	}

	public class WithPxFloatingOverlay : PausableConditionalTrait<WithPxFloatingOverlayInfo>, INotifyDamageStateChanged
	{
		// World units per screen pixel (1024 per 24 pixel cell)
		const float WorldPerPixel = 1024f / 24f;

		readonly Animation overlay;
		readonly float phase;
		bool charging;
		float height;
		float clock;
		long lastTime = -1;

		public WithPxFloatingOverlay(Actor self, WithPxFloatingOverlayInfo info)
			: base(info)
		{
			var rs = self.Trait<RenderSprites>();
			overlay = new Animation(self.World, rs.GetImage(self));
			overlay.PlayRepeating(RenderSprites.NormalizeSequence(overlay, self.GetDamageState(), info.Sequence));
			phase = Game.CosmeticRandom.Next(1000) / 1000f * MathF.PI * 2;

			var anim = new AnimationWithOffset(overlay, Offset, () => IsTraitDisabled, p => RenderUtils.ZOffsetFromCenter(self, p, 2));
			rs.Add(anim);
		}

		WVec Offset()
		{
			// Advance with real frame time so the motion stays smooth at any game speed
			var now = Game.RunTime;
			var dt = lastTime < 0 ? 0 : Math.Min((now - lastTime) / 1000f, 0.1f);
			lastTime = now;

			var target = IsTraitPaused ? 0 : Info.Hover + (charging ? Info.ChargeLift : 0);
			height += (target - height) * Math.Min(1, dt * Info.Ease);

			var speed = IsTraitPaused ? 0 : charging ? Info.ChargeSpeed : 1;
			clock += dt * speed * MathF.PI * 2 / Info.Period;

			// The bob and sway fade out as the part settles onto its seat
			var live = Info.Hover > 0 ? Math.Clamp(height / Info.Hover, 0, 1) : 1;
			var up = height + live * Info.Bob * MathF.Sin(clock + phase);
			var side = live * Info.Sway * MathF.Sin(clock * 0.5f + phase * 1.3f);
			return new WVec((int)(side * WorldPerPixel), 0, (int)(up * WorldPerPixel));
		}

		public override IEnumerable<VariableObserver> GetVariableObservers()
		{
			foreach (var observer in base.GetVariableObservers())
				yield return observer;

			if (Info.ChargeCondition != null)
				yield return new VariableObserver(ChargeConditionsChanged, Info.ChargeCondition.Variables);
		}

		void ChargeConditionsChanged(Actor self, IReadOnlyDictionary<string, int> conditions)
		{
			charging = Info.ChargeCondition.Evaluate(conditions);
		}

		void INotifyDamageStateChanged.DamageStateChanged(Actor self, AttackInfo e)
		{
			overlay.ReplaceAnim(RenderSprites.NormalizeSequence(overlay, e.DamageState, Info.Sequence));
		}
	}
}
