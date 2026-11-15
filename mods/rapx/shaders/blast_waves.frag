#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// RedAlert Project X - pressure waves of the HD explosions (PxBlastWaves), drawn over the world view.
// Shock fronts (kind 0): a thin ring racing out over the ground that bends the picture outwards, like a lens, with a
// bright crest. Heat (kind 1): the hot air over a fireball shimmers for a moment. Pixels no wave touches are left
// alone (discard), so the pass only costs where something is exploding.

uniform sampler2D WorldTexture;
uniform vec2 Scroll;        // world pixel at the buffer origin
uniform float Downscale;    // world pixels per buffer pixel
uniform float Time;         // seconds

// Wave: centre (world px), radius, width. Params: strength (world px), kind, age 0..1
uniform vec4 Wave0, Wave1, Wave2, Wave3, Wave4, Wave5, Wave6, Wave7;
uniform vec4 WaveParams0, WaveParams1, WaveParams2, WaveParams3, WaveParams4, WaveParams5, WaveParams6, WaveParams7;

out vec4 fragColor;

// The ground plane is foreshortened: a circle on it is this much flatter on screen
const float Squash = 0.6;

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

void Wave(vec4 w, vec4 p, vec2 world, inout vec2 disp, inout float bright, inout float mask)
{
	if (p.x <= 0.0)
		return;

	vec2 d = world - w.xy;
	if (p.y < 0.5)
	{
		d.y /= Squash;
		float r = length(d) + 0.001;
		vec2 n = d / r;
		float band = exp(-pow((r - w.z) / w.w, 2.0));
		if (band < 0.002)
			return;

		// Compressed air just behind the front: the picture is pulled outwards and the crest catches the light
		disp += -n * vec2(1.0, Squash) * band * p.x;
		bright += band * p.x * 0.014 * (1.0 - p.z);
		mask += band;
	}
	else
	{
		float r = length(d);
		float m = smoothstep(w.z, w.z * 0.3, r);
		if (m < 0.002)
			return;

		vec2 sh = vec2(Noise(world / 13.0 + vec2(0.0, -Time * 3.0)) - 0.5, Noise(world / 10.0 + vec2(Time * 2.1, 3.1)) - 0.5);
		disp += sh * p.x * m * 2.0;
		mask += m;
	}
}

void main()
{
	vec2 fc = gl_FragCoord.xy;
	vec2 world = Scroll + fc * Downscale;
	vec2 disp = vec2(0.0);
	float bright = 0.0;
	float mask = 0.0;

	Wave(Wave0, WaveParams0, world, disp, bright, mask);
	Wave(Wave1, WaveParams1, world, disp, bright, mask);
	Wave(Wave2, WaveParams2, world, disp, bright, mask);
	Wave(Wave3, WaveParams3, world, disp, bright, mask);
	Wave(Wave4, WaveParams4, world, disp, bright, mask);
	Wave(Wave5, WaveParams5, world, disp, bright, mask);
	Wave(Wave6, WaveParams6, world, disp, bright, mask);
	Wave(Wave7, WaveParams7, world, disp, bright, mask);

	if (mask < 0.004)
		discard;

	vec2 bufferSize = vec2(textureSize(WorldTexture, 0));
	vec4 src = texture(WorldTexture, (fc + disp / Downscale) / bufferSize);
	fragColor = vec4(src.rgb + vec3(bright), src.a);
}
