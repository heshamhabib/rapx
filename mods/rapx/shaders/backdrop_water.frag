#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// RedAlert Project X - a flowing river on painted map backdrops (PxBackdropWater, Berlin's Spree).
// Runs right after the backdrop is drawn, before smudges, ore and actors, so boats and units stay sharp.
// The map's flow map gives per pixel: .r water coverage, .g flow angle (0.5 = due west), .b distance from the bank.
// Classic two-phase flow mapping: two ripple layers are advected along the current and cross-faded half a cycle
// apart, so the surface keeps streaming downstream without ever stretching. The ripples wobble the painted water
// (refraction), shade it by slope, catch the sun and break into faint foam along the quay walls.

uniform sampler2D WorldTexture;
uniform sampler2D FlowMap;
uniform vec2 Scroll;        // world pixel at the buffer origin
uniform float Downscale;    // world pixels per buffer pixel
uniform vec2 TileSize;      // world pixels per cell
uniform vec2 FlowOrigin;    // cell at the flow map's top-left corner
uniform vec2 FlowScale;     // flow map UV per cell
uniform float Time;         // seconds, wraps at a multiple of Cycle
uniform float Cycle;        // seconds per advection phase
uniform float Speed;        // world pixels per second in mid-stream
uniform float Distortion;   // refraction strength (world pixels)
uniform float Shading;      // slope shading strength
uniform float Glint;        // sun glint strength
uniform float Foam;         // foam strength at the banks

out vec4 fragColor;

const float PI2 = 6.2831853;

float Hash(vec2 p)
{
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float Noise(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(Hash(i), Hash(i + vec2(1.0, 0.0)), u.x), mix(Hash(i + vec2(0.0, 1.0)), Hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

vec4 Flow(vec2 world)
{
	return texture(FlowMap, (world / TileSize - FlowOrigin) * FlowScale);
}

// Surface height in the current's frame: long current streaks along the flow plus short isotropic chop
float Height(vec2 q, vec2 dir)
{
	vec2 perp = vec2(-dir.y, dir.x);
	vec2 s = vec2(dot(q, dir), dot(q, perp));
	float streaks = Noise(s / vec2(30.0, 7.0)) * 0.6 + Noise(s / vec2(13.0, 4.0) + 7.3) * 0.4;
	float chop = Noise(q / 6.0 + 3.1) * 0.65 + Noise(q / 2.8 + 11.7) * 0.35;
	return streaks * 0.55 + chop * 0.45;
}

// Slope of the advected surface at q (finite differences in world pixels)
vec2 Slope(vec2 q, vec2 dir)
{
	const float e = 1.5;
	float h = Height(q, dir);
	return vec2(Height(q + vec2(e, 0.0), dir) - h, Height(q + vec2(0.0, e), dir) - h) / e;
}

void main()
{
	vec2 frag = gl_FragCoord.xy;
	vec4 c = texelFetch(WorldTexture, ivec2(frag), 0);
	vec2 world = Scroll + frag * Downscale;
	vec4 f = Flow(world);
	float water = f.r;
	if (water < 0.004)
	{
		fragColor = c;
		return;
	}

	float angle = (f.g - 0.5) * PI2;
	vec2 dir = -vec2(cos(angle), sin(angle));
	float bank = f.b;

	// Slower along the quays, fastest in mid-stream
	vec2 flow = dir * Speed * mix(0.3, 1.0, smoothstep(0.0, 0.8, bank));

	float p0 = fract(Time / Cycle);
	float p1 = fract(Time / Cycle + 0.5);
	float blend = abs(1.0 - 2.0 * p0);
	vec2 q0 = world - flow * p0 * Cycle;
	vec2 q1 = world - flow * p1 * Cycle + vec2(37.0, 19.0);
	vec2 slope = mix(Slope(q0, dir), Slope(q1, dir), blend);
	float height = mix(Height(q0, dir), Height(q1, dir), blend);

	// Refraction: borrow the painted water from a little way off, never from the quay walls
	vec2 offset = slope * Distortion;
	vec3 col = c.rgb;
	if (Flow(world + offset).r > 0.6)
		col = texelFetch(WorldTexture, ivec2(frag + offset / Downscale), 0).rgb;

	// Slope shading with the sun in the north-west, a touch darker in the troughs
	vec2 sun = normalize(vec2(-0.55, -0.83));
	float lit = dot(slope, sun) * 6.0;
	col *= 1.0 + Shading * clamp(lit, -1.0, 1.0) - 0.06 * Shading * (0.5 - height);

	// Sun glints on the faces turned to the sun, twinkling as the layers fade in and out
	float facing = clamp(dot(slope, sun) * 9.0 - 0.55, 0.0, 1.0);
	float sparkle = Noise(world / 3.0 + Time * vec2(0.7, -0.4));
	col += vec3(1.0, 0.96, 0.86) * Glint * facing * facing * smoothstep(0.55, 0.9, sparkle);

	// Foam streaks where the current rubs along the banks
	float edge = 1.0 - smoothstep(0.0, 0.35, bank);
	float streak = mix(Noise((q0 - dir * 4.0) / vec2(11.0, 3.5)), Noise((q1 - dir * 4.0) / vec2(11.0, 3.5)), blend);
	col = mix(col, vec3(0.78, 0.82, 0.80), Foam * edge * smoothstep(0.55, 0.85, streak));

	fragColor = vec4(mix(c.rgb, col, water), c.a);
}
