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
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.Common;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Primitives;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("Developer tool: when the RAPX_SHOTS environment variable is set (\"x,y[,zoom];x,y[,zoom];...\" in cells),",
		"reveals the map, takes a screenshot at each location and then quits.",
		"When RAPX_MENU_SCRIPT is set (\"ms:action;ms:action;...\" with actions shot, stopvideo, quit, look [zoom],",
		"focus <ACTOR> [zoom], reveal, select <ACTOR,...>,",
		"build <ACTOR>, kill <ACTOR>, boom <WEAPON> +dx,+dy [height], chip <N> (select sidebar category chip N, 0 = All), spawn <RAPX_SPAWN entries>, click <BUTTON_ID>, press <BUTTON_ID>,",
		"scheme <ra2|ra2-right|openra>, key <KEY [Mods]> or clickcell <left|right> +dx,+dy [double]),",
		"runs those actions against the menus at the given times after the first shellmap load.",
		"When RAPX_DEV_CHEATS is set (\"enable-tech;unlimited-power;...\"), runs those developer chat commands",
		"as soon as a skirmish or mission loads (needs the lobby's debug menu option).",
		"Does nothing otherwise.")]
	public class DevScreenshotsInfo : TraitInfo
	{
		public readonly int StartDelay = 60;
		public readonly int Interval = 25;

		public override object Create(ActorInitializer init) { return new DevScreenshots(this); }
	}

	public sealed class DevScreenshots : IWorldLoaded, ITick
	{
		readonly DevScreenshotsInfo info;
		(CPos Cell, float Zoom)[] shots;
		WorldRenderer worldRenderer;
		static bool menuScriptStarted;
		static World currentWorld;
		static WorldRenderer currentWorldRenderer;
		int ticks;

		public DevScreenshots(DevScreenshotsInfo info)
		{
			this.info = info;
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			currentWorld = w;
			currentWorldRenderer = wr;
			var menuScript = Environment.GetEnvironmentVariable("RAPX_MENU_SCRIPT");
			if (!string.IsNullOrEmpty(menuScript) && w.Type == WorldType.Shellmap && !menuScriptStarted)
			{
				menuScriptStarted = true;
				foreach (var step in menuScript.Split(';', StringSplitOptions.RemoveEmptyEntries))
				{
					var parts = step.Split(':', 2);
					var action = parts[1].Trim();
					Game.RunAfterDelay(Exts.ParseInt32Invariant(parts[0].Trim()), () => RunMenuAction(action));
				}
			}

			if (w.Type != WorldType.Regular)
				return;

			SpawnActors(w);
			RunDevCheats(w);

			var spec = Environment.GetEnvironmentVariable("RAPX_SHOTS");
			if (string.IsNullOrEmpty(spec))
				return;

			worldRenderer = wr;
			shots = spec.Split(';', StringSplitOptions.RemoveEmptyEntries).Select(s =>
			{
				var p = s.Split(',').Select(x => x.Trim()).ToArray();
				var zoom = p.Length > 2 ? FieldLoader.GetValue<float>("zoom", p[2]) : 0f;
				return (new CPos(Exts.ParseInt32Invariant(p[0]), Exts.ParseInt32Invariant(p[1])), zoom);
			}).ToArray();

			// Show the whole map, as an observer would
			w.RenderPlayer = null;
		}

		/// <summary>
		/// RAPX_DEV_CHEATS="enable-tech;unlimited-power" runs those chat commands once the world has loaded
		/// (frame end, so the dev commands have registered themselves). Used by launch-game-test.sh.
		/// </summary>
		static void RunDevCheats(World w)
		{
			var cheats = Environment.GetEnvironmentVariable("RAPX_DEV_CHEATS");
			if (string.IsNullOrEmpty(cheats) || w.LocalPlayer == null)
				return;

			w.AddFrameEndTask(ww =>
			{
				var commands = ww.WorldActor.TraitOrDefault<Common.Commands.ChatCommands>();
				foreach (var cheat in cheats.Split(';', StringSplitOptions.RemoveEmptyEntries))
					commands?.OnChat(ww.LocalPlayer.PlayerName, "/" + cheat.Trim());
			});
		}

		/// <summary>
		/// RAPX_SPAWN="actor@x,y[,health%[,facing]];actor@x,y" places actors for the local player (else the first playable one), e.g. to preview
		/// new art. Coordinates starting with + or - are relative to that player's start location.
		/// Facing is a WAngle (0-1023, counter-clockwise from north). An optional fifth value spawns it that high (WDist,
		/// e.g. 2048 for a jet already in the air).
		/// </summary>
		static void SpawnActors(World w)
		{
			SpawnActors(w, Environment.GetEnvironmentVariable("RAPX_SPAWN"));
		}

		static void SpawnActors(World w, string spawn)
		{
			if (!string.IsNullOrEmpty(spawn))
			{
				var local = w.LocalPlayer ?? w.Players.First(p => p.Playable);
				foreach (var entry in spawn.Split(';', StringSplitOptions.RemoveEmptyEntries))
				{
					// actor@x,y[,health[,facing]][@N]: N picks the owner from the playable players (default: local player)
					var parts = entry.Split('@');
					var owner = parts.Length > 2 ? w.Players.Where(p => p.Playable).ElementAt(Exts.ParseInt32Invariant(parts[2])) : local;
					var xy = parts[1].Split(',');
					var relative = xy[0].StartsWith('+') || xy[0].StartsWith('-');
					var cell = new CPos(Exts.ParseInt32Invariant(xy[0].TrimStart('+')), Exts.ParseInt32Invariant(xy[1].TrimStart('+')));
					if (relative)
						cell += new CVec(local.HomeLocation.X, local.HomeLocation.Y);

					// Offsets written for one map land off the edge of another (e.g. a test script's map UID went stale
					// and the lobby fell back to the last map): an actor outside the map has no footprint and crashes
					// FrozenUnderFog, so skip it
					if (!w.Map.Contains(cell))
					{
						Log.Write("debug", $"DevScreenshots: skipped {parts[0].Trim()} at {cell}: outside the map ({w.Map.Title})");
						continue;
					}

					var inits = new TypeDictionary
					{
						new LocationInit(cell),
						new OwnerInit(owner),
						new FactionInit(owner.Faction.InternalName),
					};

					// Optional third value: starting health in percent (e.g. to preview damaged art)
					if (xy.Length > 2)
						inits.Add(new HealthInit(Exts.ParseInt32Invariant(xy[2])));

					if (xy.Length > 3)
						inits.Add(new FacingInit(new WAngle(Exts.ParseInt32Invariant(xy[3]))));

					if (xy.Length > 4)
						inits.Add(new CenterPositionInit(w.Map.CenterOfCell(cell) + new WVec(0, 0, Exts.ParseInt32Invariant(xy[4]))));

					w.AddFrameEndTask(ww =>
					{
						var a = ww.CreateActor(parts[0].Trim().ToLowerInvariant(), inits);
						Log.Write("debug", $"DevScreenshots: spawned {a.Info.Name} at {a.Location} for {owner.PlayerName}");
					});
				}
			}
		}

		void ITick.Tick(Actor self)
		{
			if (shots == null)
				return;

			self.World.RenderPlayer = null;
			var t = ticks++ - info.StartDelay;
			if (t < 0)
				return;

			// Move the camera at the start of each interval and capture half an interval later
			var i = t / info.Interval;
			var phase = t % info.Interval;
			if (i < shots.Length && phase == 0)
			{
				var viewport = worldRenderer.Viewport;

				// Zoom first: zooming adjusts around the current centre
				if (shots[i].Zoom > 0)
					viewport.AdjustZoom((float)Math.Log(shots[i].Zoom / viewport.Zoom));

				viewport.Center(self.World.Map.CenterOfCell(shots[i].Cell));

				Log.Write("debug", $"DevScreenshots: shot {i} at {shots[i].Cell} -> center {viewport.CenterLocation} zoom {viewport.Zoom}");
			}
			else if (i < shots.Length && phase == info.Interval / 2)
				Game.TakeScreenshot();
			else if (i > shots.Length + 1)
				Game.Exit();
		}

		static void RunMenuAction(string action)
		{
			Log.Write("debug", $"DevScreenshots: menu action {action}");
			if (action == "shot")
				Game.TakeScreenshot();
			else if (action == "quit")
				Game.Exit();
			else if (action.StartsWith("select ", StringComparison.Ordinal))
			{
				var types = action[7..].Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
				var actors = currentWorld.Actors.Where(a => a.Owner == currentWorld.LocalPlayer && a.IsInWorld && types.Contains(a.Info.Name));
				Sync.RunUnsynced(currentWorld, () => currentWorld.Selection.Combine(currentWorld, actors, false, false));
			}
			else if (action.StartsWith("focus ", StringComparison.Ordinal))
			{
				// "focus <actor> [zoom]": centre on the local player's first actor of that type
				var args = action[6..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
				var target = currentWorld.Actors.FirstOrDefault(a => a.Owner == currentWorld.LocalPlayer && a.IsInWorld && a.Info.Name == args[0]);
				var viewport = currentWorldRenderer.Viewport;
				if (args.Length > 1)
					viewport.AdjustZoom((float)Math.Log(FieldLoader.GetValue<float>("zoom", args[1]) / viewport.Zoom));

				if (target != null)
				{
					viewport.Center(target.CenterPosition);
					Log.Write("debug", $"DevScreenshots: focus {target.Info.Name} at {target.Location} -> {viewport.CenterLocation} zoom {viewport.Zoom}");
				}
				else
					Log.Write("debug", $"DevScreenshots: nothing to focus for {args[0]}");
			}
			else if (action == "reveal")
			{
				// Render as an observer: no shroud or fog
				currentWorld.RenderPlayer = null;
			}
			else if (action.StartsWith("look", StringComparison.Ordinal) && currentWorld.LocalPlayer != null)
			{
				// "look [zoom]": centre near the local player's base, optionally zooming first
				var viewport = currentWorldRenderer.Viewport;
				if (action.Length > 5)
					viewport.AdjustZoom((float)Math.Log(FieldLoader.GetValue<float>("zoom", action[5..].Trim()) / viewport.Zoom));

				viewport.Center(currentWorld.Map.CenterOfCell(currentWorld.LocalPlayer.HomeLocation + new CVec(5, 4)));
			}
			else if (action.StartsWith("center ", StringComparison.Ordinal))
			{
				// "center <x>,<y> [zoom]": centre on a cell (absolute map coordinates), e.g. to see the map edge
				var args = action[7..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
				var viewport = currentWorldRenderer.Viewport;
				if (args.Length > 1)
					viewport.AdjustZoom((float)Math.Log(FieldLoader.GetValue<float>("zoom", args[1]) / viewport.Zoom));

				var xy = FieldLoader.GetValue<int2>("cell", args[0]);
				viewport.Center(currentWorld.Map.CenterOfCell(new CPos(xy.X, xy.Y)));
			}
			else if (action.StartsWith("kill ", StringComparison.Ordinal))
			{
				// "kill <actor>": destroy the local player's first actor of that type (e.g. to preview death effects)
				var name = action[5..].Trim().ToLowerInvariant();
				var target = currentWorld.Actors.FirstOrDefault(a => a.Owner == currentWorld.LocalPlayer && a.IsInWorld && a.Info.Name == name);
				if (target != null)
					currentWorld.AddFrameEndTask(w => target.Kill(target));
				else
					Log.Write("debug", $"DevScreenshots: nothing to kill for {name}");
			}
			else if (action.StartsWith("attack ", StringComparison.Ordinal) && currentWorld.LocalPlayer != null)
			{
				// "attack <attacker[,attacker]> <target type>": the local player's actors of those types attack the
				// nearest enemy actor of the target type (e.g. to preview weapons and loadouts)
				var args = action[7..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
				var types = args[0].ToLowerInvariant().Split(',');
				var attackers = currentWorld.Actors.Where(a => a.Owner == currentWorld.LocalPlayer && a.IsInWorld && types.Contains(a.Info.Name)).ToList();
				foreach (var a in attackers)
				{
					var target = currentWorld.Actors
						.Where(t => t.IsInWorld && t.Info.Name == args[1].ToLowerInvariant() && t.Owner.RelationshipWith(a.Owner) == PlayerRelationship.Enemy)
						.MinByOrDefault(t => (t.CenterPosition - a.CenterPosition).LengthSquared);
					if (target != null)
						currentWorld.IssueOrder(new Order("Attack", a, Target.FromActor(target), false));
				}

				Log.Write("debug", $"DevScreenshots: {attackers.Count} attackers ordered at {args[1]}");
			}
			else if (action == "slots" && currentWorld.LocalPlayer != null)
			{
				// "slots": log the local player's airfield slot pools and which aircraft use them, and which aircraft
				// the Aircraft queue offers right now (a helicopter missing from it while slots are full = the bug)
				var player = currentWorld.LocalPlayer.PlayerActor;
				foreach (var q in player.TraitsImplementing<PxAirfieldProductionQueue>())
				{
					var buildable = string.Join(",", q.BuildableItems().Select(i => i.Name));
					Log.Write("debug", $"DevScreenshots: slots jets free {q.FreeSlots(0)} airlift free {q.FreeSlots(1)} | buildable {buildable}");
				}

				foreach (var r in currentWorld.ActorsWithTrait<Reservable>().Where(r => r.Actor.Owner == currentWorld.LocalPlayer && r.Trait.Info.HasSlots))
					Log.Write("debug", $"DevScreenshots: slots pads {r.Actor.Info.Name} free {r.Trait.SlotUsage().Free}/{r.Trait.SlotUsage().Total}");

				foreach (var a in currentWorld.Actors.Where(a => a.Owner == currentWorld.LocalPlayer && a.IsInWorld && a.Info.HasTraitInfo<AircraftInfo>()))
				{
					var home = Reservable.HomeOf(a);
					Log.Write("debug", $"DevScreenshots: slots aircraft {a.Info.Name} #{a.ActorID} home slot at [{home?.Info.Name}]");
				}
			}
			else if (action.StartsWith("ammo ", StringComparison.Ordinal))
			{
				// "ammo <type>": log the ammo left in every pool of the local player's actors of that type
				var name = action[5..].Trim().ToLowerInvariant();
				foreach (var a in currentWorld.Actors.Where(a => a.Owner == currentWorld.LocalPlayer && a.IsInWorld && a.Info.Name == name))
				{
					var pools = string.Join(", ", a.TraitsImplementing<AmmoPool>().Select(p => $"{p.Info.Name} {p.CurrentAmmoCount}/{p.Info.Ammo}"));
					var height = currentWorld.Map.DistanceAboveTerrain(a.CenterPosition).Length;
					var acts = new List<string>();
					var child = typeof(OpenRA.Activities.Activity).GetProperty("ChildActivity",
						System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public);
					for (var act = a.CurrentActivity; act != null; act = (OpenRA.Activities.Activity)child?.GetValue(act))
						acts.Add(act.GetType().Name);
					var foe = currentWorld.Actors.FirstOrDefault(t => t.IsInWorld && t.Owner.RelationshipWith(a.Owner) == PlayerRelationship.Enemy && t.Info.HasTraitInfo<MobileInfo>());
					var ft = foe != null ? Target.FromActor(foe) : Target.Invalid;
					var arms = string.Join(", ", a.TraitsImplementing<Armament>().Select(x => $"{x.Info.Name}{(x.IsTraitPaused ? " paused" : "")}{(x.IsTraitDisabled ? " disabled" : "")}" +
						(foe != null ? (x.Weapon.IsValidAgainst(ft, currentWorld, a) ? " ok-vs-" : " INVALID-vs-") + foe.Info.Name : "")));
					var attack = a.TraitsImplementing<AttackBase>().Select(t => string.Join("+", t.Armaments.Select(x => x.Info.Name)));
					arms += " | attack uses " + string.Join(" ; ", attack);
					Log.Write("debug", $"DevScreenshots: ammo {name} #{a.ActorID} (height {height}): {pools} | {string.Join(" > ", acts)} | {arms}");
				}
			}
			else if (action.StartsWith("fly ", StringComparison.Ordinal) && currentWorld.LocalPlayer != null)
			{
				// "fly <type[,type]> +dx,+dy": every player's actors of those types move to the cell at that offset from the
				// local player's start (aircraft take off), e.g. to put enemy jets in the air for a dogfight test
				var args = action[4..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
				var types = args[0].ToLowerInvariant().Split(',');
				var offset = FieldLoader.GetValue<int2>("offset", args[1].Replace("+", ""));
				var cell = currentWorld.LocalPlayer.HomeLocation + new CVec(offset.X, offset.Y);
				var target = Target.FromCell(currentWorld, cell);
				foreach (var a in currentWorld.Actors.Where(a => a.IsInWorld && types.Contains(a.Info.Name)).ToList())
					currentWorld.IssueOrder(new Order("Move", a, target, false));
			}
			else if (action.StartsWith("boom ", StringComparison.Ordinal) && currentWorld.LocalPlayer != null)
			{
				// "boom <weapon> +dx,+dy [height]": detonate that weapon's warheads at the cell at that offset from the local
				// player's start (optionally that high up, in WDist), e.g. to preview explosions
				var args = action[5..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
				if (!currentWorld.Map.Rules.Weapons.TryGetValue(args[0].ToLowerInvariant(), out var weapon))
				{
					Log.Write("debug", $"DevScreenshots: no weapon {args[0]}");
					return;
				}

				var offset = FieldLoader.GetValue<int2>("offset", args[1].Replace("+", ""));
				var cell = currentWorld.LocalPlayer.HomeLocation + new CVec(offset.X, offset.Y);
				var pos = currentWorld.Map.CenterOfCell(cell) + new WVec(0, 0, args.Length > 2 ? Exts.ParseInt32Invariant(args[2]) : 0);
				var source = currentWorld.LocalPlayer.PlayerActor;
				currentWorld.AddFrameEndTask(w => weapon.Impact(Target.FromPos(pos),
					new WarheadArgs { Weapon = weapon, SourceActor = source, ImpactPosition = pos, WeaponTarget = Target.FromPos(pos) }));
			}
			else if (action.StartsWith("spawn ", StringComparison.Ordinal))
				SpawnActors(currentWorld, action[6..].Trim());
			else if (action.StartsWith("build ", StringComparison.Ordinal))
				StartProduction(action[6..].Trim().ToLowerInvariant());
			else if (action.StartsWith("chip ", StringComparison.Ordinal))
				FindVisible<Widgets.PxCategoryBarWidget>(Ui.Root, null)?.SelectIndex(Exts.ParseInt32Invariant(action[5..].Trim()));
			else if (action.StartsWith("command ", StringComparison.Ordinal))
			{
				// "command <chat command>": run a chat command as if typed, e.g. "command endtreaty"
				var commands = currentWorld.WorldActor.TraitOrDefault<Common.Commands.ChatCommands>();
				commands?.OnChat(currentWorld.LocalPlayer?.PlayerName ?? "", "/" + action[8..].Trim());
			}
			else if (action == "stopvideo")
			{
				FindVisible<VideoPlayerWidget>(Ui.Root, null)?.Stop();
				FindVisible<Widgets.PxIntroPlayerWidget>(Ui.Root, null)?.Skip();
			}
			else if (action.StartsWith("click ", StringComparison.Ordinal))
			{
				var button = FindVisible<ButtonWidget>(Ui.Root, action[6..].Trim());
				if (button != null && !button.IsDisabled())
					Sync.RunUnsynced(currentWorld, button.OnClick);
				else
					Log.Write("debug", $"DevScreenshots: no clickable {action[6..]}");
			}
			else if (action.StartsWith("press ", StringComparison.Ordinal))
			{
				// Dropdown buttons open on mouse down rather than click
				var button = FindVisible<ButtonWidget>(Ui.Root, action[6..].Trim());
				if (button != null && !button.IsDisabled())
					Sync.RunUnsynced(currentWorld, () => button.OnMouseDown(default));
				else
					Log.Write("debug", $"DevScreenshots: no pressable {action[6..]}");
			}
			else if (action.StartsWith("scheme ", StringComparison.Ordinal))
			{
				// "scheme <ra2|ra2-right|openra>": apply a control scheme preset
				Widgets.Logic.PxControlSchemes.Apply(Game.ModData, action[7..].Trim());
				var scheme = action[7..].Trim();
				Log.Write("debug", $"DevScreenshots: control scheme now {Widgets.Logic.PxControlSchemes.Current(Game.ModData)}; differences: " +
					string.Join(", ", Widgets.Logic.PxControlSchemes.Differences(Game.ModData, scheme)));
			}
			else if (action.StartsWith("key ", StringComparison.Ordinal))
			{
				// "key <KEY [Mods]>", e.g. "key Z" or "key T": a key press as if typed
				if (Hotkey.TryParse(action[4..].Trim(), out var key))
				{
					foreach (var e in new[] { KeyInputEvent.Down, KeyInputEvent.Up })
						Sync.RunUnsynced(currentWorld, () => Ui.HandleKeyPress(new KeyInput { Key = key.Key, Modifiers = key.Modifiers, Event = e }));

					Log.Write("debug", $"DevScreenshots: key {key.DisplayString()}; order generator {currentWorld.OrderGenerator.GetType().Name}");
				}
				else
					Log.Write("debug", $"DevScreenshots: bad key {action[4..]}");
			}
			else if (action.StartsWith("clickcell ", StringComparison.Ordinal) && currentWorld.LocalPlayer != null)
			{
				// "clickcell <left|right> +dx,+dy [double]": click the cell at that offset from the player's start
				var args = action[10..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
				var button = args[0] == "right" ? MouseButton.Right : MouseButton.Left;
				var offset = FieldLoader.GetValue<int2>("offset", args[1].Replace("+", ""));
				var cell = currentWorld.LocalPlayer.HomeLocation + new CVec(offset.X, offset.Y);
				var screen = currentWorldRenderer.Viewport.WorldToViewPx(currentWorldRenderer.ScreenPxPosition(currentWorld.Map.CenterOfCell(cell)));
				var taps = args.Length > 2 && args[2] == "double" ? 2 : 1;
				for (var tap = 1; tap <= taps; tap++)
				{
					foreach (var e in new[] { MouseInputEvent.Down, MouseInputEvent.Up })
					{
						var mi = new MouseInput(e, button, screen, int2.Zero, Modifiers.None, tap);
						Sync.RunUnsynced(currentWorld, () => Ui.HandleInput(mi));
					}
				}

				var og = currentWorld.OrderGenerator;
				var waypoints = og is Orders.PxWaypointOrderGenerator wog ? $" ({wog.Count} waypoints)" : "";
				Log.Write("debug", $"DevScreenshots: {args[0]} click x{taps} on {cell} at {screen}; order generator {og.GetType().Name}{waypoints}");
			}
			else if (action.StartsWith("hovercell ", StringComparison.Ordinal) && currentWorld.LocalPlayer != null)
			{
				// "hovercell +dx,+dy": move the mouse over the cell at that offset from the player's start (shows its tooltip)
				var offset = FieldLoader.GetValue<int2>("offset", action[10..].Trim().Replace("+", ""));
				var cell = currentWorld.LocalPlayer.HomeLocation + new CVec(offset.X, offset.Y);
				var screen = currentWorldRenderer.Viewport.WorldToViewPx(currentWorldRenderer.ScreenPxPosition(currentWorld.Map.CenterOfCell(cell)));
				var mi = new MouseInput(MouseInputEvent.Move, MouseButton.None, screen, int2.Zero, Modifiers.None, 0);
				Sync.RunUnsynced(currentWorld, () => Ui.HandleInput(mi));
				Log.Write("debug", $"DevScreenshots: hover {cell} at {screen}");
			}
			else if (action.StartsWith("hover ", StringComparison.Ordinal))
			{
				// "hover x,y": move the mouse to that screen position (UI points), e.g. over a sidebar tile
				var screen = FieldLoader.GetValue<int2>("position", action[6..].Trim());
				var mi = new MouseInput(MouseInputEvent.Move, MouseButton.None, screen, int2.Zero, Modifiers.None, 0);
				Sync.RunUnsynced(currentWorld, () => Ui.HandleInput(mi));
				Log.Write("debug", $"DevScreenshots: hover at {screen}");
			}
			else if (action.StartsWith("clickat ", StringComparison.Ordinal))
			{
				// "clickat x,y": left click at that screen position (UI points), e.g. on a slider or seek bar
				var screen = FieldLoader.GetValue<int2>("position", action[8..].Trim());
				foreach (var e in new[] { MouseInputEvent.Move, MouseInputEvent.Down, MouseInputEvent.Up })
				{
					var mi = new MouseInput(e, e == MouseInputEvent.Move ? MouseButton.None : MouseButton.Left, screen, int2.Zero, Modifiers.None, 1);
					Sync.RunUnsynced(currentWorld, () => Ui.HandleInput(mi));
				}

				Log.Write("debug", $"DevScreenshots: click at {screen}");
			}
		}

		/// <summary>Queue one of the given actor on the first local production queue that can build it.</summary>
		static void StartProduction(string item)
		{
			var player = currentWorld?.LocalPlayer;
			var queue = player?.PlayerActor.TraitsImplementing<ProductionQueue>()
				.FirstOrDefault(q => q.Enabled && q.BuildableItems().Any(a => a.Name == item));
			if (queue == null)
			{
				Log.Write("debug", $"DevScreenshots: nothing can build {item}");
				return;
			}

			currentWorld.IssueOrder(Order.StartProduction(queue.Actor, item, 1));
		}

		static T FindVisible<T>(Widget w, string id) where T : Widget
		{
			if (!w.IsVisible())
				return null;

			if (w is T t && (id == null || w.Id == id))
				return t;

			foreach (var c in w.Children)
				if (FindVisible<T>(c, id) is T found)
					return found;

			return null;
		}
	}
}
