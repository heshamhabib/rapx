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
using System.Reflection;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("Draws a bridge actor's tiles with the HD tile art from PxHDTiles (intact, damaged and destroyed states)",
		"instead of the classic tile sprites. Cells without HD art keep the classic sprite.")]
	public class WithPxHDBridgeInfo : TraitInfo, Requires<BridgeInfo>
	{
		public override object Create(ActorInitializer init) { return new WithPxHDBridge(init.Self); }
	}

	public class WithPxHDBridge : IRenderModifier
	{
		// Bridge keeps its current template and footprint (cell -> tile index) private
		static readonly FieldInfo TemplateField = typeof(Bridge).GetField("template", BindingFlags.NonPublic | BindingFlags.Instance);
		static readonly FieldInfo FootprintField = typeof(Bridge).GetField("footprint", BindingFlags.NonPublic | BindingFlags.Instance);

		readonly Bridge bridge;
		readonly PxHDTiles tiles;

		public WithPxHDBridge(Actor self)
		{
			bridge = self.Trait<Bridge>();
			tiles = self.World.WorldActor.TraitOrDefault<PxHDTiles>();
		}

		IEnumerable<IRenderable> IRenderModifier.ModifyRender(Actor self, WorldRenderer wr, IEnumerable<IRenderable> r)
		{
			if (tiles == null || TemplateField?.GetValue(bridge) is not ushort template ||
				FootprintField?.GetValue(bridge) is not Dictionary<CPos, byte> footprint)
			{
				foreach (var renderable in r)
					yield return renderable;

				yield break;
			}

			var map = self.World.Map;
			foreach (var renderable in r)
			{
				if (renderable is SpriteRenderable sr && footprint.TryGetValue(map.CellContaining(sr.Pos), out var index))
				{
					var hd = tiles.CellSprite(template, index);
					if (hd != null)
					{
						yield return new SpriteRenderable(hd, sr.Pos, WVec.Zero, sr.ZOffset, null, tiles.CellScale, 1f,
							float3.Ones, TintModifiers.None, true);
						continue;
					}
				}

				yield return renderable;
			}
		}

		IEnumerable<Rectangle> IRenderModifier.ModifyScreenBounds(Actor self, WorldRenderer wr, IEnumerable<Rectangle> r)
		{
			return r;
		}
	}
}
