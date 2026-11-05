#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// RedAlert Project X - HD terrain detail pass.
// Runs after the classic terrain tiles are drawn (before resources, smudges and actors).
// Each pixel is classified as grass / dirt / rock / water from a blurred neighbourhood of
// the classic terrain, then re-rendered with photo-scanned textures sampled in world space.
// The look is prototyped in artsrc/terrain/prototype.py - keep the constants in sync.

uniform sampler2D WorldTexture;
uniform sampler2D GrassTexture;
uniform sampler2D DirtTexture;
uniform sampler2D RockTexture;
uniform sampler2D RoughTexture;
uniform sampler2D BeachTexture;
uniform sampler2D WaterTexture;
uniform sampler2D RiverTexture;

// One texel per map cell: (rough, beach, water, river) membership of the cell's terrain type, read as .bgra
uniform sampler2D CellMap;
uniform vec2 CellMapSize;
uniform float TileSize;
uniform float Time;          // seconds, drives the water drift
uniform float WaterFlow;     // world pixels per second
uniform float WaterDetail;   // < 0: keep the classic water
uniform float WaterGlints;   // brightness of the sun glints on HD water
uniform vec4 Repeat2;        // world pixels per repeat (rough, beach, water, river)
uniform vec3 RoughGain;
uniform float RockLum;       // mean luminance of the classic rock (cliff) colour
uniform float RockDetail;    // 0: classic cliff art with grain; 1: HD cliff texture lit by the classic light/dark faces
uniform vec3 WaterGain;
uniform vec3 RiverGain;

uniform vec2 Scroll;        // world pixel at the buffer origin
uniform float Downscale;    // world pixels per buffer pixel
uniform vec3 Repeat;        // world pixels per texture repeat (grass, dirt, rock)
uniform vec3 MeanLum;       // mean luminance of the grass, dirt, rock textures
uniform float ShadeStrength;
uniform float GroundLum;    // mean luminance of the classic ground (the grass shading reference)
uniform vec3 GroundGain;    // per-channel recolour of the grass texture (GroundTint)
uniform float EdgeWarp;     // world pixels the ground/dirt border is wobbled by (0 = classic cell-aligned borders)

// Mode 0: temperate rules (green = grass, bright = rock, blue = water, the rest dirt).
// Mode 1: nearest classic reference colours, RefN = (r, g, b, class 0 grass / 1 dirt / 2 rock / 3 water, -1 unused).
uniform float Mode;
uniform float Softness;
uniform vec4 Ref0;
uniform vec4 Ref1;
uniform vec4 Ref2;
uniform vec4 Ref3;
uniform vec4 Ref4;
uniform vec4 Ref5;
uniform vec4 Ref6;
uniform vec4 Ref7;

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

const vec3 LUMA = vec3(0.299, 0.587, 0.114);

vec3 World(vec2 worldOffset)
{
	ivec2 size = textureSize(WorldTexture, 0);
	ivec2 p = ivec2(gl_FragCoord.xy + worldOffset / Downscale);
	return texelFetch(WorldTexture, clamp(p, ivec2(0), size - ivec2(1)), 0).rgb;
}

// Gaussian-ish neighbourhood average (sigma ~1.1 world pixels) so the speckled classic grass averages out
vec3 Blurred(vec2 o)
{
	vec3 c = World(o) * 0.12;
	c += (World(o + vec2(1.0, 0.0)) + World(o + vec2(-1.0, 0.0)) + World(o + vec2(0.0, 1.0)) + World(o + vec2(0.0, -1.0))) * 0.10;
	c += (World(o + vec2(1.0, 1.0)) + World(o + vec2(-1.0, 1.0)) + World(o + vec2(1.0, -1.0)) + World(o + vec2(-1.0, -1.0))) * 0.07;
	c += (World(o + vec2(2.0, 0.0)) + World(o + vec2(-2.0, 0.0)) + World(o + vec2(0.0, 2.0)) + World(o + vec2(0.0, -2.0))) * 0.04;
	return c / 0.96;
}

// Wider neighbourhood for the reference-colour classification: dithered classic ground (desert sand,
// snow) has single light and dark pixels that would otherwise read as road or rock specks
vec3 BlurredWide(vec3 centre, vec2 o)
{
	vec3 ring3 = World(o + vec2(3.0, 0.0)) + World(o + vec2(-3.0, 0.0)) + World(o + vec2(0.0, 3.0)) + World(o + vec2(0.0, -3.0))
		+ World(o + vec2(2.0, 2.0)) + World(o + vec2(-2.0, 2.0)) + World(o + vec2(2.0, -2.0)) + World(o + vec2(-2.0, -2.0));
	vec3 ring6 = World(o + vec2(6.0, 0.0)) + World(o + vec2(-6.0, 0.0)) + World(o + vec2(0.0, 6.0)) + World(o + vec2(0.0, -6.0))
		+ World(o + vec2(4.0, 4.0)) + World(o + vec2(-4.0, 4.0)) + World(o + vec2(4.0, -4.0)) + World(o + vec2(-4.0, -4.0));
	return centre * 0.4 + ring3 * (0.35 / 8.0) + ring6 * (0.25 / 8.0);
}

// Bilinear interpolation between classic world pixels: smooth upscaling that keeps the
// classic sprite's form (rock faces, shadows) without the blocky pixels
vec3 WorldBilinear(vec2 world)
{
	vec2 p = world - vec2(0.5);
	vec2 f = fract(p);
	vec2 base = floor(p) + vec2(0.5) - world;
	vec3 a = World(base);
	vec3 b = World(base + vec2(1.0, 0.0));
	vec3 c = World(base + vec2(0.0, 1.0));
	vec3 d = World(base + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float Lum(vec3 c)
{
	return dot(c, LUMA);
}

float Hash(vec2 p)
{
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float ValueNoise(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(Hash(i), Hash(i + vec2(1.0, 0.0)), u.x), mix(Hash(i + vec2(0.0, 1.0)), Hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float RefDistance(vec4 r, vec3 c)
{
	vec3 d = c - r.rgb;
	return r.a < 0.0 ? 1e6 : dot(d, d);
}

vec4 RefWeight(vec4 r, vec3 c, float nearest)
{
	if (r.a < 0.0)
		return vec4(0.0);

	// Soft-min over the reference colours: the nearest ones win, close calls blend
	float w = exp(-(RefDistance(r, c) - nearest) / (2.0 * Softness * Softness));
	return w * vec4(r.a < 0.5 ? 1.0 : 0.0, abs(r.a - 1.0) < 0.5 ? 1.0 : 0.0,
		abs(r.a - 2.0) < 0.5 ? 1.0 : 0.0, r.a > 2.5 ? 1.0 : 0.0);
}

// (grass, dirt, rock, water) weights from the reference colours
vec4 ClassifyByReference(vec3 c)
{
	float nearest = min(min(min(RefDistance(Ref0, c), RefDistance(Ref1, c)), min(RefDistance(Ref2, c), RefDistance(Ref3, c))),
		min(min(RefDistance(Ref4, c), RefDistance(Ref5, c)), min(RefDistance(Ref6, c), RefDistance(Ref7, c))));
	vec4 w = RefWeight(Ref0, c, nearest) + RefWeight(Ref1, c, nearest) + RefWeight(Ref2, c, nearest) + RefWeight(Ref3, c, nearest)
		+ RefWeight(Ref4, c, nearest) + RefWeight(Ref5, c, nearest) + RefWeight(Ref6, c, nearest) + RefWeight(Ref7, c, nearest);
	return w / max(w.x + w.y + w.z + w.w, 1e-6);
}

void main()
{
	vec2 world = Scroll + gl_FragCoord.xy * Downscale;
	vec3 original = World(vec2(0.0));
	if (Hidden(world))
	{
		fragColor = vec4(original, 1.0);
		return;
	}

	vec3 C = Blurred(vec2(0.0));
	float v = max(C.r, max(C.g, C.b));

	// Outside the map (black) is left untouched
	if (max(original.r, max(original.g, original.b)) < 0.02 && v < 0.03)
	{
		fragColor = vec4(original, 1.0);
		return;
	}

	vec3 Cw = BlurredWide(C, vec2(0.0));

	// Blocky road / sand tile layouts: the grass/dirt split and the ground shading are read from a noise-warped,
	// wider neighbourhood so the borders between the classic cells become organic instead of square
	vec3 Cg = C;
	vec3 Cgw = Cw;
	if (EdgeWarp > 0.0)
	{
		vec2 n1 = vec2(ValueNoise(world / 22.0), ValueNoise(world / 22.0 + vec2(31.7, 11.3))) - 0.5;
		vec2 n2 = vec2(ValueNoise(world / 9.0 + vec2(5.1, 47.9)), ValueNoise(world / 9.0 + vec2(63.2, 2.7))) - 0.5;
		vec2 warp = (n1 * 1.5 + n2 * 0.5) * EdgeWarp;
		Cg = Blurred(warp);
		vec3 ring = World(warp + vec2(9.0, 0.0)) + World(warp + vec2(-9.0, 0.0)) + World(warp + vec2(0.0, 9.0))
			+ World(warp + vec2(0.0, -9.0)) + World(warp + vec2(6.0, 6.0)) + World(warp + vec2(-6.0, 6.0))
			+ World(warp + vec2(6.0, -6.0)) + World(warp + vec2(-6.0, -6.0));
		Cgw = BlurredWide(Cg, warp) * 0.6 + ring * (0.4 / 8.0);
	}

	float water, rock, grass, dirt;
	if (Mode < 0.5)
	{
		float green = (C.g - (C.r + C.b) * 0.5) / (v + 0.02);
		float blue = (C.b - (C.r + C.g) * 0.5) / (v + 0.02);

		water = smoothstep(0.10, 0.22, blue) * smoothstep(0.30, 0.42, v);
		rock = smoothstep(0.33, 0.45, v) * (1.0 - water);
		grass = smoothstep(0.03, 0.14, green) * (1.0 - water) * (1.0 - rock);

		// Dark, desaturated areas are shadows (e.g. beside cliffs), not dirt: render them as shaded grass
		dirt = clamp(1.0 - water - rock - grass, 0.0, 1.0) * smoothstep(0.17, 0.24, v);
		grass = clamp(1.0 - water - rock - dirt, 0.0, 1.0);
	}
	else
	{
		vec4 w = ClassifyByReference(Cw);
		rock = w.z;
		water = w.w;

		// Rock and water keep their exact classic outline; the rest is split into ground and dirt from the warped sample
		vec4 g = EdgeWarp > 0.0 ? ClassifyByReference(Cgw) : w;
		float split = g.y / max(g.x + g.y, 1e-6);
		float land = w.x + w.y;
		grass = land * (1.0 - split);
		dirt = land * split;
	}

	// Grass: two differently scaled/rotated samples hide the texture repeat, plus slow macro variation
	vec3 cg = texture(GrassTexture, world / Repeat.x).rgb;
	vec2 rotated = mat2(0.6, -0.8, 0.8, 0.6) * world;
	vec3 cg2 = texture(GrassTexture, rotated / (Repeat.x * 2.7)).rgb;
	float macro = smoothstep(0.2, 0.8, Lum(texture(DirtTexture, world / vec2(24.0 * 23.0, 24.0 * 19.0)).rgb) * 2.2);
	cg = (cg * (0.8 + 0.2 * macro) * 0.5 + cg2 * 0.5) * GroundGain;

	vec3 cd = texture(DirtTexture, world / Repeat.y).rgb;
	vec3 cr = texture(RockTexture, world / Repeat.z).rgb;

	// Terrain type of the surrounding cells: rough, beach, water, river (bilinear, so materials blend at cell edges)
	vec4 cells = texture(CellMap, (world / TileSize) / CellMapSize).bgra;

	// Water only where the map has water (sea, river, beach or bridge cells): dark blue-grey shadows along cliffs
	// would otherwise be drawn as water. Their weight goes to rock.
	if (WaterDetail >= 0.0)
	{
		float allowed = clamp((cells.y + cells.z + cells.w) * 4.0, 0.0, 1.0);
		rock += water * (1.0 - allowed);
		water *= allowed;
	}

	// Local light and dark of the classic art relative to its neighbourhood (keeps wet sand edges, ruts, waves)
	float localShade = clamp(Lum(C) / max(Lum(Cw), 0.02), 0.65, 1.35);

	// Rocks and dirt keep the classic form and take surface detail from the photo texture
	// Rocks: the classic sprite carries the 3D form; the photo adds only fine surface detail
	vec3 smoothed = WorldBilinear(world);
	vec3 classicRock = smoothed * mix(1.0, Lum(cr) / MeanLum.z, 0.5) * 1.08;

	// HD cliff: the cliff texture (two scales against visible repeats) lit by the classic art's light and dark faces,
	// taken from the slightly blurred classic so its pixel blocks don't show
	vec3 rockTex = cr * 0.65 + texture(RockTexture, rotated / (Repeat.z * 1.9)).rgb * 0.35;
	float form = clamp(Lum(mix(smoothed, C, 0.6)) / RockLum, 0.25, 1.9);
	cr = mix(classicRock, rockTex * form * (MeanLum.z > 0.0 ? RockLum / MeanLum.z : 1.0), RockDetail);
	cd = Cg * (Lum(cd) / MeanLum.y) * 1.2 * 0.45 + cd * 0.44;

	// Rough ground replaces grass and dirt in Rough cells
	vec3 cro = texture(RoughTexture, world / Repeat2.x).rgb * 0.6 + texture(RoughTexture, rotated / (Repeat2.x * 2.3)).rgb * 0.4;
	cro *= RoughGain;
	cg = mix(cg, cro, cells.x);
	cd = mix(cd, cro * localShade, cells.x);

	// Height blend: each material's own brightness decides which wins at the boundaries
	float wg = pow(grass * (Lum(cg) + 0.6), 6.0);
	float wd = pow(dirt * (Lum(cd) + 0.6), 6.0);
	float wr = pow(rock * (Lum(cr) + 0.6), 6.0);
	float total = wg + wd + wr + 1e-6;

	// Grass keeps the classic large-scale light and shadow (darker patches, cliff shadows)
	float ratio = clamp(Lum(Cg) / GroundLum, 0.45, 1.35);
	cg *= 1.0 + ShadeStrength * (ratio - 1.0);

	vec3 hd = (cg * wg + cd * wd + cr * wr) / total;

	// Beach cells: all land is sand, shaded by the classic art (wet edges, dunes)
	vec3 cb = texture(BeachTexture, world / Repeat2.y).rgb * 0.6 + texture(BeachTexture, rotated / (Repeat2.y * 2.1)).rgb * 0.4;
	hd = mix(hd, cb * localShade, cells.y);

	// Water: two drifting layers of the water (or river) texture, carrying the classic water's waves and foam
	vec3 wc = C;
	if (WaterDetail >= 0.0)
	{
		vec2 drift = vec2(Time * WaterFlow);
		mat2 turn = mat2(0.8, -0.6, 0.6, 0.8);
		vec3 sea = texture(WaterTexture, (world + drift * vec2(1.0, 0.6)) / Repeat2.z).rgb * 0.5
			+ texture(WaterTexture, (turn * world - drift * vec2(0.7, -0.9)) / (Repeat2.z * 1.37)).rgb * 0.5;
		vec3 river = texture(RiverTexture, (world + drift * vec2(1.6, 1.0)) / Repeat2.w).rgb * 0.5
			+ texture(RiverTexture, (turn * world + drift * vec2(1.1, -1.4)) / (Repeat2.w * 1.29)).rgb * 0.5;
		float riverShare = cells.w / max(cells.z + cells.w, 1e-3);
		float waveShade = clamp(Lum(C) / max(Lum(Cw), 0.02), 0.5, 1.6);
		wc = mix(sea * WaterGain, river * RiverGain, riverShare) * mix(1.0, waveShade, WaterDetail);

		// Sun glints: two noise fields drifting against each other; only where both peak does a glint flash
		// (~0.2% of the water), gathered in slowly wandering patches where the sun catches the waves
		vec2 gp = world * 0.42;
		float n = ValueNoise(gp + vec2(Time * 1.1, -Time * 0.7)) * ValueNoise(gp * 1.63 + vec2(-Time * 0.9, Time * 1.3) + 17.0);
		float sunPatch = smoothstep(0.35, 0.75, ValueNoise(world / 300.0 + vec2(Time * 0.02, Time * 0.013)));
		wc += smoothstep(0.7, 0.88, n) * sunPatch * WaterGlints * vec3(1.0, 0.97, 0.88);
	}

	fragColor = vec4(mix(hd, wc, water), 1.0);
}
