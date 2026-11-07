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
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	[Desc("HD ammo panel under the selected aircraft: one bar per ammo type (missiles, bombs, rockets, gun...).",
		"Ammo pools whose weapons belong to the same type are merged into one bar (e.g. three Maverick stations).",
		"Shows the refill of the next round while the ammo reloads or rearms, and blinks red when a type is empty.")]
	public class WithPxAmmoBarsInfo : TraitInfo, Requires<InteractableInfo>
	{
		[Desc("Weapon name prefix -> ammo type. The longest matching prefix wins; unmatched weapons get their own type.")]
		public readonly Dictionary<string, string> WeaponTypes = new();

		[Desc("Ammo type -> short label shown in front of its bar.")]
		public readonly Dictionary<string, string> TypeLabels = new();

		[Desc("Ammo type -> bar colour.")]
		public readonly Dictionary<string, Color> TypeColors = new();

		[Desc("Colour of ammo types missing from TypeColors.")]
		public readonly Color DefaultColor = Color.FromArgb(200, 205, 215);

		[Desc("Magazines up to this many rounds are drawn as one cell per round; bigger ones as a continuous bar.")]
		public readonly int MaxCells = 12;

		[Desc("Width of the bars in screen pixels.")]
		public readonly int BarWidth = 52;

		[Desc("Height of the bars in screen pixels, including their frame.")]
		public readonly int BarHeight = 6;

		[Desc("Gap between the decoration bounds and the panel, in screen pixels.")]
		public readonly int Margin = 3;

		[Desc("Ticks after a round was added during which the pool still counts as rearming (no ReloadAmmoPool).")]
		public readonly int RearmGrace = 30;

		public readonly string Font = "TinyBold";

		public override object Create(ActorInitializer init) { return new WithPxAmmoBars(init.Self, this); }
	}

	public class WithPxAmmoBars : INotifyCreated, ITick, IRenderAnnotationsWhenSelected
	{
		sealed class Group
		{
			public string Label;
			public Color Color;
			public readonly List<AmmoPool> Pools = new();
		}

		sealed class PoolState
		{
			public ReloadAmmoPool Reload;
			public int LastCount;
			public int LastChangeTick;
			public int LastGainTick = int.MinValue / 2;
		}

		readonly WithPxAmmoBarsInfo info;
		readonly Interactable interactable;
		readonly List<Group> groups = new();
		readonly Dictionary<AmmoPool, PoolState> states = new();

		public WithPxAmmoBars(Actor self, WithPxAmmoBarsInfo info)
		{
			this.info = info;
			interactable = self.Trait<Interactable>();
		}

		void INotifyCreated.Created(Actor self)
		{
			var armaments = self.TraitsImplementing<Armament>().ToArray();
			var reloads = self.TraitsImplementing<ReloadAmmoPool>().ToArray();
			var byType = new Dictionary<string, Group>();

			foreach (var pool in self.TraitsImplementing<AmmoPool>())
			{
				if (pool.Info.Ammo <= 0)
					continue;

				// A pool shared by several armaments takes the type of the first one.
				var weapon = armaments.FirstOrDefault(a => pool.Info.Armaments.Contains(a.Info.Name))?.Info.Weapon;
				if (weapon == null)
					continue;

				var type = TypeOf(weapon);
				if (!byType.TryGetValue(type, out var group))
				{
					group = new Group
					{
						Label = info.TypeLabels.TryGetValue(type, out var label) ? label : type.ToUpperInvariant(),
						Color = info.TypeColors.TryGetValue(type, out var color) ? color : info.DefaultColor
					};

					byType[type] = group;
					groups.Add(group);
				}

				group.Pools.Add(pool);
				states[pool] = new PoolState
				{
					Reload = reloads.FirstOrDefault(r => r.Info.AmmoPool == pool.Info.Name),
					LastCount = pool.CurrentAmmoCount
				};
			}
		}

		string TypeOf(string weapon)
		{
			string best = null;
			foreach (var kv in info.WeaponTypes)
				if (weapon.StartsWith(kv.Key, StringComparison.Ordinal) && (best == null || kv.Key.Length > best.Length))
					best = kv.Key;

			return best != null ? info.WeaponTypes[best] : weapon;
		}

		void ITick.Tick(Actor self)
		{
			var tick = self.World.WorldTick;
			foreach (var kv in states)
			{
				var count = kv.Key.CurrentAmmoCount;
				var s = kv.Value;
				if (count == s.LastCount)
					continue;

				// The reload timer runs from the last change: a round added, or the first round fired from a full pool.
				if (count > s.LastCount)
				{
					s.LastGainTick = tick;
					s.LastChangeTick = tick;
				}
				else if (s.LastCount == kv.Key.Info.Ammo)
					s.LastChangeTick = tick;

				s.LastCount = count;
			}
		}

		/// <summary>Progress (0..1) of the round being added to this pool, or -1 when it is not refilling.</summary>
		float RefillProgress(AmmoPool pool, int tick)
		{
			if (pool.HasFullAmmo)
				return -1;

			var s = states[pool];
			int period;
			if (s.Reload != null && !s.Reload.IsTraitDisabled && !s.Reload.IsTraitPaused)
				period = s.Reload.Info.Delay;
			else if (tick - s.LastGainTick <= pool.Info.ReloadDelay + info.RearmGrace)
				period = pool.Info.ReloadDelay;
			else
				return -1;

			return period > 0 ? Math.Clamp((float)(tick - s.LastChangeTick) / period, 0, 1) : 1;
		}

		IEnumerable<IRenderable> IRenderAnnotationsWhenSelected.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			if (groups.Count == 0 || !self.IsInWorld || self.IsDead)
				yield break;

			if (self.World.RenderPlayer != null && !self.Owner.IsAlliedWith(self.World.RenderPlayer))
				yield break;

			var tick = self.World.WorldTick;
			var rows = new PxAmmoBarRow[groups.Count];
			for (var i = 0; i < groups.Count; i++)
			{
				var g = groups[i];
				int current = 0, max = 0;
				var refill = -1f;
				foreach (var pool in g.Pools)
				{
					current += pool.CurrentAmmoCount;
					max += pool.Info.Ammo;
					refill = Math.Max(refill, RefillProgress(pool, tick));
				}

				rows[i] = new PxAmmoBarRow(g.Label, g.Color, current, max, refill);
			}

			yield return new PxAmmoBarsRenderable(self.CenterPosition, interactable.DecorationBounds(self, wr), rows,
				Game.Renderer.Fonts[info.Font], info);
		}

		bool IRenderAnnotationsWhenSelected.SpatiallyPartitionable => true;
	}
}
