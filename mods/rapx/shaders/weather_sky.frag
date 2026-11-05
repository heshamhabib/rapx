#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// RedAlert Project X - weather in the air (IDEA-20), drawn over the whole world view.
// Procedural, no textures: heat shimmer, the light of each weather, drifting fog banks, blowing dust and sand,
// gusting rain curtains, four depth layers of rain (parallax: near drops move faster when the camera scrolls),
// splashes on the ground, four layers of snowflakes (soft bokeh up close, motion streaks in a blizzard),
// tumbling leaves / powder in strong wind, branching lightning bolts that light the ground, and sky flashes.

uniform sampler2D WorldTexture;
uniform vec2 Scroll;        // world pixel at the buffer origin
uniform float Downscale;    // world pixels per buffer pixel
uniform vec2 ViewSize;      // visible view in buffer pixels
uniform float Time;         // seconds

uniform float Rain, Snow, Sand, Fog, Storm, Haze, Wind, Dark, Dust, Flash;
uniform vec2 WindDir;
uniform vec2 FogOffset;     // integrated fog drift (world px)
uniform vec2 DustOffset;    // integrated dust drift (world px)
uniform vec3 FogColor;
uniform vec3 SandColor;
uniform vec3 DebrisColor;

// Lightning bolts: (start xy, end xy) in world px; params = (intensity, seed, branches)
uniform vec4 Bolt0;
uniform vec3 BoltParams0;
uniform vec4 Bolt1;
uniform vec3 BoltParams1;

out vec4 fragColor;

float Hash(vec2 p)
{
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float Hash1(float x)
{
	return fract(sin(x * 127.1) * 43758.5453);
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

	return clamp((v - 0.47) / 0.3 + 0.5, 0.0, 1.0);
}

float Lum(vec3 c)
{
	return dot(c, vec3(0.299, 0.587, 0.114));
}

// One streak per jittered cell. q is a frame where streaks run along +y (already moving); cell in px.
float Streak(vec2 q, vec2 cell, float len, float width, float density, float seed)
{
	vec2 g = q / cell;
	vec2 id = floor(g);
	vec2 f = fract(g);
	if (Hash(id + seed) > density)
		return 0.0;

	float x = 0.15 + 0.7 * Hash(id + seed + 3.7);
	float y = Hash(id + seed + 9.1) * (1.0 - len);
	float along = (f.y - y) / len;
	if (along < 0.0 || along > 1.0)
		return 0.0;

	// Fades in from the tail, brightest towards the leading end
	float dx = abs(f.x - x) * cell.x;
	float shape = smoothstep(0.0, 0.6, along) * smoothstep(1.0, 0.9, along);
	return smoothstep(width, width * 0.2, dx) * shape * (0.55 + 0.45 * Hash(id + seed + 1.3));
}

float RainLayer(vec2 p, float slant, vec2 cell, float speed, float len, float width, float density, float seed)
{
	vec2 q = vec2(p.x - p.y * slant, p.y - Time * speed);
	return Streak(q, cell, len, max(width, Downscale * 0.9), density, seed);
}

// Flakes falling with the wind, fluttering; stretched along their motion when the wind is strong
float FlakeLayer(vec2 p, float cell, float speed, float size, float density, float seed, float stretch, float flutter)
{
	vec2 v = vec2(WindDir.x * (0.3 + Wind * 2.2), 1.0) * speed;
	p -= v * Time;
	p.x += sin(p.y / 37.0 + seed + Time * 0.7) * flutter;

	vec2 g = p / cell;
	vec2 id = floor(g);
	vec2 f = fract(g);
	float h = Hash(id + seed);
	if (h > density)
		return 0.0;

	vec2 pos = 0.2 + 0.6 * Hash2(id + seed);
	pos += 0.12 * vec2(sin(Time * (1.3 + h * 2.0) + h * 30.0), cos(Time * (1.1 + h) + h * 17.0));
	vec2 d = (f - pos) * cell;
	vec2 vd = normalize(v);
	float dist = length(vec2(dot(d, vd) / stretch, dot(d, vec2(-vd.y, vd.x))));
	float s = max(size * (0.6 + 0.6 * Hash(id + seed + 4.4)), Downscale * 0.8);
	return smoothstep(s, s * 0.25, dist) * (0.6 + 0.4 * h / max(density, 0.001));
}

// Small splash crowns where drops hit the ground (world-anchored)
float Splashes(vec2 w, float density)
{
	const float Cell = 17.0;
	vec2 id = floor(w / Cell);
	float acc = 0.0;
	for (int y = -1; y <= 1; y++)
	{
		for (int x = -1; x <= 1; x++)
		{
			vec2 c = id + vec2(float(x), float(y));
			float cycle = Time * (1.7 + Hash(c + 2.2)) + Hash(c);
			vec2 seed = c + floor(cycle) * 3.17;
			if (Hash(seed + 8.8) > density)
				continue;

			float s = fract(cycle) / 0.3;
			if (s > 1.0)
				continue;

			vec2 d = w - (c + 0.15 + 0.7 * Hash2(seed)) * Cell;
			d.y *= 2.0;
			float r = length(d);
			float ring = exp(-pow(r - (0.6 + 2.6 * s), 2.0) * 2.0) * (1.0 - s);

			// Two droplets thrown up and out
			vec2 dr = vec2(abs(d.x) - 1.8 * s, (d.y / 2.0) + 7.0 * s * (1.0 - s));
			float drop = exp(-dot(dr, dr) * 3.0) * (1.0 - s);
			acc += ring * 0.45 + drop * 0.5;
		}
	}

	return acc;
}

float SegDist(vec2 p, vec2 a, vec2 b)
{
	vec2 pa = p - a;
	vec2 ba = b - a;
	float h = clamp(dot(pa, ba) / max(dot(ba, ba), 0.0001), 0.0, 1.0);
	return length(pa - ba * h);
}

vec2 BoltPoint(vec2 a, vec2 b, float t, float seed, float amp)
{
	vec2 d = b - a;
	vec2 n = normalize(vec2(-d.y, d.x));
	float o = (Noise(vec2(t * 5.0, seed)) - 0.5)
		+ (Noise(vec2(t * 17.0, seed + 3.0)) - 0.5) * 0.6
		+ (Noise(vec2(t * 43.0, seed + 9.0)) - 0.5) * 0.35;
	return a + d * t + n * o * amp * sqrt(sin(3.14159 * t));
}

float BoltDist(vec2 p, vec2 a, vec2 b, float seed, float amp, float segs)
{
	float d = 1e5;
	vec2 prev = a;
	for (int i = 1; i <= 32; i++)
	{
		if (float(i) > segs)
			break;

		vec2 cur = BoltPoint(a, b, float(i) / segs, seed, amp);
		d = min(d, SegDist(p, prev, cur));
		prev = cur;
	}

	return d;
}

vec3 Lightning(vec2 p, vec4 bolt, vec3 params)
{
	float intensity = params.x;
	if (intensity <= 0.001)
		return vec3(0.0);

	vec2 a = bolt.xy;
	vec2 b = bolt.zw;
	float seed = params.y;
	float len = length(b - a);
	float amp = len * 0.12;
	vec3 glowColor = vec3(0.62, 0.7, 1.0);

	// The strike lights the ground around it (flattened for the isometric view)
	vec2 g = (p - b) * vec2(1.0, 1.6);
	vec3 result = glowColor * (exp(-length(g) / 130.0) * 0.45 + exp(-length(g) / 22.0) * 0.6) * intensity;

	if (SegDist(p, a, b) > amp * 1.2 + 200.0)
		return result;

	float d = BoltDist(p, a, b, seed, amp, 32.0);
	float core = smoothstep(2.0, 0.3, d / Downscale);
	for (int k = 0; k < 3; k++)
	{
		if (float(k) >= params.z)
			break;

		float fk = float(k);
		float tb = 0.3 + 0.2 * fk + 0.1 * Hash1(seed + fk);
		vec2 s = BoltPoint(a, b, tb, seed, amp);
		float ang = (Hash1(seed + fk * 3.3) > 0.5 ? 1.0 : -1.0) * (0.4 + 0.5 * Hash1(seed + fk * 5.1));
		vec2 dir = normalize(b - a);
		dir = vec2(dir.x * cos(ang) - dir.y * sin(ang), dir.x * sin(ang) + dir.y * cos(ang));
		vec2 e = s + dir * len * (0.15 + 0.15 * Hash1(seed + fk * 7.7));
		d = min(d, BoltDist(p, s, e, seed + fk * 13.0 + 1.0, amp * 0.35, 14.0) * 1.8);
	}

	core = max(core, smoothstep(1.4, 0.2, d / Downscale) * 0.7);
	float glow = exp(-d / 4.0) * 0.7 + exp(-d / 18.0) * 0.3 + exp(-d / 90.0) * 0.08;
	result += (vec3(1.0) * core * 1.5 + glowColor * glow) * intensity;
	return result;
}

void main()
{
	vec2 fc = gl_FragCoord.xy;
	vec2 view = fc * Downscale;
	vec2 world = Scroll + view;
	vec2 bufferSize = vec2(textureSize(WorldTexture, 0));

	// Heat shimmer: the air bends the light above the hot ground
	vec2 uvOffset = vec2(0.0);
	if (Haze > 0.003)
	{
		vec2 sh = vec2(Noise(world / 22.0 + vec2(0.0, Time * 1.8)) - 0.5, Noise(world / 29.0 + vec2(Time * 1.3, 7.0)) - 0.5);
		uvOffset = sh * Haze * 2.6;
	}

	vec4 src = texture(WorldTexture, (fc + uvOffset) / bufferSize);
	vec3 col = src.rgb;
	float baseLum = Lum(col);

	// --- Light of the weather: storms are dark, cold and grey; heat is bright and warm ---
	col = mix(col, vec3(Lum(col)), clamp(0.35 * Dark + 0.12 * Rain + 0.2 * Fog, 0.0, 1.0));
	col *= mix(vec3(1.0), vec3(0.8, 0.86, 1.0), clamp(Dark * 1.3 + Snow * 0.25, 0.0, 1.0));
	col *= 1.0 - 0.5 * Dark;
	col = mix(col, col * vec3(1.06, 1.0, 0.9) + vec3(0.03, 0.02, 0.0), Haze);

	// --- Fog banks: two drifting layers, the upper one with a little parallax ---
	if (Fog > 0.003)
	{
		float f1 = Fbm((world - FogOffset) / 380.0);
		float f2 = Fbm((world + Scroll * 0.12 - FogOffset * 1.6) / 150.0 + 7.3);
		float f3 = Fbm((world + Scroll * 0.25 - FogOffset * 2.3) / 70.0 + 2.1);
		float bank = smoothstep(0.3, 0.8, f1 * 0.6 + f2 * 0.3 + f3 * 0.1);
		float density = Fog * (0.2 + 0.68 * bank);
		vec3 fogColor = FogColor * (0.9 + 0.15 * f2) * (1.0 - 0.45 * Dark) + Flash * 0.35;
		col = mix(col, fogColor, density);
	}

	// --- Sand and dust: billowing clouds, a warm haze, and grains racing along the wind ---
	vec2 wd = normalize(WindDir + vec2(0.0001));
	vec2 wp = vec2(-wd.y, wd.x);
	if (Sand + Dust > 0.003)
	{
		float d1 = Fbm((world - DustOffset) / vec2(480.0, 300.0));
		float d2 = Fbm((world - DustOffset * 1.4) / 170.0 + 5.0);
		float cloud = smoothstep(0.3, 0.9, d1 * 0.6 + d2 * 0.4);
		vec3 dustColor = mix(FogColor, SandColor, clamp(Sand * 1.5, 0.0, 1.0)) * (0.75 + 0.35 * d2);
		col = mix(col, col * mix(vec3(1.0), SandColor * 1.3, 0.6), Sand * 0.5);
		col = mix(col, dustColor, clamp((Sand * 0.6 + Dust * 0.3) * cloud + Sand * 0.15, 0.0, 0.85));

		if (Sand > 0.01)
		{
			vec2 q = vec2(dot(view + Scroll * 1.1, wp), dot(view + Scroll * 1.1, wd) - Time * 900.0);
			float grains = Streak(q, vec2(5.0, 140.0), 0.35, max(0.5, Downscale * 0.8), 0.5 * Sand, 2.0);
			q = vec2(dot(view + Scroll * 1.3, wp), dot(view + Scroll * 1.3, wd) - Time * 1300.0);
			grains += Streak(q, vec2(9.0, 220.0), 0.3, max(0.9, Downscale * 0.8), 0.35 * Sand, 7.0);
			col = mix(col, SandColor * 1.25, clamp(grains * 0.55, 0.0, 0.8));
		}
	}

	// --- Rain ---
	if (Rain > 0.003)
	{
		float slant = clamp(WindDir.x * (0.08 + 0.45 * Wind), -0.6, 0.6);

		// Gusting curtains of heavier rain sweep across the field
		float sheet = Fbm((world - DustOffset * 0.6) / vec2(520.0, 320.0));
		float gust = 0.55 + 0.9 * sheet;
		col = mix(col, FogColor * (0.75 - 0.3 * Dark) + Flash * 0.3, Rain * (0.06 + 0.12 * sheet) * (0.6 + Storm));

		// Splashes on the ground
		float splash = Splashes(world, Rain * 0.55);
		col += splash * (0.05 + 0.25 * Lum(col)) * vec3(0.85, 0.9, 1.0) * (1.0 + Flash);

		float light = 1.0 + Flash * 1.5;
		vec3 dropColor = vec3(0.82, 0.88, 1.0);
		float r1 = RainLayer(view + Scroll * 1.0, slant, vec2(8.0, 60.0), 950.0, 0.45, 0.9, 0.5 * Rain * gust, 1.0);
		float r2 = RainLayer(view + Scroll * 1.12, slant * 1.1, vec2(13.0, 100.0), 1300.0, 0.5, 1.2, 0.42 * Rain * gust, 2.0);
		float r3 = RainLayer(view + Scroll * 1.3, slant * 1.2, vec2(22.0, 170.0), 1750.0, 0.55, 1.7, 0.32 * Rain * gust, 3.0);
		float r4 = RainLayer(view + Scroll * 1.6, slant * 1.35, vec2(40.0, 320.0), 2400.0, 0.6, 3.0, 0.25 * Rain * Storm * gust, 4.0);
		float drops = r1 * 0.4 + r2 * 0.55 + r3 * 0.7 + r4 * 0.5;

		// Near drops refract what is behind them
		if (r3 + r4 > 0.01)
			col = mix(col, texture(WorldTexture, (fc + uvOffset + vec2(2.0, 1.0)) / bufferSize).rgb * 1.15, clamp(r3 * 0.25 + r4 * 0.35, 0.0, 1.0));

		col = mix(col, dropColor * (0.55 + 0.35 * Lum(col)) * light, clamp(drops * 0.55, 0.0, 0.8));
	}

	// --- Snow ---
	if (Snow > 0.003)
	{
		float stretch = 1.0 + Wind * Snow * 4.5;
		float flutter = 6.0 * (1.0 - Wind * 0.6);
		float density = min(1.0, Snow * 1.3);
		float s1 = FlakeLayer(view + Scroll * 1.0, 12.0, 45.0, 1.1, 0.6 * density, 1.0, stretch, flutter);
		float s2 = FlakeLayer(view + Scroll * 1.15, 20.0, 70.0, 1.8, 0.55 * density, 2.0, stretch, flutter);
		float s3 = FlakeLayer(view + Scroll * 1.35, 38.0, 110.0, 3.0, 0.45 * density, 3.0, stretch, flutter);
		float s4 = FlakeLayer(view + Scroll * 1.8, 90.0, 190.0, 6.5, 0.3 * density, 4.0, stretch, flutter * 2.0);
		float flakes = clamp(s1 * 0.55 + s2 * 0.7 + s3 * 0.8 + s4 * 0.35, 0.0, 1.0);
		vec3 flakeColor = vec3(0.96, 0.98, 1.0) * (1.0 - 0.25 * Dark) + Flash * 0.5;
		col = mix(col, flakeColor, flakes);
	}

	// --- Strong wind: leaves (or powder) tumbling past ---
	float debris = max(0.0, Wind - 0.45) * (1.0 - Rain) * (1.0 - Snow) * (1.0 - Sand);
	if (debris > 0.003)
	{
		float b1 = FlakeLayer(view + Scroll * 1.2, 60.0, 60.0, 2.6, debris * 0.7, 11.0, 1.8, 14.0);
		float b2 = FlakeLayer(view + Scroll * 1.5, 110.0, 90.0, 4.0, debris * 0.6, 12.0, 2.2, 20.0);
		vec3 leaf = DebrisColor * (0.7 + 0.6 * Hash(floor((view + Scroll) / 40.0)));
		col = mix(col, leaf, clamp(b1 + b2, 0.0, 1.0) * 0.9);
	}

	// --- Lightning: bolts light the land around them, the whole sky flashes ---
	vec3 bolt = Lightning(world, Bolt0, BoltParams0) + Lightning(world, Bolt1, BoltParams1);
	col += bolt * (0.35 + col);
	col = col * (1.0 + Flash * 0.6) + Flash * 0.04 * vec3(0.85, 0.9, 1.0) * step(0.004, baseLum);

	// --- Heavy weather closes in at the edges of the view ---
	vec2 uv = fc / max(ViewSize, vec2(1.0)) - 0.5;
	float vignette = smoothstep(0.3, 0.85, length(uv * vec2(1.0, 0.8)) * 1.3);
	col *= 1.0 - vignette * clamp(0.5 * Dark + 0.15 * Fog + 0.3 * Sand + 0.15 * Snow * Wind, 0.0, 0.6);

	fragColor = vec4(col, src.a);
}
