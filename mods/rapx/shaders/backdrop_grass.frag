#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// RedAlert Project X - lawns moving in the wind on painted map backdrops (PxBackdropGrass, Monument City).
// Runs right after the backdrop is drawn, before smudges, ore and actors. The grass mask (.r) says where the lawns are.
// Gusts: broad soft bands of wind travel downwind across the grass; where a gust passes, the blades bend over and
// show their lighter, sunlit sides, and the painted blades sway a little. Small ripples ride inside each gust.

uniform sampler2D WorldTexture;
uniform sampler2D FlowMap;   // the grass mask
uniform vec2 Scroll;        // world pixel at the buffer origin
uniform float Downscale;    // world pixels per buffer pixel
uniform vec2 TileSize;      // world pixels per cell
uniform vec2 FlowOrigin;    // cell at the mask's top-left corner
uniform vec2 FlowScale;     // mask UV per cell
uniform float Time;         // seconds
uniform float Speed;        // gust speed, world pixels per second
uniform vec2 Wind;          // unit wind direction (world pixels, y down)
uniform float Distortion;   // sway, world pixels
uniform float Shading;      // how much a gust lightens the grass
uniform sampler2D Detail;   // HD grass texture, drawn at screen resolution
uniform vec3 DetailMean;    // its mean colour
uniform float DetailCells;  // cells per repeat
uniform float DetailStrength;
uniform float DetailColor;
uniform float GradeSaturation; // colour grade: saturation, sage tint, its strength, brightness lift
uniform vec3 GradeTint;
uniform float GradeAmount;
uniform float GradeLift;

out vec4 fragColor;

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

float Grass(vec2 world)
{
	return texture(FlowMap, (world / TileSize - FlowOrigin) * FlowScale).r;
}

// Gust strength at a world position: long bands across the wind, broken up so they read as patches, moving downwind
float Gust(vec2 world)
{
	vec2 perp = vec2(-Wind.y, Wind.x);
	vec2 s = vec2(dot(world, Wind), dot(world, perp));
	s.x -= Time * Speed;
	float bands = Noise(s / vec2(90.0, 260.0)) * 0.65 + Noise(s / vec2(40.0, 110.0) + 5.1) * 0.35;
	return smoothstep(0.45, 0.85, bands);
}

void main()
{
	vec2 frag = gl_FragCoord.xy;
	vec4 c = texelFetch(WorldTexture, ivec2(frag), 0);
	vec2 world = Scroll + frag * Downscale;
	float grass = Grass(world);
	if (grass < 0.004)
	{
		fragColor = c;
		return;
	}

	float gust = Gust(world);

	// Ripples inside the gust: the blades bend in quick waves that also travel downwind
	vec2 perp = vec2(-Wind.y, Wind.x);
	float along = dot(world, Wind) - Time * Speed * 1.6;
	float ripple = sin(along / 7.0 + Noise(world / 25.0) * 6.0) * 0.5 + 0.5;
	float bend = gust * (0.55 + 0.45 * ripple);

	// Sway: borrow the painted grass from a little way upwind, only from other grass
	vec2 offset = -Wind * Distortion * bend + perp * Distortion * 0.4 * (ripple - 0.5);
	vec3 col = c.rgb;
	if (Grass(world + offset) > 0.6)
		col = texelFetch(WorldTexture, ivec2(frag + offset / Downscale), 0).rgb;

	// HD detail: blades and clumps at screen resolution, swaying with the same offset; the painted colour is kept
	// (detail light and dark laid over it), with a little of the detail's own colour for flowers and clover
	vec2 duv = (world + offset) / (TileSize * DetailCells);
	vec3 d = texture(Detail, duv).rgb;
	vec3 d2 = texture(Detail, duv * 0.37 + vec2(0.31, 0.17)).rgb;     // second, larger scale against repeats
	d = mix(d, d2, 0.35);
	vec3 ratio = d / max(DetailMean, vec3(0.05));
	vec3 detailed = col * mix(vec3(1.0), ratio, DetailStrength);
	float lum = dot(col, vec3(0.299, 0.587, 0.114)) / max(dot(DetailMean, vec3(0.299, 0.587, 0.114)), 0.05);
	col = mix(detailed, d * lum, DetailColor);

	// Bent blades show their paler, sunlit sides: lighter and a touch yellower; calm grass slightly deeper
	vec3 tint = vec3(1.0 + Shading * 1.1, 1.0 + Shading, 1.0 + Shading * 0.4);
	col *= mix(vec3(1.0 - Shading * 0.25), tint, bend);

	// Pale, soft grade: less saturated, pulled towards a sage green, a little lighter
	float l = dot(col, vec3(0.299, 0.587, 0.114));
	vec3 graded = mix(vec3(l), col, GradeSaturation);
	graded = mix(graded, vec3(l) * GradeTint, GradeAmount);
	col = graded + GradeLift * (1.0 - graded);

	fragColor = vec4(mix(c.rgb, col, grass), c.a);
}
