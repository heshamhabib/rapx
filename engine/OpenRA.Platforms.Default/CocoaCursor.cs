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
using System.Runtime.InteropServices;
using OpenRA.Primitives;

namespace OpenRA.Platforms.Default
{
	/// <summary>
	/// Builds a macOS NSCursor whose image keeps every pixel but is sized in points (pixels / density),
	/// and swaps it into an SDL2 cursor. SDL2 itself always creates 1 pixel = 1 point cursors, which
	/// macOS then blurs when it upscales them on Retina displays.
	/// </summary>
	static class CocoaCursor
	{
		const string ObjC = "/usr/lib/libobjc.A.dylib";

		[StructLayout(LayoutKind.Sequential)]
		struct CGSize
		{
			public double Width, Height;
			public CGSize(double w, double h) { Width = w; Height = h; }
		}

		[StructLayout(LayoutKind.Sequential)]
		struct CGPoint
		{
			public double X, Y;
			public CGPoint(double x, double y) { X = x; Y = y; }
		}

		[DllImport(ObjC)]
		static extern IntPtr objc_getClass(string name);

		[DllImport(ObjC)]
		static extern IntPtr sel_registerName(string name);

		[DllImport(ObjC, EntryPoint = "objc_msgSend")]
		static extern IntPtr Send(IntPtr receiver, IntPtr selector);

		[DllImport(ObjC, EntryPoint = "objc_msgSend")]
		static extern IntPtr Send(IntPtr receiver, IntPtr selector, IntPtr arg);

		[DllImport(ObjC, EntryPoint = "objc_msgSend")]
		static extern IntPtr Send(IntPtr receiver, IntPtr selector, string arg);

		[DllImport(ObjC, EntryPoint = "objc_msgSend")]
		static extern IntPtr Send(IntPtr receiver, IntPtr selector, CGSize size);

		[DllImport(ObjC, EntryPoint = "objc_msgSend")]
		static extern IntPtr Send(IntPtr receiver, IntPtr selector, IntPtr image, CGPoint hotspot);

		[DllImport(ObjC, EntryPoint = "objc_msgSend")]
		static extern IntPtr Send(IntPtr receiver, IntPtr selector, IntPtr planes, long width, long height,
			long bitsPerSample, long samplesPerPixel, [MarshalAs(UnmanagedType.I1)] bool hasAlpha,
			[MarshalAs(UnmanagedType.I1)] bool isPlanar, IntPtr colorSpaceName, long bytesPerRow, long bitsPerPixel);

		static IntPtr Sel(string name) => sel_registerName(name);

		static IntPtr Alloc(string cls) => Send(objc_getClass(cls), Sel("alloc"));

		/// <param name="sdlCursor">An SDL_Cursor*: { SDL_Cursor *next; void *driverdata (a retained NSCursor) }.</param>
		/// <param name="bgra">Straight-alpha BGRA pixels.</param>
		public static void ReplaceWithHighDensity(IntPtr sdlCursor, Size size, byte[] bgra, int2 hotspot, int density)
		{
			try
			{
				var colorSpace = Send(Alloc("NSString"), Sel("initWithUTF8String:"), "NSDeviceRGBColorSpace");
				var rep = Send(Alloc("NSBitmapImageRep"),
					Sel("initWithBitmapDataPlanes:pixelsWide:pixelsHigh:bitsPerSample:samplesPerPixel:hasAlpha:isPlanar:colorSpaceName:bytesPerRow:bitsPerPixel:"),
					IntPtr.Zero, size.Width, size.Height, 8, 4, true, false, colorSpace, 4 * size.Width, 32);
				Send(colorSpace, Sel("release"));
				if (rep == IntPtr.Zero)
					return;

				// NSBitmapImageRep wants premultiplied RGBA
				var rgba = new byte[bgra.Length];
				for (var i = 0; i < bgra.Length; i += 4)
				{
					var a = bgra[i + 3];
					rgba[i] = (byte)(bgra[i + 2] * a / 255);
					rgba[i + 1] = (byte)(bgra[i + 1] * a / 255);
					rgba[i + 2] = (byte)(bgra[i] * a / 255);
					rgba[i + 3] = a;
				}

				Marshal.Copy(rgba, 0, Send(rep, Sel("bitmapData")), rgba.Length);

				var points = new CGSize((double)size.Width / density, (double)size.Height / density);
				Send(rep, Sel("setSize:"), points);
				var image = Send(Alloc("NSImage"), Sel("initWithSize:"), points);
				Send(image, Sel("addRepresentation:"), rep);
				Send(rep, Sel("release"));

				var nsCursor = Send(Alloc("NSCursor"), Sel("initWithImage:hotSpot:"), image,
					new CGPoint((double)hotspot.X / density, (double)hotspot.Y / density));
				Send(image, Sel("release"));
				if (nsCursor == IntPtr.Zero)
					return;

				// SDL releases driverdata when the cursor is freed, so hand it our (+1 retained) cursor
				var old = Marshal.ReadIntPtr(sdlCursor, IntPtr.Size);
				Marshal.WriteIntPtr(sdlCursor, IntPtr.Size, nsCursor);
				if (old != IntPtr.Zero)
					Send(old, Sel("release"));
			}
			catch (Exception e)
			{
				// Keep SDL's own (low density) cursor
				Log.Write("debug", $"Failed to create high-DPI cursor: {e.Message}");
			}
		}
	}
}
