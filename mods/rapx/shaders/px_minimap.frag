#version {VERSION}
#ifdef GL_ES
precision highp float;
precision highp int;
#endif

// RedAlert Project X - high-end tactical minimap.
// Draws over the whole stock radar panel at full screen resolution:
//  - terrain upscaled with Catmull-Rom filtering, tactical grade and relief shading
//  - units and buildings as crisp rounded blips (metaballs over the cell grid) with bloom, flaring under the sweep
//  - the Tactical shroud of PxShroudRenderer (shared cell map: same fades and reveals as the main view)
//  - the area beside a non-wide map as a styled table with a frame line, radar sweep, range rings,
//    scanlines, vignette and the camera frame
// Terrain is never drawn under the shroud.

uniform sampler2D Radar;     // stock radar sheet: terrain and actor layers, one texel per cell
uniform vec4 TerrainRect;    // texels: x, y, w, h
uniform vec4 ActorRect;
uniform sampler2D CellMap;   // PxShroudRenderer: .bgra = (explored, visible, reveal, inside map)
uniform vec2 CellMapSize;
uniform float HasShroud;     // 0 = everything visible (observers)
uniform vec4 Bounds;         // playable cells: left, top, width, height
uniform vec2 PanelSize;      // radar panel in UI pixels
uniform vec4 MapRect;        // map area inside the panel (UI pixels): x, y, w, h
uniform vec4 View;           // camera rectangle in map UVs: left, top, right, bottom
uniform float Time;
uniform float SweepPeriod;
uniform vec3 BorderColor;
uniform vec3 SweepColor;

in vec2 vUV;
out vec4 fragColor;

const float TAU = 6.2831853;

float Hash(vec2 p)
{
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float Lum(vec3 c)
{
	return dot(c, vec3(0.299, 0.587, 0.114));
}

vec4 Fetch(vec4 rect, vec2 t)
{
	vec2 c = clamp(t, rect.xy, rect.xy + rect.zw - 1.0);
	return texelFetch(Radar, ivec2(c), 0);
}

vec3 Row(vec4 rect, vec2 t, vec2 wx0, vec2 wx1)
{
	return Fetch(rect, t + vec2(-1.0, 0.0)).rgb * wx0.x + Fetch(rect, t).rgb * wx0.y
		+ Fetch(rect, t + vec2(1.0, 0.0)).rgb * wx1.x + Fetch(rect, t + vec2(2.0, 0.0)).rgb * wx1.y;
}

// Catmull-Rom upscale (p in texels relative to the rect; texel centres at +0.5)
vec3 Bicubic(vec4 rect, vec2 p)
{
	vec2 q = p - 0.5;
	vec2 i = floor(q);
	vec2 f = q - i;
	vec2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
	vec2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
	vec2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
	vec2 w3 = f * f * (-0.5 + 0.5 * f);
	vec2 b = rect.xy + i;
	vec2 wx0 = vec2(w0.x, w1.x);
	vec2 wx1 = vec2(w2.x, w3.x);
	vec3 c = Row(rect, b + vec2(0.0, -1.0), wx0, wx1) * w0.y + Row(rect, b, wx0, wx1) * w1.y
		+ Row(rect, b + vec2(0.0, 1.0), wx0, wx1) * w2.y + Row(rect, b + vec2(0.0, 2.0), wx0, wx1) * w3.y;
	return clamp(c, 0.0, 1.0);
}

vec3 Bilinear(vec4 rect, vec2 p)
{
	vec2 q = p - 0.5;
	vec2 i = floor(q);
	vec2 f = q - i;
	vec2 b = rect.xy + i;
	return mix(mix(Fetch(rect, b).rgb, Fetch(rect, b + vec2(1.0, 0.0)).rgb, f.x),
		mix(Fetch(rect, b + vec2(0.0, 1.0)).rgb, Fetch(rect, b + vec2(1.0, 1.0)).rgb, f.x), f.y);
}

// Edge-directed upscale: blur the cells, then snap to the closest of the four surrounding cell colours. Boundaries
// follow the blurred field's smooth contours, so stair-stepped cell edges become crisp curves (anti-aliased).
vec3 VectorTerrain(vec4 rect, vec2 p, out vec3 blurred)
{
	vec3 b = Bilinear(rect, p) * 0.25;
	for (int i = 0; i < 8; i++)
	{
		float a = float(i) * TAU / 8.0;
		b += Bilinear(rect, p + 0.75 * vec2(cos(a), sin(a))) * 0.09375;
	}

	blurred = b;
	vec2 base = rect.xy + floor(p - 0.5);
	vec3 c0 = Fetch(rect, base).rgb;
	vec3 c1 = Fetch(rect, base + vec2(1.0, 0.0)).rgb;
	vec3 c2 = Fetch(rect, base + vec2(0.0, 1.0)).rgb;
	vec3 c3 = Fetch(rect, base + vec2(1.0, 1.0)).rgb;
	float d0 = distance(c0, b);
	float d1 = distance(c1, b);
	float d2 = distance(c2, b);
	float d3 = distance(c3, b);

	// Best and second-best candidates
	vec3 best = c0;
	float db = d0;
	vec3 second = c1;
	float ds = d1;
	if (d1 < db) { second = best; ds = db; best = c1; db = d1; }
	if (d2 < db) { second = best; ds = db; best = c2; db = d2; } else if (d2 < ds) { second = c2; ds = d2; }
	if (d3 < db) { second = best; ds = db; best = c3; db = d3; } else if (d3 < ds) { second = c3; ds = d3; }

	float ratio = db / max(db + ds, 1e-4);
	float w = fwidth(ratio) * 1.5 + 1e-3;
	// ratio reaches 0.5 where the two closest colours tie: that is the boundary
	return mix(best, second, smoothstep(0.5 - w, 0.5, ratio) * 0.5);
}

vec4 Cells(vec2 c)
{
	return texture(CellMap, c / CellMapSize).bgra;
}

vec4 SmoothCells(vec2 c)
{
	vec4 s = Cells(c) * 0.28;
	for (int i = 0; i < 8; i++)
	{
		float a = float(i) * TAU / 8.0;
		s += Cells(c + 0.7 * vec2(cos(a), sin(a))) * 0.09;
	}

	return s;
}

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

float Line(float d, float w, float width)
{
	return 1.0 - smoothstep(width * 0.5, width * 0.5 + w, d);
}

void main()
{
	vec2 ppx = vUV * PanelSize;
	vec2 uv = (ppx - MapRect.xy) / MapRect.zw;
	vec2 cuv = clamp(uv, 0.0, 1.0);
	vec2 cell = Bounds.xy + cuv * Bounds.zw;
	vec2 tp = cuv * TerrainRect.zw;
	float texelPx = MapRect.z / TerrainRect.z;  // UI pixels per cell
	float aa = fwidth(ppx.x);

	// Inside the map area (signed distance in UI pixels, negative inside)
	vec2 mq = abs(ppx - (MapRect.xy + MapRect.zw * 0.5)) - MapRect.zw * 0.5;
	float mapDist = length(max(mq, 0.0)) + min(max(mq.x, mq.y), 0.0);
	float inside = 1.0 - smoothstep(-aa, aa, mapDist);

	// Terrain: smooth upscale, cooled grade, relief from luminance slopes (per cell)
	vec3 blurred;
	vec3 terrain = VectorTerrain(TerrainRect, tp, blurred);
	float l0 = Lum(terrain);
	float lb = Lum(blurred);
	float lx = Lum(Bilinear(TerrainRect, tp + vec2(0.6, 0.0)));
	float ly = Lum(Bilinear(TerrainRect, tp + vec2(0.0, 0.6)));
	vec3 col = mix(vec3(l0), terrain, 0.82) * vec3(0.93, 1.0, 1.05);
	col *= 1.0 + clamp(((lb - lx) + (lb - ly)) * 1.0, -0.22, 0.22);
	col = pow(col, vec3(1.08)) * 1.06;

	// Fine detail grain at screen resolution
	col *= 0.97 + 0.06 * Hash(floor(ppx * 1.5));

	// Map grid every 8 cells (matches the A01 references in the main view)
	vec2 g = abs(fract((cell - Bounds.xy) / 8.0 + 0.5) - 0.5) * 8.0;
	vec2 gw = fwidth(cell);
	float grid = max(Line(g.x, gw.x, gw.x * 0.8), Line(g.y, gw.y, gw.y * 0.8));
	col = mix(col, vec3(0.55, 0.85, 1.0), grid * 0.1);

	// Shroud state (derivatives taken before any branch)
	vec4 s = HasShroud > 0.5 ? SmoothCells(cell) : vec4(1.0, 1.0, 0.0, 1.0);
	float e = s.x;
	float v = s.y;
	float de = length(vec2(dFdx(e), dFdy(e))) + 1e-5;
	float sd = (e - 0.5) / de;
	float unexplored = 1.0 - smoothstep(-0.7, 0.7, sd);

	// Radar sweep around the panel centre
	vec2 d = ppx - PanelSize * 0.5;
	float ang = atan(d.y, d.x);
	float sweep = mod(Time * TAU / SweepPeriod - ang, TAU);
	float trail = exp(-sweep * 3.0) * smoothstep(0.0, 0.01, sweep);
	float beamDist = min(sweep, TAU - sweep) * length(d);
	float beam = Line(beamDist, aa, 1.1) + exp(-beamDist / 5.0) * 0.3;

	// Fog of war: dim, cool, desaturated
	float fog = 1.0 - smoothstep(0.3, 0.7, v);
	col = mix(col, mix(vec3(Lum(col)), col, 0.35) * vec3(0.42, 0.48, 0.58), fog);

	// Blips: rounded metaballs over the actor cells, with bloom
	vec2 base = floor(tp);
	float field = 0.0;
	float halo = 0.0;
	vec3 blipCol = vec3(0.0);
	vec3 haloCol = vec3(0.0);
	for (int y = -2; y <= 2; y++)
	{
		for (int x = -2; x <= 2; x++)
		{
			vec2 t = base + vec2(float(x), float(y));
			vec4 a = Fetch(ActorRect, ActorRect.xy + t);
			vec2 dd = tp - (t + 0.5);
			float d2 = dot(dd, dd);
			float wgt = a.a * exp(-d2 * 2.2);
			field += wgt;
			blipCol += a.rgb * wgt;
			float hw = a.a * exp(-d2 * 0.7);
			halo += hw;
			haloCol += a.rgb * hw;
		}
	}

	blipCol /= max(field, 1e-4);
	haloCol /= max(halo, 1e-4);
	float fw = fwidth(field) + 1e-4;
	float blip = smoothstep(0.42 - fw, 0.42 + fw, field);
	float outline = smoothstep(0.12, 0.42, field) * (1.0 - blip);
	float flare = 1.0 + 2.5 * trail;
	col = mix(col, vec3(0.02, 0.03, 0.05), outline * 0.6);
	col += haloCol * min(halo, 1.5) * 0.22 * flare;
	col = mix(col, blipCol * 1.2 + vec3(0.15) * smoothstep(1.0, 1.8, field), blip);

	// Unexplored: Tactical navy with a hex lattice and a red glowing border
	vec3 hex = Hex(ppx / 6.0);
	float hexLine = Line(hex.x, aa / 6.0, 0.1);
	float hr = Hash(hex.yz);
	float twinkle = smoothstep(0.9, 1.0, hr) * (0.5 + 0.5 * sin(Time * 1.3 + Hash(hex.yz + 3.1) * 30.0));
	vec3 tactical = mix(vec3(0.030, 0.046, 0.078), vec3(0.046, 0.072, 0.115), vUV.y);
	tactical += vec3(0.04, 0.08, 0.13) * twinkle * 0.5;
	tactical = mix(tactical, vec3(0.08, 0.14, 0.22), hexLine * 0.7);
	tactical += SweepColor * trail * 0.08;
	vec3 shrouded = mix(tactical, BorderColor * 0.5, smoothstep(0.0, 0.5, e) * 0.35);
	col = mix(col, shrouded, unexplored);
	col += BorderColor * exp(-abs(sd) / max(texelPx * 0.6, 1.0)) * 0.4 * HasShroud;
	col = mix(col, BorderColor * 1.1, Line(abs(sd), 1.0, 1.0) * 0.9 * HasShroud);

	// Beside the map: darker table with hatching and a thin frame line around the map
	float hatch = abs(fract((ppx.x + ppx.y) / 9.0) - 0.5) * 9.0;
	vec3 outside = tactical * 0.55;
	outside = mix(outside, vec3(0.05, 0.07, 0.10), Line(hatch, aa, 2.5) * 0.6);
	col = mix(outside, col, inside);
	col = mix(col, vec3(0.30, 0.42, 0.52), Line(abs(mapDist - 0.5), aa, 1.0) * 0.8);

	// Range rings, crosshair and sweep beam
	float r = length(d) / (PanelSize.y * 0.5);
	float rings = Line(abs(fract(r * 3.0 + 0.5) - 0.5) / 3.0 * PanelSize.y * 0.5, aa, 0.8) * step(r, 2.0);
	float cross = max(Line(abs(d.x), aa, 0.8), Line(abs(d.y), aa, 0.8));
	col += SweepColor * (rings * 0.06 + cross * 0.04);
	col += SweepColor * (trail * 0.09 + beam * 0.45);

	// Camera frame: thin outline, bright corner brackets, faint fill
	vec2 vtl = MapRect.xy + View.xy * MapRect.zw;
	vec2 vbr = MapRect.xy + View.zw * MapRect.zw;
	vec2 vc = (vtl + vbr) * 0.5;
	vec2 vh = (vbr - vtl) * 0.5;
	vec2 vq = abs(ppx - vc) - vh;
	float vd = length(max(vq, 0.0)) + min(max(vq.x, vq.y), 0.0);
	float vin = 1.0 - smoothstep(-aa, aa, vd);
	vec2 corner = vh - abs(ppx - vc);
	float bracket = step(min(corner.x, corner.y), 1.0) * step(max(corner.x, corner.y), min(vh.x, vh.y) * 0.4 + 1.0);
	col += vec3(1.0) * vin * 0.05;
	col = mix(col, vec3(0.92, 0.97, 1.0), Line(abs(vd), aa, 0.8) * mix(0.45, 1.0, bracket));
	col = mix(col, vec3(1.0), Line(abs(vd + 0.6), aa, 1.4) * bracket * 0.85);

	// Display: fine scanlines, vignette, faint noise
	col *= 0.965 + 0.035 * step(0.5, fract(gl_FragCoord.y / 3.0));
	vec2 vg = (vUV - 0.5) * 2.0;
	col *= 1.0 - 0.3 * pow(clamp(dot(vg, vg) * 0.5, 0.0, 1.0), 1.5);
	col += (Hash(gl_FragCoord.xy + floor(Time * 20.0)) - 0.5) * 0.015;

	fragColor = vec4(col, 1.0);
}
