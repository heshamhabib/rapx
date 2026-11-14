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
using System.Globalization;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// "Enemy structures remaining" counter: counts what the enemy still has to lose before they are defeated,
	/// using the same rule as ConquestVictoryConditions (short game: MustBeDestroyed actors with RequiredForShortGame,
	/// i.e. buildings and MCVs, even inside transports; otherwise every MustBeDestroyed actor in the world).
	/// Glows amber when only a few stragglers are left.
	/// </summary>
	public class PxEnemyRemainingWidget : Widget
	{
		public readonly string LabelFont = "PXSidebarSmall";
		public readonly string DigitFont = "PXDigitsMedium";

		[Desc("At or below this count the plate glows amber.")]
		public readonly int StragglerCount = 3;

		[Desc("Milliseconds between recounts.")]
		public readonly int RefreshInterval = 500;

		[FluentReference]
		const string TitleStructures = "label-px-enemy-remaining-structures";

		[FluentReference]
		const string TitleForces = "label-px-enemy-remaining-forces";

		[FluentReference("buildings", "mobile")]
		const string DetailStructures = "label-px-enemy-remaining-detail-structures";

		[FluentReference("buildings", "mobile")]
		const string DetailForces = "label-px-enemy-remaining-detail-forces";

		readonly World world;
		bool? shortGame;
		long nextCount;
		int buildings;
		int mobile;
		bool hasEnemies;

		[ObjectCreator.UseCtor]
		public PxEnemyRemainingWidget(World world)
		{
			this.world = world;
			IgnoreMouseOver = true;
		}

		protected PxEnemyRemainingWidget(PxEnemyRemainingWidget other)
			: base(other)
		{
			world = other.world;
			LabelFont = other.LabelFont;
			DigitFont = other.DigitFont;
			StragglerCount = other.StragglerCount;
			RefreshInterval = other.RefreshInterval;
			IgnoreMouseOver = true;
		}

		public override Widget Clone() { return new PxEnemyRemainingWidget(this); }

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		public override void Tick()
		{
			var now = Game.RunTime;
			if (now < nextCount)
				return;

			nextCount = now + RefreshInterval;
			Recount();
		}

		void Recount()
		{
			buildings = mobile = 0;
			hasEnemies = false;

			var me = world.LocalPlayer;
			if (me == null || me.WinState != WinState.Undefined)
				return;

			shortGame ??= world.WorldActor.TraitOrDefault<MapOptions>()?.ShortGame ?? true;

			foreach (var p in world.Players)
				if (!p.NonCombatant && p.Playable && p.WinState == WinState.Undefined && !p.IsAlliedWith(me))
					hasEnemies = true;

			if (!hasEnemies)
				return;

			foreach (var a in world.ActorsHavingTrait<MustBeDestroyed>(t => !shortGame.Value || t.Info.RequiredForShortGame))
			{
				var owner = a.Owner;
				if (a.IsDead || owner.NonCombatant || !owner.Playable || owner.IsAlliedWith(me) || owner.WinState != WinState.Undefined)
					continue;

				// Mirrors PlayerExtensions.HasNoRequiredUnits: the long game ignores actors that are not in the world
				if (!shortGame.Value && !a.IsInWorld)
					continue;

				if (a.Info.HasTraitInfo<BuildingInfo>())
					buildings++;
				else
					mobile++;
			}
		}

		public override void Draw()
		{
			if (!hasEnemies || shortGame == null)
				return;

			var total = buildings + mobile;
			var rb = RenderBounds;
			var straggler = total <= StragglerCount;
			var accent = straggler ? PxWarChrome.Amber : PxWarChrome.Hostile;
			var glow = straggler ? 0.35f + 0.65f * PxWarChrome.Pulse(1400) : 0;

			PxWarChrome.DrawSteelPlate(rb, 8, PxWarChrome.Darken(accent, 0.25f), glow, accent);

			// Count in a sunken LCD window on the right
			var digitFont = Game.Renderer.Fonts[DigitFont];
			var text = total.ToString(NumberFormatInfo.CurrentInfo);
			var size = digitFont.Measure(text);
			var wellWidth = Math.Max(size.X + 16, 40);
			var well = new Rectangle(rb.Right - wellWidth - 8, rb.Y + 7, wellWidth, rb.Height - 14);
			PxWarChrome.DrawWell(well);
			WidgetUtils.FillRectWithColor(well, Color.FromArgb(18, accent));
			digitFont.DrawTextWithContrast(text, new float2(well.X + (well.Width - size.X) / 2, well.Y + (well.Height - size.Y) / 2),
				PxWarChrome.Lerp(accent, Color.White, 0.2f), Color.FromArgb(90, accent), 1);

			// Stencilled title and the breakdown below it
			var labelFont = Game.Renderer.Fonts[LabelFont];
			var title = FluentProvider.GetMessage(shortGame.Value ? TitleStructures : TitleForces);
			PxWarChrome.DrawSpaced(labelFont, title, rb.X + 12, rb.Y + 8, 1, PxWarChrome.Stencil);

			var detail = FluentProvider.GetMessage(shortGame.Value ? DetailStructures : DetailForces, "buildings", buildings, "mobile", mobile);
			labelFont.DrawTextWithShadow(detail, new float2(rb.X + 12, rb.Y + 25), straggler ? accent : Color.FromArgb(170, PxWarChrome.Stencil),
				Color.Black, 1);
		}
	}
}
