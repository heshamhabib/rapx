#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// RedAlert Project X - drifting cloud shadows over the whole battlefield (terrain, buildings and units).
// Procedural: a few octaves of value noise in world space, scrolled by the wind.
// PERF: outputs only the shadow's colour multiplier; it is drawn with multiplicative blending (dst * src), so the pass
// needs no copy of the world image. Black (outside the map) stays black on its own.

uniform vec2 Scroll;        // world pixel at the buffer origin
uniform float Downscale;    // world pixels per buffer pixel
uniform vec2 Offset;        // cloud drift so far (world pixels)
uniform float CloudSize;    // world pixels per noise unit (largest octave)
uniform float Cover;        // 0..1, share of the sky covered
uniform float Strength;     // darkness of a full shadow (0..1)
uniform vec3 ShadowTint;    // colour multiplier inside the shadow

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

float Clouds(vec2 p)
{
	float v = 0.0;
	float a = 0.55;
	for (int i = 0; i < 4; i++)
	{
		v += a * Noise(p);
		p = mat2(1.6, 1.2, -1.2, 1.6) * p + vec2(3.1, 1.7);
		a *= 0.5;
	}

	return v;
}

void main()
{
	vec2 world = Scroll + gl_FragCoord.xy * Downscale;
	if (Hidden(world))
	{
		fragColor = vec4(1.0);
		return;
	}

	// The 4-octave noise sits around 0.42 +- 0.15; spread it to roughly 0..1 so Cover is the covered share
	float density = (Clouds((world - Offset) / CloudSize) - 0.42) / 0.30 + 0.5;
	float threshold = 1.0 - Cover;
	float shadow = smoothstep(threshold - 0.12, threshold + 0.22, density) * Strength;
	fragColor = vec4(mix(vec3(1.0), ShadowTint, shadow), 1.0);
}
