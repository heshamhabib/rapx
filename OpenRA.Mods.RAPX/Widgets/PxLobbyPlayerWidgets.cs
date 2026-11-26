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

using OpenRA.Graphics;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Network;
using OpenRA.Primitives;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	/// <summary>
	/// Decorates a lobby player row (place it first in the row so it draws underneath): a stripe and tint in
	/// the player's colour, an avatar tile (person or robot), a crown for the host, a role tag under the name
	/// and a READY pill for rows that only show the ready state. The client is found by the row's name.
	/// </summary>
	public class PxPlayerRowDecorWidget : Widget
	{
		public readonly int2 AvatarOffset = new(16, 12);
		public readonly int TagX = 72;
		public readonly int TagY = 38;
		public readonly int StatusX = 806;
		public readonly int StatusWidth = 104;
		public readonly string TagFont = "PXSidebarSmall";

		public PxPlayerRowDecorWidget() { IgnoreMouseOver = true; }

		protected PxPlayerRowDecorWidget(PxPlayerRowDecorWidget other)
			: base(other)
		{
			AvatarOffset = other.AvatarOffset;
			TagX = other.TagX;
			TagY = other.TagY;
			StatusX = other.StatusX;
			StatusWidth = other.StatusWidth;
			TagFont = other.TagFont;
			IgnoreMouseOver = true;
		}

		public override Widget Clone() { return new PxPlayerRowDecorWidget(this); }

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		string RowName()
		{
			foreach (var id in new[] { "NAME", "SLOT_OPTIONS", "PLAYER_ACTION" })
			{
				var w = Parent.GetOrNull(id);
				if (w == null || !w.IsVisible())
					continue;

				switch (w)
				{
					case TextFieldWidget tf: return tf.Text;
					case LabelWidget l: return l.GetText();
					case ButtonWidget b: return b.GetText();
				}
			}

			return null;
		}

		Session.Client FindClient()
		{
			var lobby = PxLobbyState.OrderManager?.LobbyInfo;
			if (lobby == null)
				return null;

			var name = RowName();
			var byName = name == null ? null : lobby.Clients.FirstOrDefault(c => c.Name == name);
			if (byName != null)
				return byName;

			// Bot names are translated for display, so fall back to the row's player colour
			var colorBlock = Parent.GetOrNull<ColorBlockWidget>("COLORBLOCK");
			if (colorBlock == null)
				return null;

			var color = colorBlock.GetColor();
			return lobby.Clients.FirstOrDefault(c => c.Slot != null && c.Color == color);
		}

		public override void Draw()
		{
			var rb = Parent.RenderBounds;
			var client = FindClient();
			var color = client?.Color ?? Color.FromArgb(70, 71, 80);

			// Player colour: soft tint fading in from the left and a glowing stripe
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X + 2, rb.Y + 2, rb.Width / 2, rb.Height - 4),
				Color.FromArgb(56, color), Color.FromArgb(0, color), Color.FromArgb(0, color), Color.FromArgb(56, color));
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X + 1, rb.Y + 1, 6, rb.Height - 2), Color.FromArgb(70, color));
			WidgetUtils.FillRectWithColor(new Rectangle(rb.X + 1, rb.Y + 1, 4, rb.Height - 2), color);

			if (client == null)
				return;

			// Avatar
			var tile = new Rectangle(rb.X + AvatarOffset.X, rb.Y + AvatarOffset.Y, 44, 44);
			WidgetUtils.FillRectWithColor(tile, Color.FromArgb(52, 53, 60));
			WidgetUtils.FillRectWithColor(tile.InflateBy(-1, -1, -1, -1), Color.FromArgb(12, 12, 15));
			var avatar = ChromeProvider.TryGetImage("px-lobby-icons", client.Bot != null ? "avatar-bot" : "avatar-human");
			if (avatar != null)
				WidgetUtils.DrawSprite(avatar, new float2(tile.X + 10, tile.Y + 10));

			var local = PxLobbyState.OrderManager.LocalClient;
			if (client.IsAdmin)
			{
				var crown = ChromeProvider.TryGetImage("px-lobby-icons", "crown");
				if (crown != null)
					WidgetUtils.DrawSprite(crown, new float2(tile.X + 14, tile.Y - 7));
			}

			string tag;
			Color tagColor;
			if (client.Bot != null)
				(tag, tagColor) = ("AI COMMANDER", PxDraw.Muted);
			else if (local != null && client.Index == local.Index)
				(tag, tagColor) = (client.IsAdmin ? "HOST · YOU" : "YOU", PxDraw.AccentBright);
			else
				(tag, tagColor) = (client.IsAdmin ? "HOST" : "COMMANDER", PxDraw.Muted);

			Game.Renderer.Fonts[TagFont].DrawText(tag, new float2(rb.X + TagX, rb.Y + TagY), tagColor);

			// Read-only ready state (the local player's own row has a toggle instead)
			var statusImage = Parent.GetOrNull("STATUS_IMAGE");
			var checkbox = Parent.GetOrNull("STATUS_CHECKBOX");
			if (checkbox != null && checkbox.IsVisible())
				return;

			var ready = statusImage != null && statusImage.IsVisible();
			PxReadyPillWidget.DrawPill(new Rectangle(rb.X + StatusX, rb.Y + (rb.Height - 42) / 2, StatusWidth, 42), ready, false, false);
		}
	}

	/// <summary>The lobby ready checkbox drawn as a READY / NOT READY pill.</summary>
	public class PxReadyPillWidget : CheckboxWidget
	{
		[ObjectCreator.UseCtor]
		public PxReadyPillWidget(ModData modData)
			: base(modData) { }

		protected PxReadyPillWidget(PxReadyPillWidget other)
			: base(other) { }

		public override Widget Clone() { return new PxReadyPillWidget(this); }

		public override void Draw()
		{
			DrawPill(RenderBounds, IsChecked(), Ui.MouseOverWidget == this, IsDisabled());
		}

		public static void DrawPill(Rectangle r, bool ready, bool hover, bool disabled)
		{
			var border = ready ? Color.FromArgb(93, 255, 122) : hover ? PxDraw.AccentBright : Color.FromArgb(74, 75, 82);
			var fill = ready ? Color.FromArgb(28, 70, 38) : Color.FromArgb(20, 21, 25);
			WidgetUtils.FillRectWithColor(r, border);
			WidgetUtils.FillRectWithColor(r.InflateBy(-1, -1, -1, -1), fill);

			// Narrow pill (the lobby's STATUS column): the icon alone, centred; its tooltip says what it means
			if (r.Width < 80)
			{
				var only = ChromeProvider.TryGetImage("px-lobby-icons", ready ? "tick-ready" : "waiting");
				if (only != null)
					WidgetUtils.DrawSprite(only, new float2(r.X + (r.Width - only.Size.X) / 2, r.Y + (r.Height - only.Size.Y) / 2));

				return;
			}

			var font = Game.Renderer.Fonts["PXSidebarSmall"];
			var text = ready ? "READY" : "NOT READY";
			var size = font.Measure(text);
			var x = r.X + (r.Width - size.X + 18) / 2;
			var y = r.Y + (r.Height - size.Y) / 2;
			var color = disabled ? PxDraw.Dim : ready ? Color.FromArgb(143, 255, 159) : Color.FromArgb(185, 186, 194);
			font.DrawText(text, new float2(x, y), color);

			// Status icon to the left of the text
			var icon = ChromeProvider.TryGetImage("px-lobby-icons", ready ? "tick-ready" : "waiting");
			if (icon != null)
				WidgetUtils.DrawSprite(icon, new float2(x - 8 - icon.Size.X, r.Y + (r.Height - icon.Size.Y) / 2));
		}
	}

	/// <summary>Lobby state shared with widgets that the engine creates without logic arguments.</summary>
	public static class PxLobbyState
	{
		public static OrderManager OrderManager;
	}

	/// <summary>
	/// A container that never draws or takes input, whatever the logic sets IsVisible to. Used for lobby rows
	/// that LobbyLogic needs to find but this mod does not show, such as the Spectate row.
	/// </summary>
	public class PxHiddenWidget : Widget
	{
		public PxHiddenWidget() { }

		protected PxHiddenWidget(PxHiddenWidget other)
			: base(other) { }

		public override Widget Clone() { return new PxHiddenWidget(this); }

		public override void DrawOuter() { }

		public override bool EventBoundsContains(int2 location) { return false; }
	}
}
