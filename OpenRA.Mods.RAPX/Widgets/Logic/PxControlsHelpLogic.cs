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
using System.Linq;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>In-game list of the current mouse controls and hotkeys (IDEA-11), opened from the in-game menu.</summary>
	public class PxControlsHelpLogic : ChromeLogic
	{
		[FluentReference("scheme")]
		const string SchemeLine = "label-px-controls-scheme";

		[FluentReference]
		const string HeaderMouse = "label-px-controls-header.mouse";

		[FluentReference]
		const string HeaderUnits = "label-px-controls-header.units";

		[FluentReference]
		const string HeaderBase = "label-px-controls-header.base";

		[FluentReference]
		const string HeaderSidebar = "label-px-controls-header.sidebar";

		[FluentReference]
		const string HeaderTeams = "label-px-controls-header.teams";

		[FluentReference]
		const string MouseSelect = "label-px-controls-mouse-select";

		[FluentReference]
		const string MouseSelectInput = "label-px-controls-mouse-select.input";

		[FluentReference]
		const string MouseOrder = "label-px-controls-mouse-order";

		[FluentReference]
		const string MouseOrderClassic = "label-px-controls-mouse-order.classic";

		[FluentReference]
		const string MouseOrderModern = "label-px-controls-mouse-order.modern";

		[FluentReference]
		const string MouseDeselect = "label-px-controls-mouse-deselect";

		[FluentReference]
		const string MouseDeselectClassic = "label-px-controls-mouse-deselect.classic";

		[FluentReference]
		const string MouseDeselectModern = "label-px-controls-mouse-deselect.modern";

		[FluentReference]
		const string MouseScroll = "label-px-controls-mouse-scroll";

		[FluentReference]
		const string MouseScrollRight = "label-px-controls-mouse-scroll.right";

		[FluentReference]
		const string MouseScrollMiddle = "label-px-controls-mouse-scroll.middle";

		[FluentReference]
		const string MouseSameType = "label-px-controls-mouse-same-type";

		[FluentReference]
		const string MouseSameTypeInput = "label-px-controls-mouse-same-type.input";

		[FluentReference]
		const string MousePrimary = "label-px-controls-mouse-primary";

		[FluentReference]
		const string MousePrimaryInput = "label-px-controls-mouse-primary.input";

		[FluentReference]
		const string MouseAdd = "label-px-controls-mouse-add";

		[FluentReference]
		const string MouseAddInput = "label-px-controls-mouse-add.input";

		[FluentReference]
		const string MouseForceFire = "label-px-controls-mouse-force-fire";

		[FluentReference]
		const string MouseForceFireInput = "label-px-controls-mouse-force-fire.input";

		[FluentReference]
		const string MouseForceMove = "label-px-controls-mouse-force-move";

		[FluentReference]
		const string MouseForceMoveInput = "label-px-controls-mouse-force-move.input";

		[FluentReference]
		const string NoteTwice = "label-px-controls-note.twice";

		[FluentReference]
		const string NoteWaypoint = "label-px-controls-note.waypoint";

		[FluentReference]
		const string TeamCreate = "label-px-controls-team.create";

		[FluentReference]
		const string TeamSelect = "label-px-controls-team.select";

		[FluentReference]
		const string TeamAdd = "label-px-controls-team.add";

		[FluentReference]
		const string TeamJump = "label-px-controls-team.jump";

		[FluentReference]
		const string BookmarkSave = "label-px-controls-bookmark.save";

		[FluentReference]
		const string BookmarkJump = "label-px-controls-bookmark.jump";

		[FluentReference]
		const string Unbound = "label-px-controls-unbound";

		readonly ModData modData;
		readonly ScrollPanelWidget list;
		readonly Widget headerTemplate;
		readonly Widget rowTemplate;

		[ObjectCreator.UseCtor]
		public PxControlsHelpLogic(Widget widget, ModData modData, Action onExit)
		{
			this.modData = modData;

			var scheme = FluentProvider.GetMessage(SchemeLine, "scheme", PxControlSchemes.Name(PxControlSchemes.Current(modData)));
			widget.Get<LabelWidget>("SCHEME").GetText = () => scheme;

			list = widget.Get<ScrollPanelWidget>("CONTROLS_LIST");
			headerTemplate = list.Get("HEADER_TEMPLATE");
			rowTemplate = list.Get("ROW_TEMPLATE");
			list.RemoveChildren();

			var gs = Game.Settings.Game;
			var scrollRight = gs.UseClassicMouseStyle ^ gs.UseAlternateScrollButton;

			Header(HeaderMouse);
			Row(MouseSelect, Msg(MouseSelectInput));
			Row(MouseOrder, Msg(gs.UseClassicMouseStyle ? MouseOrderClassic : MouseOrderModern));
			Row(MouseDeselect, Msg(gs.UseClassicMouseStyle ? MouseDeselectClassic : MouseDeselectModern));
			Row(MouseScroll, Msg(scrollRight ? MouseScrollRight : MouseScrollMiddle));
			Row(MouseSameType, Msg(MouseSameTypeInput));
			Row(MousePrimary, Msg(MousePrimaryInput));
			Row(MouseAdd, Msg(MouseAddInput));
			Row(MouseForceFire, Msg(MouseForceFireInput));
			Row(MouseForceMove, Msg(MouseForceMoveInput));

			Header(HeaderUnits);
			HotkeyRow("SelectUnitsByType", NoteTwice);
			HotkeyRow("SelectAllUnits");
			HotkeyRow("AttackMove");
			HotkeyRow("Guard");
			HotkeyRow("Deploy");
			HotkeyRow("Stop");
			HotkeyRow("Scatter");
			HotkeyRow("PxWaypointMode", NoteWaypoint);

			Header(HeaderBase);
			HotkeyRow("CycleBase");
			HotkeyRow("ToLastEvent");
			HotkeyRow("Sell");
			HotkeyRow("Repair");
			HotkeyRow("PowerDown");
			HotkeyRow("PlaceBeacon");

			Header(HeaderSidebar);
			foreach (var tab in new[] { "Building", "Defense", "Infantry", "Vehicle", "Aircraft", "Naval" })
				HotkeyRow("ProductionType" + tab);

			Header(HeaderTeams);
			Row(TeamCreate, KeyRange("ControlGroupCreate", 1, 9));
			Row(TeamSelect, KeyRange("ControlGroupSelect", 1, 9));
			Row(TeamAdd, KeyRange("ControlGroupCombineWith", 1, 9));
			Row(TeamJump, KeyRange("ControlGroupJumpTo", 1, 9));
			Row(BookmarkSave, KeyList("MapBookmarkSave", 4));
			Row(BookmarkJump, KeyList("MapBookmarkRestore", 4));

			widget.Get<ButtonWidget>("CLOSE_BUTTON").OnClick = () =>
			{
				Ui.CloseWindow();
				onExit();
			};
		}

		static string Msg(string key) => FluentProvider.GetMessage(key);

		void Header(string label)
		{
			var header = headerTemplate.Clone();
			var text = Msg(label);
			header.Get<LabelWidget>("LABEL").GetText = () => text;
			list.AddChild(header);
		}

		void Row(string action, string input)
		{
			AddRow(Msg(action), input);
		}

		void AddRow(string action, string input)
		{
			var row = rowTemplate.Clone();
			row.Get<LabelWidget>("ACTION").GetText = () => action;
			row.Get<LabelWidget>("KEY").GetText = () => input;
			list.AddChild(row);
		}

		void HotkeyRow(string name, string note = null)
		{
			var definition = modData.Hotkeys.Definitions.FirstOrDefault(d => d.Name == name);
			if (definition == null)
				return;

			var action = Msg(definition.Description);
			if (note != null)
				action += "  " + Msg(note);

			AddRow(action, KeyText(modData.Hotkeys[name].GetValue()));
		}

		static string KeyText(Hotkey key)
		{
			return key.IsValid() ? key.DisplayString() : Msg(Unbound);
		}

		// "Ctrl + 1-9" for a numbered set that shares its modifiers
		string KeyRange(string prefix, int first, int last)
		{
			var a = modData.Hotkeys[prefix + first.ToString("00", System.Globalization.CultureInfo.InvariantCulture)].GetValue();
			var b = modData.Hotkeys[prefix + last.ToString("00", System.Globalization.CultureInfo.InvariantCulture)].GetValue();
			if (!a.IsValid() || !b.IsValid() || a.Modifiers != b.Modifiers)
				return KeyText(a);

			return a.DisplayString() + "–" + new Hotkey(b.Key, Modifiers.None).DisplayString();
		}

		// "Ctrl + F1 / F2 / F3 / F4"
		string KeyList(string prefix, int count)
		{
			var keys = Enumerable.Range(1, count)
				.Select(i => modData.Hotkeys[prefix + i.ToString("00", System.Globalization.CultureInfo.InvariantCulture)].GetValue())
				.ToList();

			if (keys.Any(k => !k.IsValid() || k.Modifiers != keys[0].Modifiers))
				return KeyText(keys[0]);

			return keys[0].DisplayString() + string.Concat(keys.Skip(1).Select(k => " / " + new Hotkey(k.Key, Modifiers.None).DisplayString()));
		}
	}
}
