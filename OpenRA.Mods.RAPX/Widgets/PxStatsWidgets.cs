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
using System.Globalization;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Network;
using OpenRA.Primitives;
using OpenRA.Traits;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets
{
	static class PxFlagDraw
	{
		const int Slices = 28;
		static readonly Dictionary<Sprite, Sprite[]> SliceCache = new();

		static Sprite[] SlicesFor(Sprite s)
		{
			if (SliceCache.TryGetValue(s, out var slices))
				return slices;

			var scale = s.Size.X / s.Bounds.Width;
			slices = new Sprite[Slices];
			for (var i = 0; i < Slices; i++)
			{
				var x0 = s.Bounds.X + s.Bounds.Width * i / Slices;
				var x1 = s.Bounds.X + s.Bounds.Width * (i + 1) / Slices;
				slices[i] = new Sprite(s.Sheet, new Rectangle(x0, s.Bounds.Y, x1 - x0, s.Bounds.Height), TextureChannel.RGBA, scale);
			}

			SliceCache[s] = slices;
			return slices;
		}

		/// <summary>Draws a flag that ripples in the wind, pinned to a pole on its left edge.</summary>
		public static void Waving(Sprite s, Rectangle r, float time, float amplitude, float alpha = 1f, bool silhouette = false)
		{
			var slices = SlicesFor(s);
			float Wave(float u) => (float)Math.Sin(time * 2.4f - u * 6.5f) * amplitude * u;
			float Shade(float u) => 1f + 0.26f * (float)Math.Cos(time * 2.4f - u * 6.5f) * Math.Min(1f, u * 3f);

			var x = (float)r.X;
			for (var i = 0; i < slices.Length; i++)
			{
				var u0 = (float)i / slices.Length;
				var u1 = (float)(i + 1) / slices.Length;
				var w = r.Width * slices[i].Bounds.Width / (float)s.Bounds.Width;

				var y0 = Wave(u0);
				var y1 = Wave(u1);

				// Sprites are premultiplied, so the tint carries the alpha too
				var shade = silhouette ? 0f : Shade((u0 + u1) / 2) * alpha;
				var tint = new float3(shade, shade, shade);
				Game.Renderer.RgbaSpriteRenderer.DrawSprite(slices[i],
					new float3(x, r.Y + y0, 0), new float3(x + w, r.Y + y1, 0),
					new float3(x + w, r.Bottom + y1, 0), new float3(x, r.Bottom + y0, 0), tint, alpha);
				x += w;
			}
		}
	}

	/// <summary>
	/// The whole player row of the game info stats panel: rank, waving flag on a pole, name, role and nation,
	/// a status chip and the score. The player is found from the stock NAME label's colour.
	/// Put the row's mute/kick buttons inside this widget so they draw on top of it.
	/// </summary>
	public class PxStatsCardWidget : Widget
	{
		public readonly string NameFont = "PXDisplayLarge";
		public readonly string MetaFont = "PXLabel";
		public readonly string TagFont = "PXSidebarSmall";
		public readonly string ScoreFont = "PXDigits";
		public readonly string RankFont = "PXDisplay";
		public readonly int ScoreRight = 24;
		public readonly int ChipRight = 236;

		readonly World world;
		Player player;
		int rank;
		readonly CachedTransform<int, string> scoreText = new(s => s.ToString("N0", NumberFormatInfo.CurrentInfo));

		[ObjectCreator.UseCtor]
		public PxStatsCardWidget(World world) { this.world = world; }

		protected PxStatsCardWidget(PxStatsCardWidget other)
			: base(other)
		{
			world = other.world;
			NameFont = other.NameFont;
			MetaFont = other.MetaFont;
			TagFont = other.TagFont;
			ScoreFont = other.ScoreFont;
			RankFont = other.RankFont;
			ScoreRight = other.ScoreRight;
			ChipRight = other.ChipRight;
		}

		public override Widget Clone() { return new PxStatsCardWidget(this); }

		Player FindPlayer()
		{
			var name = Parent.GetOrNull<LabelWidget>("NAME");
			if (name == null)
				return null;

			var color = name.GetColor();
			return world.Players.FirstOrDefault(p => p.Playable && !p.NonCombatant && p.Color == color);
		}

		int FindRank()
		{
			var cards = Parent.Parent.Children.Select(c => c.GetOrNull<PxStatsCardWidget>("CARD")).Where(c => c != null).ToList();
			return cards.IndexOf(this) + 1;
		}

		static Color Brighten(Color c, float k)
		{
			return Color.FromArgb(c.A, (int)(c.R + (255 - c.R) * k), (int)(c.G + (255 - c.G) * k), (int)(c.B + (255 - c.B) * k));
		}

		public override void Draw()
		{
			player ??= FindPlayer();
			if (player == null)
				return;

			if (rank == 0)
				rank = FindRank();

			var rb = RenderBounds;
			var time = Game.RunTime / 1000f + rank * 1.7f;
			var local = world.LocalPlayer;
			var isLocal = local == player;
			var lost = player.WinState == WinState.Lost;
			var won = player.WinState == WinState.Won;
			var client = world.LobbyInfo.ClientWithIndex(player.ClientIndex);
			var gone = client != null && client.State == Session.ClientState.Disconnected;
			var color = lost || gone ? Color.FromArgb(110, 110, 118) : player.Color;
			var nameColor = Brighten(color, 0.5f);

			// Which flag this viewer may see: enemies show their disguise until the game is decided
			var showTrue = local == null || local.RelationshipWith(player) == PlayerRelationship.Ally || local.WinState != WinState.Undefined;
			var faction = showTrue ? player.Faction : player.DisplayFaction;
			var flag = ChromeProvider.TryGetImage("flags-large", faction.InternalName) ?? ChromeProvider.TryGetImage("flags", faction.InternalName);

			// Card body
			var border = isLocal ? PxDraw.Accent : Color.FromArgb(58, 59, 67);
			WidgetUtils.FillRectWithColor(rb, border);
			var inner = rb.InflateBy(-1, -1, -1, -1);
			WidgetUtils.FillRectWithColor(inner, Color.FromArgb(14, 14, 18), Color.FromArgb(22, 22, 27), Color.FromArgb(17, 17, 21), Color.FromArgb(10, 10, 13));

			// Giant flag watermark behind the score side, faded into the card
			if (flag != null)
			{
				var wm = new Rectangle(inner.Right - inner.Height * 3, inner.Y - 8, inner.Height * 3 + 8, inner.Height + 16);
				Game.Renderer.EnableScissor(inner);
				PxFlagDraw.Waving(flag, wm, time * 0.6f, 3, lost ? 0.06f : 0.14f);
				Game.Renderer.DisableScissor();
				var bg = Color.FromArgb(17, 17, 21);
				WidgetUtils.FillRectWithColor(new Rectangle(wm.X, inner.Y, wm.Width / 2, inner.Height),
					bg, Color.FromArgb(0, bg), Color.FromArgb(0, bg), bg);
			}

			// Player colour wash and stripe
			WidgetUtils.FillRectWithColor(new Rectangle(inner.X, inner.Y, inner.Width * 3 / 5, inner.Height),
				Color.FromArgb(70, color), Color.FromArgb(0, color), Color.FromArgb(0, color), Color.FromArgb(70, color));
			WidgetUtils.FillRectWithColor(new Rectangle(inner.X, inner.Y, 10, inner.Height), Color.FromArgb(60, color));
			WidgetUtils.FillRectWithColor(new Rectangle(inner.X, inner.Y, 5, inner.Height), color);

			// Top sheen
			WidgetUtils.FillRectWithColor(new Rectangle(inner.X, inner.Y, inner.Width, 1), Color.FromArgb(40, 255, 255, 255));

			// Rank
			var rankFont = Game.Renderer.Fonts[RankFont];
			var rankText = rank.ToString("00", NumberFormatInfo.InvariantInfo);
			var rankSize = rankFont.Measure(rankText);
			rankFont.DrawText(rankText, new float2(rb.X + 36 - rankSize.X / 2, rb.Y + (rb.Height - rankSize.Y) / 2),
				rank == 1 && !lost ? Color.FromArgb(255, 205, 90) : Color.FromArgb(92, 93, 102));

			// Flag pole + waving flag
			var flagRect = new Rectangle(rb.X + 76, rb.Y + (rb.Height - 60) / 2, 90, 60);
			var poleX = flagRect.X - 4;
			WidgetUtils.FillRectWithColor(new Rectangle(poleX, flagRect.Y - 6, 3, flagRect.Height + 16),
				Color.FromArgb(230, 230, 236), Color.FromArgb(120, 120, 130), Color.FromArgb(70, 70, 78), Color.FromArgb(150, 150, 160));
			WidgetUtils.FillEllipseWithColor(new Rectangle(poleX - 2, flagRect.Y - 11, 7, 7), Color.FromArgb(255, 205, 90));
			if (flag != null)
			{
				// Cast shadow, then the cloth
				var shadow = new Rectangle(flagRect.X + 4, flagRect.Y + 5, flagRect.Width, flagRect.Height);
				PxFlagDraw.Waving(flag, shadow, time - 0.15f, 3.5f, 0.45f, true);
				WidgetUtils.FillRectWithColor(new Rectangle(shadow.X + 2, shadow.Bottom - 1, shadow.Width - 6, 4), Color.FromArgb(70, 0, 0, 0));
				PxFlagDraw.Waving(flag, flagRect, time, 3.5f, lost ? 0.45f : 1f);
			}

			// Name
			var textX = flagRect.Right + 24;
			var nameFont = Game.Renderer.Fonts[NameFont];
			var maxName = rb.Right - ChipRight - textX - 16;
			var name = WidgetUtils.TruncateText(player.ResolvedPlayerName, maxName, nameFont);
			nameFont.DrawTextWithShadow(name, new float2(textX, rb.Y + 14), nameColor, Color.FromArgb(160, 0, 0, 0), 2);

			// Role tag + nation line
			string tag;
			Color tagColor;
			if (player.IsBot)
				(tag, tagColor) = ("AI COMMANDER", PxDraw.Muted);
			else if (isLocal)
				(tag, tagColor) = ("YOU", PxDraw.AccentBright);
			else
				(tag, tagColor) = ("COMMANDER", PxDraw.Muted);

			var tagFont = Game.Renderer.Fonts[TagFont];
			var tagY = rb.Bottom - 30;
			var avatar = ChromeProvider.TryGetImage("px-lobby-icons", player.IsBot ? "avatar-bot" : "avatar-human");
			var tx = textX;
			if (avatar != null)
			{
				WidgetUtils.DrawSprite(avatar, new float2(tx, tagY - 4), new float2(18, 18));
				tx += 24;
			}

			var tagSize = tagFont.Measure(tag);
			var tagBox = new Rectangle(tx - 1, tagY - 3, tagSize.X + 14, 18);
			WidgetUtils.FillRectWithColor(tagBox, Color.FromArgb(isLocal ? 60 : 40, tagColor));
			tagFont.DrawText(tag, new float2(tagBox.X + 7, tagY), tagColor);

			var metaFont = Game.Renderer.Fonts[MetaFont];
			var nation = FluentProvider.GetMessage(faction.Name).ToUpperInvariant();
			var side = faction.Side switch
			{
				"Union" => "THE UNION",
				"Vanguard" => "THE VANGUARD",
				_ => null
			};

			var meta = side != null ? $"{nation}  ·  {side}" : nation;
			metaFont.DrawText(meta, new float2(tagBox.Right + 12, tagY - 4), Color.FromArgb(200, 201, 208));

			// Status chip
			string status;
			Color statusColor;
			if (gone)
				(status, statusColor) = ("DISCONNECTED", Color.FromArgb(138, 139, 147));
			else if (won)
				(status, statusColor) = ("VICTORIOUS", Color.FromArgb(93, 255, 122));
			else if (lost)
				(status, statusColor) = ("DEFEATED", Color.FromArgb(255, 77, 77));
			else
				(status, statusColor) = ("IN COMBAT", Color.FromArgb(255, 190, 70));

			var chip = new Rectangle(rb.Right - ChipRight, rb.Y + (rb.Height - 26) / 2, 128, 26);
			WidgetUtils.FillRectWithColor(chip, Color.FromArgb(110, statusColor));
			WidgetUtils.FillRectWithColor(chip.InflateBy(-1, -1, -1, -1), Color.FromArgb(235, 16, 16, 20));
			WidgetUtils.FillRectWithColor(chip.InflateBy(-1, -1, -1, -1), Color.FromArgb(30, statusColor));
			var pulse = !won && !lost && !gone ? 0.55f + 0.45f * (float)Math.Sin(Game.RunTime / 260f) : 1f;
			var dot = new Rectangle(chip.X + 11, chip.Y + 9, 8, 8);
			WidgetUtils.FillEllipseWithColor(dot.InflateBy(3, 3, 3, 3), Color.FromArgb((int)(60 * pulse), statusColor));
			WidgetUtils.FillEllipseWithColor(dot, Color.FromArgb((int)(255 * pulse), statusColor));
			var statusSize = tagFont.Measure(status);
			tagFont.DrawText(status, new float2(chip.X + 27 + (chip.Width - 31 - statusSize.X) / 2, chip.Y + (chip.Height - statusSize.Y) / 2), statusColor);

			// Score
			var stats = player.PlayerActor.TraitOrDefault<PlayerStatistics>();
			var score = scoreText.Update(stats?.Experience ?? 0);
			var scoreFont = Game.Renderer.Fonts[ScoreFont];
			var scoreSize = scoreFont.Measure(score);
			var scoreX = rb.Right - ScoreRight - scoreSize.X;
			tagFont.DrawText("SCORE", new float2(rb.Right - ScoreRight - tagFont.Measure("SCORE").X, rb.Y + 14), PxDraw.Dim);
			scoreFont.DrawTextWithShadow(score, new float2(scoreX, rb.Y + 32), lost ? PxDraw.Dim : Color.White, Color.FromArgb(160, 0, 0, 0), 2);
		}
	}

	/// <summary>Backdrop for the mission status block: framed band with a status light for the local player.</summary>
	public class PxMissionBannerWidget : Widget
	{
		readonly World world;

		[ObjectCreator.UseCtor]
		public PxMissionBannerWidget(World world) { this.world = world; IgnoreMouseOver = true; }

		protected PxMissionBannerWidget(PxMissionBannerWidget other)
			: base(other)
		{
			world = other.world;
			IgnoreMouseOver = true;
		}

		public override Widget Clone() { return new PxMissionBannerWidget(this); }

		public override bool HandleMouseInput(MouseInput mi) { return false; }

		public override void Draw()
		{
			var rb = RenderBounds;
			var state = world.LocalPlayer?.WinState ?? WinState.Undefined;
			var c = state == WinState.Won ? Color.FromArgb(93, 255, 122) : state == WinState.Lost ? Color.FromArgb(255, 77, 77) : PxDraw.Accent;

			WidgetUtils.FillRectWithColor(rb, Color.FromArgb(58, 59, 67));
			var inner = rb.InflateBy(-1, -1, -1, -1);
			WidgetUtils.FillRectWithColor(inner, Color.FromArgb(50, c), Color.FromArgb(14, 14, 18), Color.FromArgb(14, 14, 18), Color.FromArgb(30, c));
			WidgetUtils.FillRectWithColor(new Rectangle(inner.X, inner.Y, 5, inner.Height), c);

			// Hazard ticks on the right end
			Game.Renderer.EnableScissor(inner);
			for (var x = inner.Right - 150; x < inner.Right + 20; x += 16)
				Game.Renderer.RgbaColorRenderer.FillRect(
					new float3(x, inner.Bottom, 0), new float3(x + 7, inner.Bottom, 0),
					new float3(x + 7 + inner.Height, inner.Y, 0), new float3(x + inner.Height, inner.Y, 0), Color.FromArgb(18, c));
			Game.Renderer.DisableScissor();
		}
	}
}
