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

using System.IO;
using System.Linq;
using OpenRA.FileSystem;
using OpenRA.Graphics;

namespace OpenRA.Mods.RAPX.Graphics
{
	/// <summary>Shader bindings that load GLSL from the mod's shaders/ folder instead of the engine's glsl/ directory.</summary>
	public sealed class ModShaderBindings : IShaderBindings
	{
		public string VertexShaderName { get; }
		public string VertexShaderCode { get; }
		public string FragmentShaderName { get; }
		public string FragmentShaderCode { get; }
		public int Stride { get; }
		public ShaderVertexAttribute[] Attributes { get; }

		public ModShaderBindings(IReadOnlyFileSystem fileSystem, string vertexShader, string fragmentShader, params ShaderVertexAttribute[] attributes)
		{
			Attributes = attributes;
			Stride = attributes.Sum(a => a.Components * 4);
			VertexShaderName = vertexShader;
			VertexShaderCode = Read(fileSystem, vertexShader);
			FragmentShaderName = fragmentShader;
			FragmentShaderCode = Read(fileSystem, fragmentShader);
		}

		static string Read(IReadOnlyFileSystem fileSystem, string filename)
		{
			using (var stream = fileSystem.Open(filename))
			using (var reader = new StreamReader(stream))
				return reader.ReadToEnd();
		}
	}
}
