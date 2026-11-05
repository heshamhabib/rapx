#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// RedAlert Project X - weather on the ground (IDEA-20), drawn after the HD terrain pass so only the land changes:
// rain-soaked ground (darker, richer, glossy) with rippling puddles that mirror the clouds, rain rings on open water,
// settling snow that keeps the land's relief and sparkles, and wind-blown sand drifts. Everything is world-anchored.

uniform sampler2D WorldTexture;
uniform sampler2D CellMap;     // per cell: .bgra = rough, beach, water, river
uniform float HasCellMap;
uniform vec2 CellMapSize;
uniform float TileSize;
uniform vec2 Scroll;           // world pixel at the buffer origin
uniform float Downscale;       // world pixels per buffer pixel
uniform float Time;            // seconds

uniform float Wetness;         // 0..1 soaked ground
uniform float Rain;            // 0..1 falling rain (ripples)
uniform float Puddles;         // share of open ground that floods when soaked
uniform float SnowCover;       // 0..1
uniform float SandCover;       // 0..1
uniform float Dark;            // storm darkness (sky reflected in puddles)
uniform float Flash;           // lightning flash
uniform vec2 WindDir;
uniform vec2 CloudOffset;      // integrated cloud drift (world px)
uniform vec2 DustOffset;       // integrated sand drift (world px)
uniform vec3 SnowColor;
uniform vec3 SandColor;

out vec4 fragColor;

// PERF: cells the shroud pass paints over completely (PxShroudRenderer.BindHiddenCells); this pass skips them
uniform sampler2D HiddenMap;
uniform vec2 HiddenMapSize;  // map size in cells (0: no shroud)
uniform vec2 HiddenTileSize; // world pixels per cell

bool Hidden(vec2 worldPos)
{
	if (HiddenMapSize.x < 1.0)
		return false;

	ivec2 cell = ivec2(floor(worldPos / HiddenTileSize));
	if (cell.x < 0 || cell.y < 0 || cell.x >= int(HiddenMapSize.x) || cell.y >= int(HiddenMapSize.y))
		return false;

	return texelFetch(HiddenMap, cell, 0).r > 0.5;
}

const vec3 LightDir = vec3(-0.45, -0.55, 0.7);

float Hash(vec2 p)
{
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

vec2 Hash2(vec2 p)
{
	return vec2(Hash(p), Hash(p + vec2(17.17, 31.31)));
}

float Noise(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(Hash(i), Hash(i + vec2(1.0, 0.0)), u.x), mix(Hash(i + vec2(0.0, 1.0)), Hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float Fbm(vec2 p)
{
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++)
	{
		v += a * Noise(p);
		p = mat2(1.6, 1.2, -1.2, 1.6) * p + vec2(3.1, 1.7);
		a *= 0.5;
	}

	// ~0.47 +- 0.15 -> roughly 0..1
	return clamp((v - 0.47) / 0.3 + 0.5, 0.0, 1.0);
}

float Lum(vec3 c)
{
	return dot(c, vec3(0.299, 0.587, 0.114));
}

vec3 Fetch(ivec2 p)
{
	return texelFetch(WorldTexture, clamp(p, ivec2(0), textureSize(WorldTexture, 0) - 1), 0).rgb;
}

// Rain drops hitting water: expanding rings at random spots on a jittered grid.
// Returns (outward slope xy, ring highlight).
vec3 Ripples(vec2 p, float t, float density)
{
	const float Cell = 9.0;
	vec2 id = floor(p / Cell);
	vec3 acc = vec3(0.0);
	for (int y = -1; y <= 1; y++)
	{
		for (int x = -1; x <= 1; x++)
		{
			vec2 c = id + vec2(float(x), float(y));
			vec2 h = Hash2(c);
			float speed = 0.8 + 0.6 * Hash(c + 5.1);
			float cycle = t * speed + h.y;
			float phase = fract(cycle);

			// Each drop picks a new spot every cycle; light rain leaves most spots empty
			vec2 seed = c + floor(cycle) * 7.31;
			if (Hash(seed + 11.7) > density)
				continue;

			vec2 d = p - (c + 0.15 + 0.7 * Hash2(seed)) * Cell;
			float r = length(d);
			float x0 = (r - phase * 6.0) * 1.4;
			float fade = (1.0 - phase) * (1.0 - phase);
			float wave = sin(x0 * 2.4) * exp(-x0 * x0 * 0.3) * fade;
			acc.xy += (r > 0.001 ? d / r : vec2(0.0)) * wave;
			acc.z += exp(-x0 * x0 * 0.8) * fade;
		}
	}

	return acc;
}

void main()
{
	ivec2 ip = ivec2(gl_FragCoord.xy);
	vec4 src = texelFetch(WorldTexture, ip, 0);
	vec3 c = src.rgb;

	// Outside the map (black) stays black
	if (max(c.r, max(c.g, c.b)) < 0.004)
	{
		fragColor = src;
		return;
	}

	vec2 world = Scroll + gl_FragCoord.xy * Downscale;
	if (Hidden(world))
	{
		fragColor = src;
		return;
	}

	// Surface relief from the picture (luminance as height): fine for gloss, wide for slopes
	vec2 grad = vec2(Lum(Fetch(ip + ivec2(1, 0))) - Lum(Fetch(ip - ivec2(1, 0))),
		Lum(Fetch(ip + ivec2(0, 1))) - Lum(Fetch(ip - ivec2(0, 1))));
	vec2 grad2 = vec2(Lum(Fetch(ip + ivec2(3, 0))) - Lum(Fetch(ip - ivec2(3, 0))),
		Lum(Fetch(ip + ivec2(0, 3))) - Lum(Fetch(ip - ivec2(0, 3)))) / 3.0;

	// Open water and beaches from the terrain types (or a colour guess without the HD terrain pass)
	float water;
	float beach = 0.0;
	if (HasCellMap > 0.5)
	{
		vec4 cells = texture(CellMap, (world / TileSize) / CellMapSize).bgra;
		water = clamp(cells.z + cells.w, 0.0, 1.0);
		beach = cells.y;
	}
	else
		water = smoothstep(0.04, 0.12, c.b - max(c.r, c.g) * 0.9) * step(Lum(c), 0.45);

	float land = 1.0 - smoothstep(0.3, 0.7, water);
	vec3 L = normalize(LightDir);
	vec3 col = c;

	// --- Rain-soaked ground ---
	if (Wetness > 0.003)
	{
		float w = Wetness * land;

		// Wet soil is darker and more saturated
		vec3 wet = pow(col, vec3(1.0 + 0.5 * w)) * (1.0 - 0.2 * w);
		float l = Lum(wet);
		col = mix(vec3(l), wet, 1.0 + 0.3 * w);

		// Gloss: a soft sheen off every bump, lit by the storm sky (and the lightning)
		vec3 n = normalize(vec3(-grad * 3.5, 1.0));
		vec3 h = normalize(L + vec3(0.0, 0.0, 1.0));
		float spec = pow(max(dot(n, h), 0.0), 36.0);
		float skyLight = 0.6 - 0.35 * Dark + Flash * 0.8;
		col += spec * w * 0.2 * skyLight * vec3(0.85, 0.9, 1.0);

		// Puddles: small pools (a cell or two across) that gather on flat ground and grow as it soaks
		float flatness = 1.0 - smoothstep(0.03, 0.2, length(grad2));
		float pn = Fbm(world / 46.0 + 3.7) * 0.75 + Fbm(world / 13.0 + 9.2) * 0.25 - (1.0 - flatness) * 0.05;
		float threshold = 1.0 - Puddles * Wetness * 0.45;
		float puddle = smoothstep(threshold, threshold + 0.09, pn) * land * (1.0 - 0.7 * beach);
		if (puddle > 0.001)
		{
			vec3 rip = Ripples(world, Time, 0.25 + 0.75 * Rain) * Rain;

			// Mirror of the clouds drifting overhead, broken up by the ripples
			vec2 r = world + rip.xy * 5.0;
			float cloud = Fbm((r + CloudOffset) / 220.0);
			vec3 sky = mix(vec3(0.3, 0.35, 0.43), vec3(0.72, 0.76, 0.82), smoothstep(0.3, 0.8, cloud));
			sky = sky * (1.0 - 0.5 * Dark) + Flash * vec3(0.35, 0.37, 0.4);

			// Ground seen through the shallow water: darker and cooler, refracted by the ripples
			ivec2 ro = ivec2(rip.xy * 2.0);
			vec3 under = (Fetch(ip + ro) + Fetch(ip + ro + ivec2(2, 1)) + Fetch(ip + ro - ivec2(1, 2))) / 3.0;
			under *= vec3(0.5, 0.53, 0.58);

			// Deeper middle reflects more sky; a bright glint where the ripples face the light
			float depth = smoothstep(threshold, threshold + 0.16, pn);
			vec3 pc = mix(under, sky, 0.1 + 0.22 * depth);
			pc += rip.z * vec3(0.08, 0.085, 0.095) * (0.7 + Flash);
			pc += pow(max(dot(normalize(vec3(-rip.xy * 0.8, 1.0)), normalize(L + vec3(0.0, 0.0, 1.0))), 0.0), 60.0) * 0.25;

			// Muddy darker rim around each puddle
			float rim = smoothstep(threshold - 0.07, threshold, pn) - puddle;
			col *= 1.0 - 0.3 * rim * land * Wetness;
			col = mix(col, pc, puddle * 0.92);
		}
	}

	// --- Rain on open water: rings and a darker, rougher surface ---
	if (Rain > 0.01 && water > 0.01)
	{
		vec3 rip = Ripples(world * 0.8 + 50.0, Time * 1.1, 0.3 + 0.7 * Rain);
		col *= 1.0 - 0.12 * Rain * water;
		col += (rip.z * 0.07 + rip.x * 0.03) * Rain * water * vec3(0.8, 0.88, 1.0);
	}

	// --- Snow cover: drifts along the wind, steep slopes stay bare, the land form shows through ---
	if (SnowCover > 0.003)
	{
		vec2 wd = normalize(WindDir + vec2(0.0001));
		vec2 wq = vec2(dot(world, wd), dot(world, vec2(-wd.y, wd.x)));
		float drift = Fbm(vec2(wq.x / 380.0, wq.y / 110.0));
		float s = Fbm(world / 90.0) * 0.55 + drift * 0.45 - length(grad2) * 3.0;
		float t = 1.0 - SnowCover * 1.15;
		float cover = smoothstep(t, t + 0.18, s) * (1.0 - smoothstep(0.2, 0.6, water));

		vec3 n = normalize(vec3(-grad2 * 2.5, 1.0));
		float light = dot(n, L);
		vec3 snow = SnowColor * (0.8 + 0.25 * light) * (0.95 + 0.08 * Noise(world / 5.0));

		// Cold blue in the hollows
		snow = mix(snow, snow * vec3(0.8, 0.87, 1.0), clamp(0.55 - light, 0.0, 1.0));

		// Glitter: a few crystals catch the light
		float g = Hash(floor(world / 2.0));
		snow += step(0.995, g) * (0.5 + 0.5 * sin(Time * 3.0 + g * 80.0)) * 0.5 * cover;

		col = mix(col, snow, cover);

		// Thin dusting where the cover breaks up
		col = mix(col, SnowColor * (0.7 + 0.3 * Lum(c)), smoothstep(t - 0.25, t, s) * (1.0 - cover) * 0.35 * land);
	}

	// --- Sand drifts: long streaks along the wind with fine ripples across them, creeping slowly ---
	if (SandCover > 0.003)
	{
		vec2 wd = normalize(WindDir + vec2(0.0001));
		vec2 q = world - DustOffset * 0.08;
		vec2 wq = vec2(dot(q, wd), dot(q, vec2(-wd.y, wd.x)));
		float streak = Fbm(vec2(wq.x / 360.0, wq.y / 50.0));
		float ripple = 0.5 + 0.5 * sin(wq.x / 6.0 + Noise(world / 40.0) * 6.0);
		float t = 1.0 - SandCover * 0.85;
		float cover = smoothstep(t, t + 0.25, streak) * land;
		vec3 sand = SandColor * (0.85 + 0.18 * ripple) * (0.92 + 0.16 * Noise(world / 3.0));
		col = mix(col, sand, cover * 0.8);
	}

	fragColor = vec4(col, src.a);
}
