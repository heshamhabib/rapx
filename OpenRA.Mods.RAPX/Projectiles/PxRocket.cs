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
using OpenRA.Effects;
using OpenRA.GameRules;
using OpenRA.Graphics;
using OpenRA.Mods.RAPX.Effects;
using OpenRA.Mods.RAPX.Graphics;
using OpenRA.Primitives;
using OpenRA.Support;
using OpenRA.Traits;

namespace OpenRA.Mods.RAPX.Projectiles
{
	/// <summary>How a PxRocket flies to its target.</summary>
	public enum PxRocketProfile
	{
		/// <summary>A flat arc (Arc) from the launcher to the target.</summary>
		Arc,

		/// <summary>Straight up out of a vertical launcher, then bending over onto the target (Climb sets how high).</summary>
		Vertical,

		/// <summary>Up out of a tilted launcher, high over the first third of the way, then diving onto the target.</summary>
		Loft,
	}

	[Desc("High-definition rocket: a drawn rocket body with a white-hot exhaust flame flying an arc to its target, a launch",
		"blast, and a thick HD smoke trail (pxfx particles) that billows, drifts and lingers after the impact.")]
	public class PxRocketInfo : IProjectileInfo
	{
		[Desc("Flight speed per tick.")]
		public readonly WDist Speed = new(220);

		[Desc("Draw this image's sequence (32 facings) as the missile instead of the drawn rocket body; the exhaust flame",
			"and smoke trail stay. Used by the jet weapons (rendered missiles, artsrc/jets/render_missiles.py).")]
		public readonly string Image = null;

		public readonly string Sequence = "idle";

		[Desc("Sequence of Image drawn while climbing steeply (nose up), e.g. a rocket just off its launch rail.",
			"Empty = always use Sequence.")]
		public readonly string ClimbSequence = null;

		[Desc("Sequence of Image drawn while diving steeply (nose down) onto the target. Empty = always use Sequence.")]
		public readonly string DiveSequence = null;

		[Desc("Slope (height gained per distance flown) beyond which ClimbSequence / DiveSequence is used.")]
		public readonly float AttitudeSlope = 0.36f;

		[Desc("0 = constant speed; up to 1 = leaves the launcher slowly and speeds up (a heavy rocket off its rail).")]
		public readonly float LaunchEase = 0f;

		[Desc("Height of the flight arc, as a fraction of the distance.")]
		public readonly float Arc = 0.12f;

		[Desc("Follow the targeted actor while flying.")]
		public readonly bool TrackTarget = true;

		[Desc("The maximum/constant/incremental inaccuracy used in conjunction with the InaccuracyType property.",
			"A missed rocket keeps its offset while tracking, so a salvo spreads over the target area.")]
		public readonly WDist Inaccuracy = WDist.Zero;

		[Desc("Controls the way inaccuracy is calculated. Possible values are " +
			"'Maximum' - scale from 0 to max with range, " +
			"'PerCellIncrement' - scale from 0 with range, " +
			"'Absolute' - use set value regardless of range.")]
		public readonly OpenRA.Mods.Common.InaccuracyType InaccuracyType = OpenRA.Mods.Common.InaccuracyType.Maximum;

		[Desc("Length of the rocket body.")]
		public readonly WDist Length = new(150);

		[Desc("Width of the rocket body.")]
		public readonly WDist Width = new(36);

		[Desc("Rocket body colour.")]
		public readonly Color BodyColor = Color.FromArgb(255, 70, 76, 82);

		[Desc("Nose / band colour.")]
		public readonly Color NoseColor = Color.FromArgb(255, 220, 220, 210);

		[Desc("Exhaust flame colour.")]
		public readonly Color FlameColor = Color.FromArgb(255, 255, 170, 60);

		[Desc("Trail and launch smoke colour (a white-hot solid motor gives pale smoke, a thermobaric or old motor darker).")]
		public readonly Color SmokeColor = Color.FromArgb(255, 217, 217, 217);

		[Desc("Size of the trail smoke puffs, as a multiple of the default.")]
		public readonly float TrailSize = 1f;

		[Desc("Length and size of the exhaust flame, as a multiple of the default.")]
		public readonly float FlameSize = 1f;

		[Desc("Strength of the rolling orange fire plume behind the nozzle (0 = none), lighting the smoke warm like a",
			"rocket motor's exhaust. Each rocket varies it a little, along with how warm and twisted its trail is.")]
		public readonly float FirePlume = 1f;

		[Desc("Smoke puffs emitted per tick of flight.")]
		public readonly int TrailDensity = 2;

		[Desc("How long trail smoke lingers, in ticks.")]
		public readonly int TrailLife = 45;

		[Desc("Smoke puffs in the launch blast.")]
		public readonly int LaunchPuffs = 10;

		[Desc("Filmed launch blast on the ground under the launcher (sequence of image pxvideofx,",
			"artsrc/fx/make_video_fx.py). Plays once per salvo: rockets the same launcher fires within LaunchVideoGap",
			"ticks of it share one. Not for cold or water launches.")]
		public readonly string LaunchVideo = null;

		[Desc("Ticks after a filmed launch blast in which the same launcher's next rockets play none (one per salvo).")]
		public readonly int LaunchVideoGap = 90;

		[Desc("Size of the filmed launch blast.")]
		public readonly float LaunchVideoScale = 1f;

		[Desc("Launched from under water (missile submarine): the launch blast is a burst of foam, spray and steam.")]
		public readonly bool WaterLaunch = false;

		[Desc("What kind of threat air defence sees (PxInterceptor Chances): Rocket (artillery rockets, guided bombs),",
			"Cruise, Ballistic, Hypersonic, Drone; any other name (e.g. AirToAir) is ignored by air defence.")]
		public readonly string ThreatType = "Rocket";

		[Desc("Point defence (PxPointDefense) and air defence (PxInterceptor) may shoot it down. False for artillery",
			"shells, which only borrow the HD smoke trail.")]
		public readonly bool Interceptable = true;

		[Desc("Equivalent to sequence ZOffset. Controls Z sorting.")]
		public readonly int ZOffset = 1024;

		[Desc("Flight path: Arc (default), Vertical (vertical launch that bends over onto the target) or Loft (climbs out",
			"of a tilted launcher and dives onto the target).")]
		public readonly PxRocketProfile Profile = PxRocketProfile.Arc;

		[Desc("Vertical / Loft: height of the climb, as a fraction of the distance.")]
		public readonly float Climb = 0.5f;

		[Desc("Vertical / Loft: the climb is at least this high.")]
		public readonly WDist MinClimb = new(1024);

		[Desc("Cold launch: for this many ticks the missile is thrown out of its canister by gas, motor off (a white gas",
			"cloud, no flame), then the motor ignites with a flash. Pair with LaunchEase.")]
		public readonly int ColdLaunch = 0;

		[Desc("Corkscrew: the missile spirals around its flight line this far (a short-range missile rolling as it",
			"flies), most in the middle of the flight.")]
		public readonly WDist Corkscrew = WDist.Zero;

		[Desc("Ticks per turn of the corkscrew.")]
		public readonly int CorkscrewPeriod = 10;

		[Desc("Dual-pulse motor: the first pulse burns out at this tick, the missile coasts (no flame, a thin trail) for",
			"CoastTicks, then the second pulse lights with a flash. 0 = one long burn.")]
		public readonly int CoastStart = 0;

		[Desc("Ticks the missile coasts between the two motor pulses.")]
		public readonly int CoastTicks = 0;

		[Desc("Hit-to-kill seeker: over the last this many ticks the attitude control motors fire, a ring of tiny",
			"sideways jets around the nose.")]
		public readonly int DivertTicks = 0;

		[Desc("Percent chance that the seeker ignores a jet's flares (PxFlareDispenser): radar seekers high, old IR low.")]
		public readonly int FlareResistance = 0;

		[Desc("Size of the tail fins (0 = none) of the drawn body.")]
		public readonly float Fins = 1f;

		[Desc("Small steering fins behind the nose of the drawn body.")]
		public readonly bool Canards = false;

		[Desc("Colour of a band around the drawn body (transparent = none).")]
		public readonly Color BandColor = Color.Transparent;

		[Desc("Length of the drawn nose cone, as a fraction of the body.")]
		public readonly float NoseLength = 0.22f;

		[Desc("Long-exposure streak: the path flown stays drawn as a thin glowing line for this many ticks, fading from",
			"the oldest end (the interceptor trails of a night-time Iron Dome photo). 0 = none.")]
		public readonly int StreakLife = 0;

		[Desc("Colour of the streak's glow; its core is drawn white-hot.")]
		public readonly Color StreakColor = Color.FromArgb(255, 255, 196, 110);

		[Desc("Width of the streak's core.")]
		public readonly WDist StreakWidth = new(14);

		[Desc("Interception burst size (when air defence shoots this down), as a multiple of the default.")]
		public readonly float InterceptBurst = 1f;

		[Desc("No motor: a free-falling bomb or dispenser (no flame, no fire plume, no launch flash, only a wisp of air).")]
		public readonly bool Unpowered = false;

		[Desc("Draw the rocket body (false: only the flame and glow show, e.g. a burning bomblet).")]
		public readonly bool DrawBody = true;

		[Desc("Cluster dispenser: the warheads go off this high above the aim point (the dispenser opens there, so a",
			"FireCluster warhead throws its bomblets down from the air). The opening shows as a pop, a puff and the two",
			"shell halves tumbling away. 0 = impacts on the target.")]
		public readonly WDist BurstHeight = WDist.Zero;

		[Desc("Glittering sparks shed per tick that hang and fall slowly behind it (burning submunitions).")]
		public readonly int Sparkle = 0;

		public IProjectile Create(ProjectileArgs args) { return new PxRocket(this, args); }
	}

	/// <summary>One shared particle system for every rocket's trail, launch blast and interception burst, drawn high in
	/// the sky above the battlefield as a single emitter: a salvo of forty rockets costs the renderer one or two batches
	/// instead of a few per rocket, and an exploded rocket's smoke lives on here, so the projectile itself can go at
	/// once. Lives as an effect while anything is in the air or smoking, then removes itself.</summary>
	public sealed class PxTrailLayer : IEffect
	{
		static PxTrailLayer current;

		public static PxTrailLayer Get(World world)
		{
			if (current == null || current.world != world || current.removed)
			{
				var layer = new PxTrailLayer(world);
				current = layer;
				world.AddFrameEndTask(w => w.Add(layer));
			}

			return current;
		}

		public readonly PxParticles Particles;

		/// <summary>Rockets compute their puff offsets from this: past the map's bottom edge, so the whole layer
		/// sorts over every ground sprite — trail smoke is sky stuff.</summary>
		public readonly WPos Anchor;

		readonly World world;
		bool removed;
		int idle;

		PxTrailLayer(World world)
		{
			this.world = world;
			Particles = new PxParticles(world) { Max = PxParticles.GlobalBudget };
			var b = world.Map.Bounds;
			Anchor = new WPos((b.Left + b.Right) * 512, b.Bottom * 1024 + 2048, 0);
		}

		public void Tick(World world)
		{
			Particles.Update(1);
			if (Particles.Items.Count > 0)
				idle = 0;
			else if (++idle > 25)
			{
				removed = true;
				world.AddFrameEndTask(w => w.Remove(this));
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			return Particles.Render(Anchor, 2048);
		}
	}

	/// <summary>Long-exposure streaks (PxRocketInfo.StreakLife) of every rocket, drawn as one effect sorted over the
	/// battlefield like PxTrailLayer: a streak outlives its rocket and fades from its oldest point.</summary>
	public sealed class PxStreakLayer : IEffect
	{
		public sealed class Streak
		{
			public readonly List<WPos> Points = new();
			public readonly List<int> Born = new();
			public PxRocketInfo Info;
			public bool Done;
		}

		static PxStreakLayer current;

		public static PxStreakLayer Get(World world)
		{
			if (current == null || current.world != world || current.removed)
			{
				var layer = new PxStreakLayer(world);
				current = layer;
				world.AddFrameEndTask(w => w.Add(layer));
			}

			return current;
		}

		readonly World world;
		readonly List<Streak> streaks = new();
		readonly WPos anchor;
		bool removed;
		int idle;

		public int Now { get; private set; }

		PxStreakLayer(World world)
		{
			this.world = world;
			var b = world.Map.Bounds;
			anchor = new WPos((b.Left + b.Right) * 512, b.Bottom * 1024 + 2048, 0);
		}

		public Streak Start(PxRocketInfo info)
		{
			var s = new Streak { Info = info };
			streaks.Add(s);
			return s;
		}

		public void Tick(World world)
		{
			Now++;
			foreach (var s in streaks)
			{
				// Drop the points that have faded out (oldest first)
				var n = 0;
				while (n < s.Born.Count && Now - s.Born[n] >= s.Info.StreakLife)
					n++;

				if (n > 0)
				{
					s.Points.RemoveRange(0, n);
					s.Born.RemoveRange(0, n);
				}
			}

			streaks.RemoveAll(s => s.Done && s.Points.Count < 2);
			if (streaks.Count > 0)
				idle = 0;
			else if (++idle > 25)
			{
				removed = true;
				world.AddFrameEndTask(w => w.Remove(this));
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			if (streaks.Count > 0)
				yield return new PxStreakRenderable(this, anchor);
		}

		/// <summary>Draws every streak: a wide faint glow, a narrower bright glow and a white-hot core, each segment
		/// fading with its age and thinning towards the old end.</summary>
		public void Draw(WorldRenderer wr)
		{
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			foreach (var s in streaks)
			{
				if (s.Points.Count < 2)
					continue;

				var info = s.Info;
				var core = Math.Max(1f, wr.ScreenVector(new WVec(info.StreakWidth, WDist.Zero, WDist.Zero))[0]);
				var glow = info.StreakColor;
				var prev = wr.Screen3DPosition(s.Points[0]);
				for (var i = 1; i < s.Points.Count; i++)
				{
					var here = wr.Screen3DPosition(s.Points[i]);
					var fresh = 1f - (float)(Now - s.Born[i]) / info.StreakLife;
					if (fresh > 0)
					{
						// Ease out: stays bright most of its life, then dies away quickly
						var a = fresh * fresh * (3 - 2 * fresh);
						var w = core * (0.45f + 0.55f * fresh);
						cr.DrawLine(prev, here, w * 5f, Color.FromArgb((int)(40 * a), glow.R, glow.G, glow.B));
						cr.DrawLine(prev, here, w * 2.2f, Color.FromArgb((int)(120 * a), glow.R, glow.G, glow.B));
						cr.DrawLine(prev, here, w, Color.FromArgb((int)(245 * a), 255, 250, 230));
					}

					prev = here;
				}
			}
		}
	}

	public class PxStreakRenderable : IRenderable, IFinalizedRenderable
	{
		readonly PxStreakLayer layer;

		public PxStreakRenderable(PxStreakLayer layer, WPos pos)
		{
			this.layer = layer;
			Pos = pos;
		}

		public WPos Pos { get; }
		public int ZOffset => 2048;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return this; }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }
		public void Render(WorldRenderer wr) { layer.Draw(wr); }
		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}

	public class PxRocket : IProjectile, ISync
	{
		const float PixelPerWorld = 24f / 1024f;

		// Last filmed launch blast per launcher (world tick), so a salvo plays one
		static readonly Dictionary<Actor, int> LastLaunchBlast = new();

		readonly PxRocketInfo info;
		readonly ProjectileArgs args;

		// The launch point (origin moves when flares lure the rocket away)
		WPos origin;
		int flightTicks;
		readonly MersenneTwister rng = new(Game.CosmeticRandom.Next());
		PxParticles particles;
		WPos anchor;
		int ticks;
		bool launched;
		bool exploded;
		PxStreakLayer.Streak streak;

		[Sync]
		WPos target;

		[Sync]
		WPos pos;

		WPos lastPos;

		readonly WVec miss;

		// Dispensers aim (and burst) BurstHeight above the target
		readonly WVec burst;

		// This rocket's own random plume: how strong and how warm, and how its trail sways
		readonly float fire;
		readonly float warmth;
		readonly float swayAmp;
		readonly float swayFreq;
		readonly float swayPhase;

		// Corkscrew phase: from the launch point (synced), so the rockets of one salvo spiral out of step
		readonly double spiralPhase;

		public PxRocket(PxRocketInfo info, ProjectileArgs args)
		{
			this.info = info;
			this.args = args;
			origin = args.Source;
			pos = lastPos = args.Source;
			burst = new WVec(0, 0, info.BurstHeight.Length);
			target = args.PassiveTarget + burst;
			if (info.Inaccuracy.Length > 0)
			{
				var maxInaccuracyOffset = OpenRA.Mods.Common.Util.GetProjectileInaccuracy(info.Inaccuracy.Length, info.InaccuracyType, args);
				miss = WVec.FromPDF(args.SourceActor.World.SharedRandom, 2) * maxInaccuracyOffset / 1024;
				target += miss;
			}

			// A cold-launched missile always gets to light its motor before it arrives
			flightTicks = Math.Max(4, (target - origin).Length / Math.Max(1, info.Speed.Length)) + info.ColdLaunch / 2;
			if (info.ColdLaunch > 0)
				flightTicks = Math.Max(flightTicks, info.ColdLaunch + 6);

			fire = info.FirePlume * (0.7f + 0.6f * rng.NextFloat());
			warmth = 0.45f + 0.55f * rng.NextFloat();
			swayAmp = 0.5f + 2.5f * rng.NextFloat();
			swayFreq = 0.15f + 0.35f * rng.NextFloat();
			swayPhase = rng.NextFloat() * 6.283f;
			spiralPhase = ((origin.X + 3 * origin.Y + 7 * origin.Z) & 1023) * Math.PI / 512;

			// One step "behind" the launcher, so the first frame already faces the target
			lastPos = origin - (target - origin) / flightTicks;
		}

		/// <summary>Still flying (not yet exploded or shot down): point defence (PxPointDefense) can engage it.</summary>
		public bool InFlight => !exploded && launched;

		/// <summary>Point and air defence may shoot it down.</summary>
		public bool Interceptable => info.Interceptable;

		public WPos Position => pos;

		/// <summary>Where it will hit.</summary>
		public WPos TargetPosition => target;

		/// <summary>Percent chance that the seeker ignores flares.</summary>
		public int FlareResistance => info.FlareResistance;

		/// <summary>Kind of threat for air defence (PxInterceptor).</summary>
		public string ThreatType => info.ThreatType;

		/// <summary>Ticks until it hits.</summary>
		public int TicksLeft => flightTicks - ticks;

		/// <summary>Interceptors currently flying at it (PxInterceptor), so defences do not all fire at one missile.</summary>
		public int Engagements;

		/// <summary>Where it will be ticksAhead ticks from now (towards its current aim point).</summary>
		public WPos PositionAt(int ticksAhead) { return PositionAtTick(ticks + ticksAhead); }

		WPos PositionAtTick(int tick)
		{
			var t = Math.Min(1f, (float)tick / flightTicks);

			// Lured by flares: already at full speed, flies straight at them
			var u = Decoyed ? t : t + info.LaunchEase * (t * t - t);
			var dist = (target - origin).Length;
			WPos p;
			if (Decoyed || info.Profile == PxRocketProfile.Arc)
			{
				var height = Decoyed ? 0 : (int)(Math.Sin(u * Math.PI) * dist * info.Arc);
				p = WPos.Lerp(origin, target, (int)(u * 1024), 1024) + new WVec(0, 0, height);
			}
			else
			{
				// Quadratic Bezier: leaves along origin -> control (straight up, or up and forward) and ends on the target
				var climb = Math.Max(info.MinClimb.Length, (int)(dist * info.Climb));
				var control = (info.Profile == PxRocketProfile.Loft ? WPos.Lerp(origin, target, 1, 3) : origin) + new WVec(0, 0, climb);
				var a = (1 - u) * (1 - u);
				var b = 2 * u * (1 - u);
				var c = u * u;
				p = new WPos(
					(int)(a * origin.X + b * control.X + c * target.X),
					(int)(a * origin.Y + b * control.Y + c * target.Y),
					(int)(a * origin.Z + b * control.Z + c * target.Z));
			}

			if (info.Corkscrew.Length > 0 && !Decoyed)
			{
				// Spiral around the flight line: sideways and up/down, widest in the middle of the flight
				var d = target - origin;
				var h = Math.Max(1f, (float)Math.Sqrt(d.HorizontalLengthSquared));
				var turn = tick * 2 * Math.PI / Math.Max(2, info.CorkscrewPeriod) + spiralPhase;
				var r = info.Corkscrew.Length * Math.Sin(Math.Min(1f, t * 1.4f) * Math.PI);
				var side = r * Math.Sin(turn);
				p += new WVec((int)(-d.Y / h * side), (int)(d.X / h * side), (int)(r * Math.Cos(turn)));
			}

			return p;
		}

		/// <summary>The motor is burning (not yet lit after a cold launch, or coasting between two pulses).</summary>
		bool MotorLit => !info.Unpowered && (Decoyed || (ticks >= info.ColdLaunch && !Coasting));

		bool Coasting => info.CoastTicks > 0 && ticks >= info.CoastStart && ticks < info.CoastStart + info.CoastTicks;

		/// <summary>The player who fired it (null if unknown).</summary>
		public Player Owner => args.SourceActor?.Owner;

		/// <summary>The actor it is guided at (null for a ground or unguided shot).</summary>
		public Actor TargetActor => info.TrackTarget && args.GuidedTarget.Type == TargetType.Actor ? args.GuidedTarget.Actor : null;

		/// <summary>Lured away by flares (PxFlareDispenser): no longer follows its target.</summary>
		public bool Decoyed { get; private set; }

		/// <summary>The targeted jet already rolled its flare chance against this rocket.</summary>
		public bool FlaresChecked;

		/// <summary>Fooled by flares: stops tracking and flies from where it is to the decoy, bursting there.</summary>
		public void Decoy(WPos at)
		{
			if (exploded || Decoyed)
				return;

			Decoyed = true;
			origin = pos;
			target = at;
			ticks = 0;
			flightTicks = Math.Max(3, (target - origin).Length / Math.Max(1, info.Speed.Length));
		}

		/// <summary>A cluster dispenser opens: a sharp pop, a puff of grey-white smoke and the two shell halves
		/// tumbling away (the bomblets themselves are the FireCluster warhead's projectiles).</summary>
		void Open(float3 at)
		{
			Puff(PxParticleKind.Glow, at, 1, 0.7f, 4, 1f, new float3(1f, 0.92f, 0.75f), 0);
			for (var i = 0; i < 8; i++)
				Puff(PxParticleKind.Smoke, at, 5, 0.4f, info.TrailLife * 1.4f, 0.65f, new float3(0.82f, 0.81f, 0.79f), 0.02f);

			for (var i = 0; i < 2; i++)
			{
				var side = i == 0 ? -1 : 1;
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Chunk,
					X = at.X,
					Y = at.Y,
					Z = at.Z,
					VX = side * (0.6f + 0.4f * rng.NextFloat()),
					VY = (rng.NextFloat() - 0.5f) * 0.4f,
					VZ = 0.3f * rng.NextFloat(),
					Gravity = 0.05f,
					Drag = 0.01f,
					Life = 40,
					Size = 0.35f,
					Alpha = 1f,
					Tint = new float3(0.45f, 0.45f, 0.42f),
					Spin = side * 6,
					Angle = rng.Next(1024),
				});
			}
		}

		/// <summary>Shot down by point defence: bursts in the air without hitting anything.</summary>
		public void Intercept()
		{
			if (exploded)
				return;

			exploded = true;
			if (streak != null)
				streak.Done = true;

			if (particles == null)
				return;

			// Air burst: a white-hot flash, an orange fireball, burning fragments and sparks raining down out of a
			// puff of grey smoke that hangs in the air. Nothing reaches the ground.
			var k = info.InterceptBurst;
			var at = Local(pos);
			Puff(PxParticleKind.Glow, at, 2, 1.6f * k, 7, 1f, new float3(1f, 0.95f, 0.8f), 0);
			Puff(PxParticleKind.Glow, at, 3, 1.1f * k, 12, 0.8f, new float3(1f, 0.7f, 0.35f), 0);
			for (var i = 0; i < 8; i++)
				Puff(PxParticleKind.Fireball, at, 6 * k, 0.45f * k, 12, 0.95f, new float3(1f, 0.72f, 0.38f), 0.04f);

			for (var i = 0; i < 6; i++)
				Puff(PxParticleKind.Flame, at, 6 * k, 0.4f * k, 9, 0.95f, new float3(1f, 0.7f, 0.35f), 0.05f);

			for (var i = 0; i < 12; i++)
				Puff(PxParticleKind.Smoke, at, 10 * k, 0.55f * k, info.TrailLife * 1.5f, 0.7f, new float3(0.5f, 0.49f, 0.48f), 0.03f);

			// Fragments: fast sparks thrown out, then falling and burning out on the way down
			for (var i = 0; i < (int)(18 * k); i++)
			{
				var a = rng.NextFloat() * 6.283f;
				var v = (0.8f + 1.6f * rng.NextFloat()) * k;
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Spark,
					X = at.X,
					Y = at.Y,
					Z = at.Z,
					VX = (float)Math.Cos(a) * v,
					VY = (float)Math.Sin(a) * v * 0.6f,
					VZ = (rng.NextFloat() - 0.3f) * v,
					Gravity = 0.06f,
					Drag = 0.03f,
					Life = 14 + 16 * rng.NextFloat(),
					Size = 0.18f + 0.12f * rng.NextFloat(),
					Grow = 0,
					Alpha = 1f,
					Tint = new float3(1f, 0.8f + 0.2f * rng.NextFloat(), 0.5f),
					Angle = rng.Next(1024),
				});
			}
		}

		/// <summary>The exhaust colour, lightened towards white-hot, as a particle tint.</summary>
		float3 FlameTint => new((info.FlameColor.R + 255) / 510f, (info.FlameColor.G + 255) / 510f, (info.FlameColor.B + 255) / 510f);

		float3 Local(WPos p)
		{
			return new float3((p.X - anchor.X) * PixelPerWorld, (p.Y - anchor.Y) * PixelPerWorld, p.Z * PixelPerWorld);
		}

		void Puff(PxParticleKind kind, float3 at, float spread, float size, float life, float alpha, float3 tint, float rise)
		{
			particles.Add(new PxParticle
			{
				Kind = kind,
				X = at.X + (rng.NextFloat() - 0.5f) * spread,
				Y = at.Y + (rng.NextFloat() - 0.5f) * spread * 0.6f,
				Z = at.Z + (rng.NextFloat() - 0.5f) * spread * 0.4f,
				VX = (rng.NextFloat() - 0.5f) * 0.25f + 0.08f,
				VY = (rng.NextFloat() - 0.5f) * 0.15f,
				VZ = rise * (0.5f + rng.NextFloat()),
				Drag = 0.04f,
				Life = life * (0.75f + 0.5f * rng.NextFloat()),
				Size = size * (0.8f + 0.4f * rng.NextFloat()),
				Grow = 1.6f,
				Alpha = alpha,
				Tint = tint,
				Frame = rng.Next(Math.Max(1, particles.FrameCount(kind))),
				Spin = (rng.NextFloat() - 0.5f) * 4,
				Angle = rng.Next(1024),
			});
		}

		public void Tick(World world)
		{
			if (exploded)
			{
				// The shared layer keeps the lingering smoke alive; the projectile itself is done
				world.AddFrameEndTask(w => w.Remove(this));
				return;
			}

			var layer = PxTrailLayer.Get(world);
			particles = layer.Particles;
			anchor = layer.Anchor;

			var grey = new float3(info.SmokeColor.R / 255f, info.SmokeColor.G / 255f, info.SmokeColor.B / 255f);
			if (!launched)
			{
				launched = true;

				// Launch blast: a burst of smoke and a hot glow at the pod; a cold launch throws out a white gas cloud instead
				var at = Local(origin);
				var clip = info.WaterLaunch || info.ColdLaunch > 0 ? null : PxVideoEffect.Find(world, info.LaunchVideo);
				var launcher = args.SourceActor;
				if (clip != null && LastLaunchBlast.TryGetValue(launcher, out var last) && world.WorldTick - last < info.LaunchVideoGap)
					clip = null;
				if (clip != null)
				{
					if (LastLaunchBlast.Count > 256)
						LastLaunchBlast.Clear();
					LastLaunchBlast[launcher] = world.WorldTick;
					var foot = origin - new WVec(0, 0, world.Map.DistanceAboveTerrain(origin).Length);
					world.AddFrameEndTask(w => w.Add(new PxVideoEffect(w, foot, clip, clip.Scale * info.LaunchVideoScale, 60, 0)));
				}

				var gas = new float3(0.95f, 0.95f, 0.97f);
				for (var i = 0; i < info.LaunchPuffs; i++)
					Puff(PxParticleKind.Smoke, at, 10 * info.TrailSize, 0.55f * info.TrailSize, info.TrailLife * 0.8f, 0.8f,
						info.ColdLaunch > 0 ? gas : grey, info.ColdLaunch > 0 ? 0.3f : 0.15f);

				if (info.ColdLaunch > 0)
					for (var i = 0; i < info.LaunchPuffs / 2; i++)
						Puff(PxParticleKind.Billow, at, 6 * info.TrailSize, 0.4f * info.TrailSize, info.TrailLife, 0.7f, gas, 0.02f);
				else if (!info.Unpowered)
					Puff(PxParticleKind.Glow, at, 2, 0.7f * info.FlameSize, 6, 1f, FlameTint, 0);
				if (info.WaterLaunch)
				{
					var white = new float3(1f, 1f, 1f);
					for (var i = 0; i < 10; i++)
					{
						Puff(PxParticleKind.Foam, at, 8, 0.5f, info.TrailLife, 0.8f, white, 0);
						Puff(PxParticleKind.Smoke, at, 6, 0.45f, info.TrailLife * 0.5f, 0.6f, white, 0.35f);
					}
				}
			}

			if (info.TrackTarget && !Decoyed && args.GuidedTarget.IsValidFor(args.SourceActor))
				target = args.GuidedTarget.CenterPosition + miss + burst;

			ticks++;
			lastPos = pos;
			pos = PositionAtTick(ticks);
			if (info.StreakLife > 0)
			{
				var streaks = PxStreakLayer.Get(world);
				if (streak == null)
				{
					streak = streaks.Start(info);
					streak.Points.Add(origin);
					streak.Born.Add(streaks.Now);
				}

				streak.Points.Add(pos);
				streak.Born.Add(streaks.Now);
			}

			// Trail, like a rocket motor's plume: a white-hot nozzle, a rolling orange fire plume right behind it, then
			// fire-lit billowing smoke that twists (sways sideways) and lingers
			var here = Local(pos);
			var back = Local(lastPos);
			var lit = MotorLit;
			if (!Decoyed && (ticks == info.ColdLaunch || (info.CoastTicks > 0 && ticks == info.CoastStart + info.CoastTicks)) && ticks > 1)
			{
				// Ignition (after a cold launch or a coast): a flash and a burst of exhaust smoke
				Puff(PxParticleKind.Glow, back, 1, 0.8f * info.FlameSize, 5, 1f, new float3(1f, 0.97f, 0.9f), 0);
				for (var i = 0; i < 3; i++)
					Puff(PxParticleKind.Fireball, back, 2, 0.25f * info.FlameSize, 7, 0.9f, FlameTint, 0);
				for (var i = 0; i < 6; i++)
					Puff(PxParticleKind.Billow, back, 4 * info.TrailSize, 0.35f * info.TrailSize, info.TrailLife, 0.8f, grey, 0.05f);
			}

			if (!lit)
			{
				// Motor off: only a wisp of gas behind the missile
				if (ticks % 2 == 0)
					Puff(PxParticleKind.Smoke, back, 1.5f, 0.15f * info.TrailSize, info.TrailLife * 0.4f, 0.35f, new float3(0.95f, 0.95f, 0.97f), 0.02f);
			}
			else
			{
				var dx = here.X - back.X;
				var dy = here.Y - back.Y;
				var dl = Math.Max(0.01f, (float)Math.Sqrt(dx * dx + dy * dy));
				var side = new float3(-dy / dl, dx / dl, 0);
				var tint = new float3(grey.X, grey.Y * (1 - 0.14f * warmth), grey.Z * (1 - 0.34f * warmth));
				for (var i = 0; i < info.TrailDensity; i++)
				{
					var f = (float)(i + 1) / info.TrailDensity;
					var sway = (float)Math.Sin((ticks + f) * swayFreq + swayPhase) * swayAmp * info.TrailSize;
					var at = new float3(back.X + dx * f + side.X * sway, back.Y + dy * f + side.Y * sway * 0.6f, back.Z + (here.Z - back.Z) * f);
					Puff(PxParticleKind.Billow, at, 2.5f * info.TrailSize, 0.2f * info.TrailSize, info.TrailLife, 0.75f, tint, 0.04f);
					if (rng.NextFloat() < 0.5f)
						Puff(PxParticleKind.Smoke, at, 3 * info.TrailSize, 0.3f * info.TrailSize, info.TrailLife * 0.8f, 0.5f, tint, 0.05f);
				}

				if (fire > 0)
					for (var i = 0; i < 2; i++)
					{
						var f = rng.NextFloat();
						var at = new float3(back.X + dx * f, back.Y + dy * f, back.Z + (here.Z - back.Z) * f);
						Puff(PxParticleKind.Fireball, at, 1.5f * info.TrailSize, 0.16f * info.TrailSize * fire, 4 + 6 * fire, 0.85f, FlameTint, 0);
					}

				Puff(PxParticleKind.Glow, back, 0.5f, 0.25f * info.FlameSize, 3, 1f, new float3(1f, 0.97f, 0.9f), 0);
				Puff(PxParticleKind.Flame, back, 1, 0.22f * info.FlameSize, 5, 0.9f, FlameTint, 0);
			}

			for (var i = 0; i < info.Sparkle; i++)
			{
				// Burning submunition: glittering sparks left behind, hanging a moment before they fall and die out
				var f = rng.NextFloat();
				particles.Add(new PxParticle
				{
					Kind = PxParticleKind.Spark,
					X = back.X + (here.X - back.X) * f + (rng.NextFloat() - 0.5f) * 1.5f,
					Y = back.Y + (here.Y - back.Y) * f + (rng.NextFloat() - 0.5f) * 1.0f,
					Z = back.Z + (here.Z - back.Z) * f,
					VX = (rng.NextFloat() - 0.5f) * 0.15f,
					VY = (rng.NextFloat() - 0.5f) * 0.1f,
					VZ = (rng.NextFloat() - 0.2f) * 0.1f,
					Gravity = 0.01f,
					Drag = 0.08f,
					Life = 8 + 14 * rng.NextFloat(),
					Size = 0.08f + 0.1f * rng.NextFloat(),
					Alpha = 0.6f + 0.4f * rng.NextFloat(),
					Tint = new float3(1f, 0.85f + 0.15f * rng.NextFloat(), 0.6f + 0.3f * rng.NextFloat()),
					Angle = rng.Next(1024),
				});
			}

			if (info.DivertTicks > 0 && !Decoyed && flightTicks - ticks <= info.DivertTicks)
			{
				// Attitude control motors: tiny jets squirting sideways from a ring behind the nose
				var jets = new float3(1f, 0.92f, 0.75f);
				for (var i = 0; i < 3; i++)
				{
					var a = rng.NextFloat() * 6.283f;
					var dir = new float3((float)Math.Cos(a), (float)Math.Sin(a) * 0.6f, (float)Math.Sin(a * 1.7f) * 0.5f);
					Puff(PxParticleKind.Glow, here + 1.2f * dir, 0.3f, 0.12f, 2, 1f, jets, 0);
					Puff(PxParticleKind.Smoke, here + 3f * dir, 1, 0.1f, 14, 0.55f, new float3(0.95f, 0.95f, 0.95f), 0.02f);
				}
			}

			if (ticks >= flightTicks)
			{
				args.Weapon.Impact(Target.FromPos(target), new WarheadArgs(args) { ImpactPosition = target });
				exploded = true;
				if (info.BurstHeight.Length > 0)
					Open(Local(target));

				if (streak != null)
					streak.Done = true;
			}
		}

		public IEnumerable<IRenderable> Render(WorldRenderer wr)
		{
			// The trail renders through the shared PxTrailLayer
			if (!exploded && !wr.World.FogObscures(pos))
			{
				var sprite = info.Image != null;
				yield return new PxRocketRenderable(info, pos, lastPos, !sprite && info.DrawBody, MotorLit);
				if (sprite)
				{
					var d = pos - lastPos;
					var slope = d.Z / Math.Max(1f, (float)Math.Sqrt(d.HorizontalLengthSquared));
					var name = slope > info.AttitudeSlope && info.ClimbSequence != null ? info.ClimbSequence
						: slope < -info.AttitudeSlope && info.DiveSequence != null ? info.DiveSequence : info.Sequence;
					var seq = wr.World.Map.Sequences.GetSequence(info.Image, name);
					var yaw = d.HorizontalLengthSquared > 0 ? d.Yaw : WAngle.Zero;
					yield return new SpriteRenderable(seq.GetSprite(0, yaw), pos, WVec.Zero, info.ZOffset + 1, null,
						seq.Scale, 1f, float3.Ones, TintModifiers.None, true);
				}
			}
		}
	}

	public class PxRocketRenderable : IRenderable, IFinalizedRenderable
	{
		readonly PxRocketInfo info;
		readonly WPos last;
		readonly bool body;
		readonly bool lit;

		public PxRocketRenderable(PxRocketInfo info, WPos pos, WPos last, bool body = true, bool lit = true)
		{
			this.info = info;
			Pos = pos;
			this.last = last;
			this.body = body;
			this.lit = lit;
		}

		public WPos Pos { get; }
		public int ZOffset => info.ZOffset;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return new PxRocketRenderable(info, Pos + vec, last + vec, body, lit); }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		static Color Alpha(Color c, float a) { return Color.FromArgb((int)Math.Clamp(c.A * a, 0, 255), c.R, c.G, c.B); }

		public void Render(WorldRenderer wr)
		{
			var cr = Game.Renderer.WorldRgbaColorRenderer;
			var head = wr.Screen3DPosition(Pos);
			var prev = wr.Screen3DPosition(last);
			var d = head - prev;
			var len = (float)Math.Sqrt(d.X * d.X + d.Y * d.Y);
			var dir = len > 0.01f ? new float3(d.X / len, d.Y / len, 0) : new float3(1, 0, 0);
			var normal = new float3(-dir.Y, dir.X, 0);

			var bodyLen = wr.ScreenVector(new WVec(info.Length, WDist.Zero, WDist.Zero))[0];
			var w = Math.Max(1.5f, wr.ScreenVector(new WVec(info.Width, WDist.Zero, WDist.Zero))[0]);
			var tail = head - bodyLen * dir;

			// Exhaust: a flickering flame cone with a glow, hottest at the nozzle (none while the motor is off)
			if (lit)
			{
				var flick = 0.8f + 0.2f * Game.CosmeticRandom.NextFloat();
				var flameEnd = tail - bodyLen * 0.9f * info.FlameSize * flick * dir;
				cr.DrawLine(tail, flameEnd, w * 3.2f, Alpha(info.FlameColor, 0.25f));
				cr.DrawLine(tail, flameEnd, w * 1.6f, Alpha(info.FlameColor, 0.7f));
				cr.DrawLine(tail, tail - bodyLen * 0.45f * dir, w * 0.8f, Color.FromArgb(255, 255, 250, 225));
				var g = w * 2.6f;
				cr.FillEllipse(tail - new float3(g, g * 0.75f, 0), tail + new float3(g, g * 0.75f, 0), Alpha(info.FlameColor, 0.35f * flick));
			}

			if (!body)
				return;

			// Body, fins (and canards behind the nose), a band and a light nose
			if (info.Fins > 0)
			{
				var finRoot = tail + bodyLen * 0.2f * dir;
				var fin = w * 0.9f * info.Fins;
				cr.DrawLine(finRoot, tail - fin * normal - w * 0.5f * dir, Math.Max(1, w * 0.45f), info.BodyColor);
				cr.DrawLine(finRoot, tail + fin * normal - w * 0.5f * dir, Math.Max(1, w * 0.45f), info.BodyColor);
			}

			cr.DrawLine(tail, head, w, info.BodyColor);
			if (info.Canards)
			{
				var root = head - bodyLen * (info.NoseLength + 0.08f) * dir;
				cr.DrawLine(root, root - w * 0.75f * normal - w * 0.4f * dir, Math.Max(1, w * 0.35f), info.BodyColor);
				cr.DrawLine(root, root + w * 0.75f * normal - w * 0.4f * dir, Math.Max(1, w * 0.35f), info.BodyColor);
			}

			if (info.BandColor.A > 0)
			{
				var band = tail + bodyLen * 0.55f * dir;
				cr.DrawLine(band, band + bodyLen * 0.1f * dir, w * 1.05f, info.BandColor);
			}

			cr.DrawLine(tail + w * 0.25f * normal, head - bodyLen * 0.2f * dir + w * 0.25f * normal, Math.Max(1, w * 0.3f), Alpha(Color.White, 0.25f));
			cr.DrawLine(head - bodyLen * info.NoseLength * dir, head, w * 0.9f, info.NoseColor);
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}
}
