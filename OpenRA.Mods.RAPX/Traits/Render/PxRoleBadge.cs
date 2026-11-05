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
using OpenRA.Graphics;
using OpenRA.Mods.Common.Traits;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Traits.Render
{
	public enum PxRole { Rifle, Rocket, Grenade, Flame, Sniper, Pistol, Medic, Mechanic, Engineer, Tesla, Spy, Dog, MachineGun, Robot }

	[Desc("Small role badge (vector glyph on a team-coloured plate) above the unit, so look-alike soldiers can be told",
		"apart: shown when the unit is selected or under the mouse, and above every visible unit while the overlay key",
		"(Alt by default) is held.")]
	public class PxRoleBadgeInfo : TraitInfo, Requires<InteractableInfo>
	{
		[FieldLoader.Require]
		[Desc("The unit's role: Rifle, Rocket, Grenade, Flame, Sniper, Pistol, Medic, Mechanic, Engineer, Tesla, Spy, Dog,",
			"MachineGun, Robot.")]
		public readonly PxRole Role = PxRole.Rifle;

		[Desc("Hold this modifier to show the badges of every visible unit.")]
		public readonly Modifiers OverlayModifier = Modifiers.Alt;

		[Desc("Badge size in screen pixels.")]
		public readonly int Size = 24;

		public override object Create(ActorInitializer init) { return new PxRoleBadge(init.Self, this); }
	}

	public class PxRoleBadge : IRenderAnnotations
	{
		readonly PxRoleBadgeInfo info;
		readonly Interactable interactable;
		Sprite icon;

		public PxRoleBadge(Actor self, PxRoleBadgeInfo info)
		{
			this.info = info;
			interactable = self.Trait<Interactable>();
		}

		// Icons baked from game-icons.net by artsrc/role-badges/make_role_badges.py (sequences/role-badges.yaml)
		Sprite Icon(Actor self)
		{
			if (icon == null)
			{
				var name = info.Role.ToString().ToLowerInvariant();
				var seqs = self.World.Map.Sequences;
				if (seqs.HasSequence("pxroles", name))
					icon = seqs.GetSequence("pxroles", name).GetSprite(0);
			}

			return icon;
		}

		bool IRenderAnnotations.SpatiallyPartitionable => true;

		IEnumerable<IRenderable> IRenderAnnotations.RenderAnnotations(Actor self, WorldRenderer wr)
		{
			if (!self.IsInWorld || self.IsDead || self.World.FogObscures(self))
				yield break;

			var bounds = interactable.DecorationBounds(self, wr);
			var tl = wr.Viewport.WorldToViewPx(new int2(bounds.Left, bounds.Top));
			var br = wr.Viewport.WorldToViewPx(new int2(bounds.Right, bounds.Bottom));
			var mouse = Viewport.LastMousePos;
			var hovered = mouse.X >= tl.X && mouse.X <= br.X && mouse.Y >= tl.Y && mouse.Y <= br.Y;
			var show = Game.GetModifierKeys().HasModifier(info.OverlayModifier) || hovered || self.World.Selection.Contains(self);
			if (!show)
				yield break;

			// Above the health bar, centred on the unit, floating gently
			var bob = MathF.Sin(Game.RunTime / 260f + self.ActorID) * 1.2f;
			var centre = new float2((tl.X + br.X) / 2f, tl.Y - 10 - info.Size / 2f + bob);
			yield return new PxRoleBadgeRenderable(self.CenterPosition, centre, info.Role, info.Size, self.OwnerColor(), Icon(self));
		}
	}

	public class PxRoleBadgeRenderable : IRenderable, IFinalizedRenderable
	{
		static readonly Color Glyph = Color.FromArgb(255, 244, 242, 236);
		static readonly Color Red = Color.FromArgb(255, 230, 50, 45);
		static readonly Color Spark = Color.FromArgb(255, 120, 190, 255);
		static readonly Color Fire = Color.FromArgb(255, 255, 150, 50);

		readonly float2 centre;
		readonly PxRole role;
		readonly int size;
		readonly Color team;
		readonly Sprite icon;

		public PxRoleBadgeRenderable(WPos pos, float2 centre, PxRole role, int size, Color team, Sprite icon)
		{
			Pos = pos;
			this.centre = centre;
			this.role = role;
			this.size = size;
			this.team = team;
			this.icon = icon;
		}

		public WPos Pos { get; }
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxRoleBadgeRenderable(Pos + vec, centre, role, size, team, icon); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }

		static Color Alpha(Color c, float a) { return Color.FromArgb((int)Math.Clamp(c.A * a, 0, 255), c.R, c.G, c.B); }

		public void Render(WorldRenderer wr)
		{
			var cr = Game.Renderer.RgbaColorRenderer;
			var h = size / 2f;
			var c = new float3(centre.X, centre.Y, 0);
			var k = size / 15f; // stroke scale

			// No plate: a soft glow in the owner's colour fading out from the glyph, over a faint dark core for contrast
			for (var i = 5; i >= 1; i--)
			{
				var r = h * (0.55f + 0.17f * i);
				cr.FillEllipse(c - new float3(r, r, 0), c + new float3(r, r, 0), Alpha(team, 0.07f + 0.02f * (5 - i)));
			}

			var core = h * 0.78f;
			cr.FillEllipse(c - new float3(core, core, 0), c + new float3(core, core, 0), Color.FromArgb(70, 0, 0, 0));

			if (icon != null)
			{
				// The baked icon is a 128 px frame with a 96 px glyph: scale so the glyph fills the badge
				var scale = size * 1.25f / icon.Size.X;
				var tl = c - new float3(icon.Size.X * scale / 2, icon.Size.Y * scale / 2, 0);
				Game.Renderer.SpriteRenderer.DrawSprite(icon, null, tl, scale);
				return;
			}

			var s = h * 0.82f; // glyph half size
			void Line(float x0, float y0, float x1, float y1, float w, Color col)
			{
				var a = c + new float3(x0 * s, y0 * s, 0);
				var b = c + new float3(x1 * s, y1 * s, 0);
				w *= k;
				cr.DrawLine(a + new float3(0.8f, 1.2f, 0), b + new float3(0.8f, 1.2f, 0), w + 2.6f, Color.FromArgb(120, 0, 0, 0)); // shadow
				cr.DrawLine(a, b, w + 2f, Color.FromArgb(235, 10, 11, 14));                                                   // outline
				cr.DrawLine(a, b, w, col);                                                                                     // fill
				cr.DrawLine(a - new float3(0, w * 0.22f, 0), b - new float3(0, w * 0.22f, 0), Math.Max(0.8f, w * 0.35f),
					Color.FromArgb(120, 255, 255, 255));                                                                       // highlight
			}

			void Dot(float x, float y, float r, Color col)
			{
				var p = c + new float3(x * s, y * s, 0);
				if (r < 3)
					r *= k * 1.15f; // tiny fixed-size dots grow with the badge; glyph-relative radii already do
				cr.FillEllipse(p - new float3(r + 1.2f, r + 1.2f, 0), p + new float3(r + 1.2f, r + 1.2f, 0), Color.FromArgb(235, 10, 11, 14));
				cr.FillEllipse(p - new float3(r, r, 0), p + new float3(r, r, 0), col);
				cr.FillEllipse(p - new float3(r * 0.45f, r * 0.75f, 0), p + new float3(r * 0.25f, -r * 0.1f, 0), Color.FromArgb(110, 255, 255, 255));
			}

			void Ring(float x, float y, float r, float w, Color col)
			{
				const int N = 18;
				for (var i = 0; i < N; i++)
				{
					var a0 = i * MathF.PI * 2 / N;
					var a1 = (i + 1) * MathF.PI * 2 / N;
					Line(x + r * MathF.Cos(a0), y + r * MathF.Sin(a0), x + r * MathF.Cos(a1), y + r * MathF.Sin(a1), w, col);
				}
			}

			switch (role)
			{
				case PxRole.Rifle:
					Line(-1f, 0.1f, 0.95f, -0.35f, 1.6f, Glyph);  // barrel + body, slanted
					Line(-1f, 0.1f, -0.75f, 0.55f, 1.6f, Glyph);  // stock
					Line(0.05f, -0.1f, 0.15f, 0.45f, 1.5f, Glyph); // magazine
					break;
				case PxRole.Rocket:
					Line(-0.9f, 0.45f, 0.55f, -0.35f, 2.6f, Glyph); // tube
					Line(0.55f, -0.35f, 0.95f, -0.6f, 2.2f, Fire);  // warhead
					Line(-0.9f, 0.45f, -1f, 0.15f, 1.2f, Glyph);    // fins
					Line(-0.9f, 0.45f, -0.6f, 0.65f, 1.2f, Glyph);
					break;
				case PxRole.Grenade:
					Dot(0f, 0.2f, s * 0.62f, Glyph);
					Line(-0.15f, -0.55f, 0.45f, -0.75f, 1.6f, Glyph); // lever
					Ring(0.5f, -0.75f, 0.18f, 1f, Glyph);             // pin
					break;
				case PxRole.Flame:
					Dot(0f, 0.35f, s * 0.55f, Fire);
					Line(-0.4f, 0.2f, 0f, -0.95f, 2.2f, Fire);
					Line(0.4f, 0.2f, 0f, -0.95f, 2.2f, Fire);
					Dot(0f, 0.45f, s * 0.25f, Glyph);
					break;
				case PxRole.Sniper:
					Ring(0f, 0f, 0.75f, 1.3f, Glyph);
					Line(0f, -1f, 0f, -0.3f, 1.3f, Glyph);
					Line(0f, 0.3f, 0f, 1f, 1.3f, Glyph);
					Line(-1f, 0f, -0.3f, 0f, 1.3f, Glyph);
					Line(0.3f, 0f, 1f, 0f, 1.3f, Glyph);
					Dot(0f, 0f, 1.2f, Red);
					break;
				case PxRole.Pistol:
					Line(-0.6f, -0.35f, 0.85f, -0.35f, 2.2f, Glyph); // slide
					Line(-0.5f, -0.3f, -0.7f, 0.75f, 2.2f, Glyph);   // grip
					break;
				case PxRole.Medic:
					Line(0f, -0.85f, 0f, 0.85f, 3f, Red);
					Line(-0.85f, 0f, 0.85f, 0f, 3f, Red);
					break;
				case PxRole.Mechanic:
					Line(-0.75f, 0.75f, 0.35f, -0.35f, 2.2f, Glyph); // handle
					Ring(0.55f, -0.55f, 0.35f, 1.6f, Glyph);         // open jaw
					break;
				case PxRole.Engineer:
					Ring(0f, 0f, 0.55f, 1.6f, Glyph);                // gear
					for (var i = 0; i < 6; i++)
					{
						var a = i * MathF.PI / 3;
						Line(0.55f * MathF.Cos(a), 0.55f * MathF.Sin(a), 0.95f * MathF.Cos(a), 0.95f * MathF.Sin(a), 1.8f, Glyph);
					}

					break;
				case PxRole.Tesla:
					Line(0.25f, -1f, -0.35f, 0.05f, 2f, Spark);
					Line(-0.35f, 0.05f, 0.3f, 0.05f, 2f, Spark);
					Line(0.3f, 0.05f, -0.25f, 1f, 2f, Spark);
					break;
				case PxRole.Spy:
					Line(-0.95f, 0f, 0f, -0.55f, 1.4f, Glyph);
					Line(0f, -0.55f, 0.95f, 0f, 1.4f, Glyph);
					Line(-0.95f, 0f, 0f, 0.55f, 1.4f, Glyph);
					Line(0f, 0.55f, 0.95f, 0f, 1.4f, Glyph);
					Dot(0f, 0f, s * 0.28f, Glyph);
					break;
				case PxRole.Dog:
					Dot(0f, 0.35f, s * 0.4f, Glyph);
					Dot(-0.6f, -0.2f, s * 0.18f, Glyph);
					Dot(-0.2f, -0.6f, s * 0.18f, Glyph);
					Dot(0.2f, -0.6f, s * 0.18f, Glyph);
					Dot(0.6f, -0.2f, s * 0.18f, Glyph);
					break;
				case PxRole.MachineGun:
					Line(-1f, -0.2f, 0.95f, -0.2f, 2f, Glyph);
					Line(-1f, -0.2f, -0.8f, 0.4f, 1.6f, Glyph);
					Line(-0.2f, -0.2f, -0.2f, 0.4f, 1.4f, Glyph);
					Line(0.3f, -0.15f, 0.05f, 0.65f, 1.2f, Glyph); // bipod
					Line(0.3f, -0.15f, 0.55f, 0.65f, 1.2f, Glyph);
					break;
				case PxRole.Robot:
					cr.FillRect(c + new float3(-0.6f * s - 1.2f, -0.5f * s - 1.2f, 0), c + new float3(0.6f * s + 1.2f, 0.6f * s + 1.2f, 0), Color.FromArgb(235, 10, 11, 14));
					cr.FillRect(c + new float3(-0.6f * s, -0.5f * s, 0), c + new float3(0.6f * s, 0.6f * s, 0), Glyph);
					Dot(-0.28f, 0.0f, 1.3f, Spark);
					Dot(0.28f, 0.0f, 1.3f, Spark);
					Line(0f, -0.5f, 0f, -0.95f, 1.2f, Glyph);
					break;
			}
		}
	}
}
