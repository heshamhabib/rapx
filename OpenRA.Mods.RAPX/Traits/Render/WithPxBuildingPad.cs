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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Traits.Render;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Draws a foundation pad as a single sprite under the building, centred like the building sprite.",
		"Replaces WithBuildingBib for HD buildings whose pad does not follow the cell grid.")]
	public class WithPxBuildingPadInfo : TraitInfo, Requires<BuildingInfo>, Requires<RenderSpritesInfo>,
		IRenderActorPreviewSpritesInfo, IActorPreviewInitInfo
	{
		[SequenceReference]
		public readonly string Sequence = "pad";

		[PaletteReference]
		public readonly string Palette = TileSet.TerrainPaletteInternalName;

		public override object Create(ActorInitializer init) { return new WithPxBuildingPad(init.Self, this); }

		public IEnumerable<IActorPreview> RenderPreviewSprites(ActorPreviewInitializer init, string image, int facings, PaletteReference p)
		{
			if (init.Contains<HidePadPreviewInit>(this))
				yield break;

			if (Palette != null)
				p = init.WorldRenderer.Palette(Palette);

			var anim = new Animation(init.World, image);
			anim.Play(Sequence);
			anim.IsDecoration = true;

			var zOffset = PadZOffset(init.Actor.TraitInfo<BuildingInfo>(), init.World);
			yield return new SpriteActorPreview(anim, () => WVec.Zero, () => zOffset, p);
		}

		IEnumerable<ActorInit> IActorPreviewInitInfo.ActorPreviewInits(ActorInfo ai, ActorPreviewType type)
		{
			// The placement preview already shows the footprint cells
			if (type == ActorPreviewType.PlaceBuilding)
				yield return new HidePadPreviewInit();
		}

		// Sort like a bib: at the top edge of the footprint, so everything on or in front of the building draws over it
		public static int PadZOffset(BuildingInfo bi, World world)
		{
			return -(bi.CenterOffset(world).Y + 512);
		}
	}

	public class WithPxBuildingPad : INotifyAddedToWorld, INotifyRemovedFromWorld
	{
		readonly WithPxBuildingPadInfo info;
		readonly RenderSprites rs;
		readonly BuildingInfo bi;
		AnimationWithOffset pad;

		public WithPxBuildingPad(Actor self, WithPxBuildingPadInfo info)
		{
			this.info = info;
			rs = self.Trait<RenderSprites>();
			bi = self.Info.TraitInfo<BuildingInfo>();
		}

		void INotifyAddedToWorld.AddedToWorld(Actor self)
		{
			var anim = new Animation(self.World, rs.GetImage(self));
			anim.Play(info.Sequence);
			anim.IsDecoration = true;

			pad = new AnimationWithOffset(anim, null, null, WithPxBuildingPadInfo.PadZOffset(bi, self.World));
			rs.Add(pad, info.Palette);
		}

		void INotifyRemovedFromWorld.RemovedFromWorld(Actor self)
		{
			if (pad != null)
				rs.Remove(pad);

			pad = null;
		}
	}

	sealed class HidePadPreviewInit : RuntimeFlagInit { }
}
