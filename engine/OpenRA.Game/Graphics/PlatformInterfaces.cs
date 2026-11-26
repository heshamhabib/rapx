#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is free software. It is made
 * available to you under the terms of the GNU General Public License
 * as published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version. For more
 * information, see COPYING.
 */
#endregion

using System;
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA
{
	public enum GLProfile
	{
		Automatic,
		ANGLE,
		Modern,
		Embedded
	}

	/// <summary>
	/// RAPX: the graphics card the game draws with, as its driver names it (GL_RENDERER; through ANGLE it reads
	/// "ANGLE (vendor, card Direct3D11 ..., D3D11-driver version)") and the driver's vendor (GL_VENDOR).
	/// Set once the OpenGL context exists, null before; shown in Settings > Display and written to the logs.
	/// </summary>
	public static class GraphicsCard
	{
		public static string Renderer { get; set; }
		public static string Vendor { get; set; }
	}

	public interface IPlatform
	{
		IPlatformWindow CreateWindow(
			Size size, WindowMode windowMode, float scaleModifier, int vertexBatchSize, int indexBatchSize, int videoDisplay, GLProfile profile);
		ISoundEngine CreateSound(string device);
		IFont CreateFont(byte[] data);
	}

	public interface IHardwareCursor : IDisposable { }

	public enum BlendMode : byte
	{
		None,
		Alpha,
		Additive,
		Subtractive,
		Multiply,
		Multiplicative,
		DoubleMultiplicative,
		LowAdditive,
		Screen,
		Translucent
	}

	public interface IPlatformWindow : IDisposable
	{
		IGraphicsContext Context { get; }

		Size NativeWindowSize { get; }
		Size EffectiveWindowSize { get; }
		float NativeWindowScale { get; }
		float EffectiveWindowScale { get; }
		Size SurfaceSize { get; }
		int DisplayCount { get; }
		int CurrentDisplay { get; }
		bool HasInputFocus { get; }
		bool IsSuspended { get; }

		event Action<float, float, float, float> OnWindowScaleChanged;

		void PumpInput(IInputHandler inputHandler);
		string GetClipboardText();
		bool SetClipboardText(string text);

		void GrabWindowMouseFocus();
		void ReleaseWindowMouseFocus();

		// highDensity: the image is authored at 2x, so show it at half its pixel size (full resolution on high-DPI displays)
		IHardwareCursor CreateHardwareCursor(string name, Size size, byte[] data, int2 hotspot, bool pixelDouble, bool highDensity = false);
		void SetHardwareCursor(IHardwareCursor cursor);
		void SetWindowTitle(string title);
		void SetRelativeMouseMode(bool mode);
		void SetScaleModifier(float scale);

		GLProfile GLProfile { get; }

		GLProfile[] SupportedGLProfiles { get; }
	}

	public interface IGraphicsContext : IDisposable
	{
		IVertexBuffer<T> CreateVertexBuffer<T>(int size) where T : struct;
		T[] CreateVertices<T>(int size) where T : struct;
		IIndexBuffer CreateIndexBuffer(uint[] indices);
		ITexture CreateTexture();
		IFrameBuffer CreateFrameBuffer(Size s);
		IFrameBuffer CreateFrameBuffer(Size s, Color clearColor);
		IShader CreateShader(IShaderBindings shaderBindings);
		void EnableScissor(int x, int y, int width, int height);
		void DisableScissor();
		void Present();
		void DrawPrimitives(PrimitiveType pt, int firstVertex, int numVertices);
		void DrawElements(int numIndices, int offset);
		void Clear();
		void EnableDepthBuffer();
		void DisableDepthBuffer();
		void ClearDepthBuffer();
		void SetBlendMode(BlendMode mode);
		void SetVSyncEnabled(bool enabled);
		string GLVersion { get; }
	}

	public interface IRenderer
	{
		void BeginFrame();
		void EndFrame();
		void SetPalette(HardwarePalette palette);
	}

	public interface IVertexBuffer<T> : IDisposable where T : struct
	{
		void Bind();
		void SetData(T[] vertices, int length);

		/// <summary>
		/// Upon return `vertices` may reference another array object of at least the same size - containing random values.
		/// </summary>
		void SetData(ref T[] vertices, int length);
		void SetData(T[] vertices, int offset, int start, int length);
	}

	public interface IIndexBuffer : IDisposable
	{
		void Bind();
	}

	public interface IShader
	{
		void SetBool(string name, bool value);
		void SetVec(string name, float x);
		void SetVec(string name, float x, float y);
		void SetVec(string name, float x, float y, float z);
		void SetVec(string name, float[] vec, int length);
		void SetTexture(string param, ITexture texture);
		void SetMatrix(string param, float[] mtx);
		void PrepareRender();
		void Bind();
	}

	public interface IShaderBindings
	{
		string VertexShaderName { get; }
		string VertexShaderCode { get; }
		string FragmentShaderName { get; }
		string FragmentShaderCode { get; }
		int Stride { get; }
		ShaderVertexAttribute[] Attributes { get; }
	}

	public enum TextureScaleFilter
	{
		Nearest,
		Linear,

		/// <summary>Linear filtering with generated mipmaps and repeat wrapping, for tiling detail textures.</summary>
		Trilinear
	}

	public interface ITexture : IDisposable
	{
		void SetData(byte[] colors, int width, int height);
		void SetFloatData(float[] data, int width, int height);
		void SetDataFromReadBuffer(Rectangle rect);

		/// <summary>Copies a region of the read buffer into the same region of the already allocated texture.</summary>
		void UpdateFromReadBuffer(Rectangle rect);
		byte[] GetData();
		Size Size { get; }
		TextureScaleFilter ScaleFilter { get; set; }
	}

	public interface IFrameBuffer : IDisposable
	{
		void Bind();
		void Unbind();
		void EnableScissor(Rectangle rect);
		void DisableScissor();
		ITexture Texture { get; }
	}

	public enum PrimitiveType
	{
		PointList,
		LineList,
		TriangleList,
	}

	public readonly struct Range<T>
	{
		public readonly T Start, End;
		public Range(T start, T end) { Start = start; End = end; }
	}

	public enum WindowMode
	{
		Windowed,
		Fullscreen,
		PseudoFullscreen,
	}

	public interface IFont : IDisposable
	{
		FontGlyph CreateGlyph(char c, int size, float deviceScale);
	}

	public struct FontGlyph
	{
		public int2 Offset;
		public Size Size;
		public float Advance;
		public byte[] Data;
	}
}
