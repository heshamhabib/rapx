#version {VERSION}

// RedAlert Project X - places a unit quad (-1..1) on the minimap rectangle (clip space) and passes map UVs (0,0 = top-left)

in vec2 aVertexPosition;
uniform vec4 Rect;   // clip space: left, bottom, right, top
out vec2 vUV;

void main()
{
	vec2 t = aVertexPosition * 0.5 + 0.5;
	vUV = vec2(t.x, 1.0 - t.y);
	gl_Position = vec4(mix(Rect.xy, Rect.zw, t), 0.0, 1.0);
}
