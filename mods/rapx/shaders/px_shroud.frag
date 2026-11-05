#version {VERSION}
#ifdef GL_ES
precision highp float;
precision highp int;
#endif

// RedAlert Project X - high-end shroud and fog of war (IDEA-23, Tactical style).
// Replaces the whole shroud: one pass over the finished world image.
//  - unexplored: a navy "command table" with a hex grid, procedural contours, map coordinates and a radar sweep
//  - border: smooth anti-aliased curve with a glowing red line and hex cells dissolving along it
//  - newly explored ground "boots up" with a hologram scan
//  - fog of war: darker, cooler, desaturated, film grain, dim inner border
//  - outside the map: darker hatched table and a metal frame line
// Every pattern is procedural; nothing under the shroud is ever sampled from the world image.

uniform sampler2D WorldTexture;
uniform sampler2D CellMap;  // one texel per cell, .bgra = (explored, visible, reveal, inside map)
uniform vec2 CellMapSize;
uniform vec2 TileSize;      // world pixels per cell
uniform vec2 Scroll;        // world pixel at the buffer origin
uniform float Downscale;    // world pixels per buffer pixel
uniform float Time;         // seconds
uniform vec4 Bounds;        // playable area in world pixels (left, top, right, bottom)
uniform float SweepPeriod;
uniform vec3 BorderColor;
uniform vec3 HoloColor;
uniform vec2 Fog;           // brightness, saturation
uniform vec3 FogTint;

out vec4 fragColor;

const float TAU = 6.2831853;

// 3x5 pixel font: 0-9 then A-Z, rows top to bottom, 3 bits each
const int Glyphs[36] = int[](31599, 11415, 29671, 29647, 23497, 31183, 31215, 29257, 31727, 31695,
	11245, 27566, 14627, 27502, 31143, 31140, 14699, 23533, 29847, 4714, 23469, 18727, 24557, 27501, 11114,
	27556, 11123, 27565, 14478, 29842, 23407, 23402, 23549, 23213, 23186, 29351);

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

	return v;
}

float Lum(vec3 c)
{
	return dot(c, vec3(0.299, 0.587, 0.114));
}

// Cell state at a position in cell units (bilinear between cell centres)
vec4 Cells(vec2 c)
{
	return texture(CellMap, c / CellMapSize).bgra;
}

// Soft disc blur over ~0.8 cell: turns the stair-stepped cell grid into smooth curves
vec4 SmoothCells(vec2 c)
{
	vec4 s = Cells(c) * 0.2;
	for (int i = 0; i < 6; i++)
	{
		float a = float(i) * TAU / 6.0;
		s += Cells(c + 0.38 * vec2(cos(a), sin(a))) * 0.05;
	}

	for (int i = 0; i < 10; i++)
	{
		float a = (float(i) + 0.5) * TAU / 10.0;
		s += Cells(c + 0.78 * vec2(cos(a), sin(a))) * 0.05;
	}

	return s;
}

// Hex grid: x = distance to the nearest hex edge (0 on the edge, 0.5 at the centre), yz = hex id
vec3 Hex(vec2 p)
{
	const vec2 r = vec2(1.0, 1.7320508);
	vec2 h = r * 0.5;
	vec2 a = mod(p, r) - h;
	vec2 b = mod(p - h, r) - h;
	vec2 g = dot(a, a) < dot(b, b) ? a : b;
	vec2 q = abs(g);
	float d = max(dot(q, normalize(r)), q.x);
	return vec3(0.5 - d, p - g);
}

// Anti-aliased line from a distance field (d in the field's units, w = field units per pixel)
float Line(float d, float w, float width)
{
	return 1.0 - smoothstep(width * 0.5, width * 0.5 + w, d);
}

float Glyph(int glyph, vec2 p)
{
	if (p.x < 0.0 || p.y < 0.0 || p.x >= 3.0 || p.y >= 5.0)
		return 0.0;

	int bit = (4 - int(p.y)) * 3 + (2 - int(p.x));
	return float((Glyphs[glyph] >> bit) & 1);
}

// Grid reference like "C07" next to a major grid intersection
float Label(vec2 world, vec2 major, float glyphSize)
{
	vec2 id = floor(world / major);
	vec2 p = (world - id * major - vec2(5.0, 5.0)) / glyphSize;
	int col = int(mod(id.x, 26.0));
	int row = int(mod(id.y + 1.0, 100.0));
	float v = Glyph(10 + col, p);
	v += Glyph(row / 10, p - vec2(4.0, 0.0));
	v += Glyph(row - (row / 10) * 10, p - vec2(8.0, 0.0));
	return v;
}

// The Tactical "command table". edge = 0..1 closeness to the explored border, live = sweep/animation strength
vec3 Tactical(vec2 world, float px, float edge, float live, float h, float fh, float labels)
{
	float cell = TileSize.x;

	// Base: deep navy-charcoal with slow large-scale variation
	float macro = Fbm(world / (cell * 22.0));
	vec3 col = mix(vec3(0.028, 0.042, 0.072), vec3(0.050, 0.078, 0.122), macro);

	// Radar sweep around the map centre
	vec2 centre = (Bounds.xy + Bounds.zw) * 0.5;
	vec2 d = world - centre;
	float ang = atan(d.y, d.x);
	float sweep = mod(Time * TAU / SweepPeriod - ang, TAU);
	float trail = exp(-sweep * 2.4) * smoothstep(0.0, 0.015, sweep) * live;
	float leadDist = min(sweep, TAU - sweep) * length(d);
	float lead = (Line(leadDist, px, px * 1.5) + exp(-leadDist / (px * 7.0)) * 0.35) * live;
	float ping = fract(Time / SweepPeriod);
	float ring = Line(abs(length(d) - ping * length(Bounds.zw - Bounds.xy) * 0.6), px, px * 1.5) * (1.0 - ping) * 0.5 * live;
	float boost = 1.0 + 2.2 * trail;

	// Topographic contours (procedural terrain, unrelated to the real map)
	float cd = abs(fract(h - 0.5) - 0.5);
	float index = step(abs(mod(floor(h + 0.5), 5.0)), 0.5);
	float contour = Line(cd, fh, fh * mix(0.9, 1.8, index));
	col = mix(col, vec3(0.10, 0.22, 0.28) * boost, contour * mix(0.45, 0.8, index));

	// Hex grid
	vec2 hp = world / (cell * 1.25);
	vec3 hex = Hex(hp);
	float hw = px / (cell * 1.25);
	float hexLine = Line(hex.x, hw, hw * 1.1);
	float hr = Hash(hex.yz + 0.37);
	float twinkle = smoothstep(0.93, 1.0, hr) * (0.5 + 0.5 * sin(Time * (0.6 + hr * 1.7) + hr * 40.0));
	col += vec3(0.05, 0.10, 0.16) * twinkle * smoothstep(0.0, 0.08, hex.x) * 0.7;
	col = mix(col, vec3(0.09, 0.16, 0.25) * boost, hexLine * 0.75);

	// Major grid every 8 cells with coordinates
	// (counted from the playable area's top-left corner: A01)
	vec2 major = vec2(cell * 8.0);
	vec2 local = world - Bounds.xy;
	vec2 gd = abs(fract(local / major + 0.5) - 0.5) * major;
	float grid = max(Line(gd.x, px, px), Line(gd.y, px, px));
	float cross = step(min(gd.x, gd.y), px * 1.5) * step(max(gd.x, gd.y), cell * 0.45);
	col = mix(col, vec3(0.14, 0.24, 0.36) * boost, grid * 0.45 + cross * 0.5);
	float glyph = max(2.0, px * 1.0);
	col = mix(col, vec3(0.30, 0.46, 0.62) * boost, Label(local, major, glyph) * 0.6 * step(px, 2.5) * labels);

	// Sweep light
	col += HoloColor * (trail * 0.06 + lead * 0.3 + ring * 0.12);

	// Hex cells light up and dissolve along the explored border
	float dissolve = step(hr, edge * 1.25 - 0.15 + 0.12 * sin(Time * 2.3 + hr * 31.0));
	col = mix(col, BorderColor * 0.55, dissolve * edge * 0.55 * smoothstep(0.02, 0.12, hex.x));
	col = mix(col, BorderColor * 0.9, hexLine * edge * 0.5);
	col += BorderColor * edge * edge * 0.25;

	// Faint moving scanlines
	float scan = 0.94 + 0.06 * step(0.5, fract(gl_FragCoord.y / 3.0));
	scan += 0.05 * exp(-abs(fract(world.y / (cell * 30.0) - Time * 0.05) - 0.5) * 60.0);
	return col * scan;
}

// Out of bounds: darker table with diagonal hatching
vec3 OffMap(vec2 world, float px, float h, float fh)
{
	vec3 col = Tactical(world, px, 0.0, 0.0, h, fh, 0.0) * 0.5;
	float hatch = abs(fract((world.x + world.y) / (TileSize.x * 1.5)) - 0.5) * TileSize.x * 1.5;
	col = mix(col, vec3(0.06, 0.08, 0.11), Line(hatch, px, TileSize.x * 0.35) * 0.5);
	return col;
}

void main()
{
	vec3 world3 = texelFetch(WorldTexture, ivec2(gl_FragCoord.xy), 0).rgb;
	vec2 world = Scroll + gl_FragCoord.xy * Downscale;
	float px = Downscale;
	vec2 c = world / TileSize;

	// Organic, slowly breathing edge
	vec2 warp = vec2(Noise(c * 0.9 + Time * 0.07), Noise(c * 0.9 + vec2(9.1, 3.7) - Time * 0.06)) - 0.5;
	vec4 s = SmoothCells(c + warp * 0.35);
	float e = s.x;
	float v = s.y;
	float reveal = s.z;

	// Screen-pixel distance to the explored border (positive = explored side)
	float de = length(vec2(dFdx(e), dFdy(e))) + 1e-5;
	float sd = (e - 0.5) / de;
	float unexplored = 1.0 - smoothstep(-0.8, 0.8, sd);
	float dv = length(vec2(dFdx(v), dFdy(v))) + 1e-5;

	// Topographic contours (procedural terrain, unrelated to the real map); derivatives outside branches
	float topo = Fbm(world / (TileSize.x * 9.0) + vec2(17.3, 4.1)) * 14.0;
	float topoW = fwidth(topo);

	vec3 col = world3;

	// Fog of war: old information
	float fog = (1.0 - smoothstep(0.3, 0.7, v)) * step(0.001, e);
	if (fog > 0.0)
	{
		float l = Lum(world3);
		vec3 f = mix(vec3(l), world3, Fog.y) * Fog.x * FogTint;
		f += (Hash(gl_FragCoord.xy + floor(Time * 24.0)) - 0.5) * 0.035;
		vec3 hex = Hex(world / (TileSize.x * 1.25));
		f = mix(f, f + vec3(0.03, 0.06, 0.09), Line(hex.x, px / (TileSize.x * 1.25), px / (TileSize.x * 1.25)) * 0.5);
		col = mix(col, f, fog);

		// Dim inner border between visible and fogged ground
		float fogLine = Line(abs((v - 0.5) / dv), 1.0, 0.8) * smoothstep(0.75, 0.95, e);
		col = mix(col, BorderColor * 0.8, fogLine * 0.35);
		col += BorderColor * 0.05 * exp(-abs((v - 0.5) / dv) * 0.15) * smoothstep(0.75, 0.95, e);
	}

	// Explored ground darkens slightly toward the border (depth)
	col *= mix(0.55, 1.0, smoothstep(0.5, 0.9, e));

	// Reveal: hologram scan and hex cells fading out on newly explored ground
	if (reveal > 0.002)
	{
		vec3 hex = Hex(world / (TileSize.x * 1.25));
		float hw = px / (TileSize.x * 1.25);
		float hr = Hash(hex.yz + 0.37);
		float cellsOn = smoothstep(hr * 0.8, hr * 0.8 + 0.2, reveal);
		col = mix(col, col * 0.6 + HoloColor * 0.25, cellsOn * reveal * 0.8);
		col += HoloColor * Line(hex.x, hw, hw * 1.2) * reveal * 0.6;
		float scanY = abs(fract(c.y / 4.0) - (1.0 - reveal));
		col += HoloColor * exp(-scanY * 30.0) * reveal * 0.9;
	}

	// Unexplored: the tactical table, with the border glowing on both sides
	if (unexplored > 0.0)
		col = mix(col, Tactical(world, px, smoothstep(0.0, 0.5, e), 1.0, topo, topoW, 1.0), unexplored);

	float energy = 0.75 + 0.5 * Noise(world / (TileSize.x * 2.5) + vec2(Time * 0.9, -Time * 0.4));
	float border = Line(abs(sd), 1.0, 1.4);
	col += BorderColor * exp(-abs(sd) * 0.18) * 0.35 * energy;
	col = mix(col, mix(BorderColor, vec3(1.0, 0.85, 0.8), 0.35 * energy), border * 0.9);

	// Outside the playable area: darker hatched table and a bevelled frame
	vec2 q = max(Bounds.xy - world, world - Bounds.zw);
	float outside = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
	float op = outside / px;
	if (op > -1.0)
	{
		col = mix(col, OffMap(world, px, topo, topoW), smoothstep(-0.5, 0.5, op));
		// Metal bevel ~7 world pixels wide: lit on the top/left sides, a highlight ridge, red trim outside
		float width = max(7.0 / px, 4.0);
		float t = clamp(op / width, 0.0, 1.0);
		float bevel = (1.0 - smoothstep(width - 0.5, width + 0.5, op)) * smoothstep(-0.5, 0.5, op);
		float lightSide = clamp(step(world.x, Bounds.x) + step(world.y, Bounds.y), 0.0, 1.0);
		vec3 steel = mix(vec3(0.16, 0.18, 0.21), vec3(0.38, 0.41, 0.46), lightSide);
		steel *= 0.75 + 0.55 * exp(-pow((t - 0.35) * 4.0, 2.0)) - 0.25 * t;
		col = mix(col, steel, bevel);
		col = mix(col, BorderColor * 0.9, Line(abs(op - width - 1.0), 1.0, 1.2) * 0.85);
		col += BorderColor * 0.12 * exp(-max(op - width, 0.0) / (width * 1.5)) * step(width, op);
		col = mix(col, vec3(0.01), Line(abs(op), 1.0, 1.2) * 0.7);
	}

	fragColor = vec4(col, 1.0);
}
