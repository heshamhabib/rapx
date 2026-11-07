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
using OpenRA.Mods.Common.Graphics;
using OpenRA.Mods.Common.Orders;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	public enum PxPlacePreviewType { Actor, Sequence, Footprint }

	[Desc("Project X: building placement preview whose footprint is a hologram pad of hex cells (PxFootprintHexRenderable) ",
		"instead of the classic per-cell overlay sprites. Replaces ActorPreview-, Sequence- and FootprintPlaceBuildingPreview.")]
	public class PxPlaceBuildingPreviewInfo : FootprintPlaceBuildingPreviewInfo
	{
		[Desc("What to show on the pad: the actor preview, one sequence of the actor, or the footprint only (walls).")]
		public readonly PxPlacePreviewType Preview = PxPlacePreviewType.Actor;

		[SequenceReference(allowNullImage: true)]
		[Desc("Sequence to show when Preview is Sequence.")]
		public readonly string Sequence = "idle";

		[Desc("Enable the building's idle animation.")]
		public readonly bool Animated = true;

		[Desc("Opacity of the building preview.")]
		public readonly float PreviewAlpha = 1f;

		[Desc("Footprint types to draw underneath the building preview.")]
		public readonly PlaceBuildingCellType FootprintUnderPreview = PlaceBuildingCellType.Valid | PlaceBuildingCellType.LineBuild;

		[Desc("Footprint types to draw above the building preview.")]
		public readonly PlaceBuildingCellType FootprintOverPreview = PlaceBuildingCellType.Invalid;

		[Desc("Hex size (centre to corner).")]
		public readonly WDist HexSize = new(341);

		public readonly Color ValidColor = Color.FromArgb(60, 240, 170);
		public readonly Color InvalidColor = Color.FromArgb(255, 56, 48);

		[Desc("Camera elevation in degrees the HD art is rendered at: squashes the hexes so they lie on the ground.")]
		public readonly float CameraElevation = 50f;

		protected override IPlaceBuildingPreview CreatePreview(WorldRenderer wr, ActorInfo ai, TypeDictionary init)
		{
			return new PxPlaceBuildingPreviewPreview(wr, ai, this, init);
		}

		public override object Create(ActorInitializer init) { return new PxPlaceBuildingPreview(); }
	}

	public class PxPlaceBuildingPreview { }

	public class PxPlaceBuildingPreviewPreview : FootprintPlaceBuildingPreviewPreview
	{
		readonly PxPlaceBuildingPreviewInfo info;
		readonly IActorPreview[] actorPreview = Array.Empty<IActorPreview>();
		readonly Animation sequencePreview;
		readonly PaletteReference sequencePalette;
		readonly float tilt;

		public PxPlaceBuildingPreviewPreview(WorldRenderer wr, ActorInfo ai, PxPlaceBuildingPreviewInfo info, TypeDictionary init)
			: base(wr, ai, info)
		{
			this.info = info;
			tilt = MathF.Sin(info.CameraElevation * MathF.PI / 180);

			if (info.Preview == PxPlacePreviewType.Actor)
			{
				var previewInit = new ActorPreviewInitializer(ActorInfo, wr, init);
				actorPreview = ActorInfo.TraitInfos<IRenderActorPreviewInfo>()
					.SelectMany(rpi => rpi.RenderPreview(previewInit))
					.ToArray();
			}
			else if (info.Preview == PxPlacePreviewType.Sequence)
			{
				var rsi = ai.TraitInfo<RenderSpritesInfo>();
				sequencePalette = wr.Palette(rsi.Palette ?? rsi.PlayerPalette + init.Get<OwnerInit>().InternalName);
				sequencePreview = new Animation(wr.World, rsi.GetImage(ai, init.Get<FactionInit>().Value));
				sequencePreview.PlayRepeating(info.Sequence);
			}
		}

		protected override void TickInner()
		{
			if (!info.Animated)
				return;

			foreach (var p in actorPreview)
				p.Tick();

			sequencePreview?.Tick();
		}

		protected override IEnumerable<IRenderable> RenderFootprint(WorldRenderer wr, CPos topLeft, Dictionary<CPos, PlaceBuildingCellType> footprint,
			PlaceBuildingCellType filter = PlaceBuildingCellType.Invalid | PlaceBuildingCellType.Valid | PlaceBuildingCellType.LineBuild)
		{
			if (footprint.Count == 0)
				yield break;

			var minX = footprint.Keys.Min(c => c.X);
			var minY = footprint.Keys.Min(c => c.Y);
			var maxX = footprint.Keys.Max(c => c.X);
			var maxY = footprint.Keys.Max(c => c.Y);

			var cells = footprint
				.Where(c => (c.Value & filter) != 0)
				.Select(c => (c.Key.X - minX, c.Key.Y - minY, (c.Value & PlaceBuildingCellType.Invalid) != 0,
					(c.Value & PlaceBuildingCellType.LineBuild) != 0 ? info.LineBuildFootprintAlpha : info.FootprintAlpha))
				.ToArray();

			if (cells.Length == 0)
				yield break;

			// Brackets once per footprint: on the blocked layer when anything is blocked, else on the valid one.
			var anyInvalid = footprint.Values.Any(v => (v & PlaceBuildingCellType.Invalid) != 0);
			var brackets = anyInvalid ? (filter & PlaceBuildingCellType.Invalid) != 0 : (filter & PlaceBuildingCellType.Valid) != 0;

			var map = wr.World.Map;
			var corner = map.CenterOfCell(new CPos(minX, minY)) - new WVec(512, 512, 0);
			var origin = new WPos(corner.X, corner.Y, map.CenterOfCell(topLeft).Z);
			yield return new PxFootprintHexRenderable(origin, cells, new int2(maxX - minX + 1, maxY - minY + 1), info.HexSize,
				info.ValidColor, info.InvalidColor, tilt, brackets);
		}

		protected override IEnumerable<IRenderable> RenderInner(WorldRenderer wr, CPos topLeft, Dictionary<CPos, PlaceBuildingCellType> footprint)
		{
			if (info.Preview == PxPlacePreviewType.Footprint)
				return RenderFootprint(wr, topLeft, footprint);

			return RenderWithBuilding(wr, topLeft, footprint);
		}

		IEnumerable<IRenderable> RenderWithBuilding(WorldRenderer wr, CPos topLeft, Dictionary<CPos, PlaceBuildingCellType> footprint)
		{
			if (info.FootprintUnderPreview != PlaceBuildingCellType.None)
				foreach (var r in RenderFootprint(wr, topLeft, footprint, info.FootprintUnderPreview))
					yield return r;

			var centerPosition = wr.World.Map.CenterOfCell(topLeft) + CenterOffset;
			IEnumerable<IRenderable> building = sequencePreview != null
				? sequencePreview.Render(centerPosition, WVec.Zero, 0, sequencePalette)
				: actorPreview.SelectMany(p => p.Render(wr, centerPosition)).OrderBy(WorldRenderer.RenderableZPositionComparisonKey);

			foreach (var r in building)
			{
				if (info.PreviewAlpha < 1f && r is IModifyableRenderable mr)
					yield return mr.WithAlpha(mr.Alpha * info.PreviewAlpha);
				else
					yield return r;
			}

			if (info.FootprintOverPreview != PlaceBuildingCellType.None)
				foreach (var r in RenderFootprint(wr, topLeft, footprint, info.FootprintOverPreview))
					yield return r;
		}
	}
}
