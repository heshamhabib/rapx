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
using System.Reflection;
using OpenRA.Effects;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	public enum PxRallyStyle { Hex, Flag }

	[Desc("Replaces the stock rally point flag and target line: either a hologram hex road ending in a glowing hex cell (Style: Hex)",
		"or an HD banner on a glowing ground emblem linked by an animated energy beam (Style: Flag, art: artsrc/rally/make_rally.py).",
		"Does nothing on actors without RallyPoint (some maps remove it).")]
	public class PxRallyPointInfo : TraitInfo
	{
		[Desc("`Hex` = hologram honeycomb road ending in a big glowing hex cell, `Flag` = energy beam and HD banner.")]
		public readonly PxRallyStyle Style = PxRallyStyle.Hex;

		[Desc("Hex style: corner radius of the road cells in world pixels.")]
		public readonly float HexSize = 4.5f;

		[Desc("Hex style: corner radius of the big target cell in world pixels.")]
		public readonly float TargetHexSize = 20f;

		[Desc("Hex style: camera elevation in degrees the hexes are drawn for (see PxRenderBuildRadius).")]
		public readonly float CameraElevation = 50f;

		public readonly string Image = "pxrally";

		[SequenceReference(nameof(Image))]
		public readonly string FlagSequence = "flag";

		[SequenceReference(nameof(Image))]
		public readonly string BaseSequence = "base";

		[PaletteReference(nameof(IsPlayerPalette))]
		public readonly string Palette = "player";

		public readonly bool IsPlayerPalette = true;

		[Desc("Pixel in the flag frame (at sprite density) that stands on the rally point: the foot of the pole.")]
		public readonly int2 FlagAnchor = new(52, 214);

		[Desc("Horizontal radius of the ground emblem in world pixels. The beam stops at its rim.")]
		public readonly float RingRadius = 15.5f;

		[Desc("Vertical / horizontal ratio of the ground emblem ellipse.")]
		public readonly float RingRatio = 0.58f;

		[Desc("Width of the beam core in world pixels.")]
		public readonly float LineWidth = 1.4f;

		[Desc("Distance between the energy pulses running along the beam, in world pixels.")]
		public readonly float PulseSpacing = 16f;

		[Desc("Speed of the energy pulses, in world pixels per second.")]
		public readonly float PulseSpeed = 30f;

		public override object Create(ActorInitializer init) { return new PxRallyPoint(this); }
	}

	public class PxRallyPoint : INotifyCreated, INotifyAddedToWorld, INotifyRemovedFromWorld
	{
		static readonly FieldInfo StockEffectField = typeof(RallyPoint).GetField("effect", BindingFlags.Instance | BindingFlags.NonPublic);

		readonly PxRallyPointInfo info;
		RallyPoint rallyPoint;
		PxRallyPointIndicator indicator;

		public PxRallyPoint(PxRallyPointInfo info)
		{
			this.info = info;
		}

		void INotifyCreated.Created(Actor self)
		{
			// Resolved here rather than in the constructor: RallyPoint may be created after this trait.
			rallyPoint = self.TraitOrDefault<RallyPoint>();
			if (rallyPoint != null)
				indicator = new PxRallyPointIndicator(self, rallyPoint, info);
		}

		void INotifyAddedToWorld.AddedToWorld(Actor self)
		{
			if (indicator == null)
				return;

			indicator.StockEffect = StockEffectField?.GetValue(rallyPoint) as IEffect;
			self.World.AddFrameEndTask(w => w.Add(indicator));
		}

		void INotifyRemovedFromWorld.RemovedFromWorld(Actor self)
		{
			if (indicator != null)
				self.World.AddFrameEndTask(w => w.Remove(indicator));
		}
	}

	public class PxRallyPointIndicator : IEffect, IEffectAboveShroud
	{
		readonly Actor building;
		readonly RallyPoint rp;
		readonly PxRallyPointInfo info;
		readonly ISpriteSequence flag;
		readonly ISpriteSequence emblem;
		readonly List<WPos> nodes = new();
		List<CPos> cachedPath;

		// RallyPoint always adds its own indicator; it is removed once it shows up in the world.
		public IEffect StockEffect;

		public PxRallyPointIndicator(Actor building, RallyPoint rp, PxRallyPointInfo info)
		{
			this.building = building;
			this.rp = rp;
			this.info = info;
			var sequences = building.World.Map.Sequences;
			flag = sequences.GetSequence(info.Image, info.FlagSequence);
			emblem = sequences.GetSequence(info.Image, info.BaseSequence);
		}

		void IEffect.Tick(World world)
		{
			if (StockEffect != null && world.Effects.Contains(StockEffect))
			{
				var stock = StockEffect;
				world.AddFrameEndTask(w => w.Remove(stock));
				StockEffect = null;
			}

			if (cachedPath == null || !cachedPath.SequenceEqual(rp.Path))
				UpdateNodes(world);
		}

		void UpdateNodes(World world)
		{
			cachedPath = new List<CPos>(rp.Path);
			nodes.Clear();
			foreach (var c in cachedPath)
				nodes.Add(world.Map.CenterOfCell(c));

			if (nodes.Count == 0)
				return;

			var exit = building.NearestExitOrDefault(nodes[0]);
			nodes.Insert(0, building.CenterPosition + (exit?.Info.SpawnOffset ?? WVec.Zero));
		}

		IEnumerable<IRenderable> IEffect.Render(WorldRenderer wr) { return SpriteRenderable.None; }

		IEnumerable<IRenderable> IEffectAboveShroud.RenderAboveShroud(WorldRenderer wr)
		{
			if (nodes.Count < 2 || !building.IsInWorld || building.IsDead)
				yield break;

			if (!building.Owner.IsAlliedWith(building.World.LocalPlayer) || !building.World.Selection.Contains(building))
				yield break;

			var palette = wr.Palette(info.IsPlayerPalette ? info.Palette + building.Owner.InternalName : info.Palette);
			var showLine = Game.Settings.Game.TargetLines != TargetLinesType.Disabled;
			if (info.Style == PxRallyStyle.Hex)
			{
				yield return new PxHexRallyRenderable(nodes.ToArray(), info, building.OwnerColor(), showLine);
				yield break;
			}

			yield return new PxRallyPointRenderable(nodes.ToArray(), info, flag, emblem, palette, building.OwnerColor(), showLine);
		}
	}
}
