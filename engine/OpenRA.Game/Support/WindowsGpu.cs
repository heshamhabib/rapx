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
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using Microsoft.Win32;

namespace OpenRA.Support
{
	/// <summary>
	/// RAPX: the graphics cards of a Windows PC, and the choice between them that Windows keeps for each program
	/// (Settings > System > Display > Graphics, stored under HKCU\Software\Microsoft\DirectX\UserGpuPreferences).
	/// Laptops with integrated and dedicated graphics start programs on the power-saving card unless told otherwise.
	/// Every member does nothing (or returns nothing) on other platforms.
	/// </summary>
	public static class WindowsGpu
	{
		public enum Preference { WindowsDecides = 0, PowerSaving = 1, HighPerformance = 2 }

		public sealed class Adapter
		{
			public string Name;
			public uint VendorId;
			public ulong DedicatedMemory;

			/// <summary>Microsoft's stand-in for a graphics card whose own driver is missing.</summary>
			public bool NoDriver => VendorId == 0x1414;

			/// <summary>Built into the processor, going by the memory it reports as its own: about 128 MB for Intel's
			/// (its Arc cards have 4 GB or more), usually 512 MB for AMD's.</summary>
			public bool Integrated => DedicatedMemory <= (VendorId == 0x8086 ? 2048UL : 512UL) * 1024 * 1024;
		}

		const string PreferencesKey = @"Software\Microsoft\DirectX\UserGpuPreferences";

		/// <summary>The game's own executable, or null on other platforms and when the game runs inside the shared
		/// dotnet host (during development), whose preference would apply to every .NET program.</summary>
		public static string GameExecutable
		{
			get
			{
				var path = Environment.ProcessPath;
				if (!OperatingSystem.IsWindows() || string.IsNullOrEmpty(path))
					return null;

				return Path.GetFileNameWithoutExtension(path).Equals("dotnet", StringComparison.OrdinalIgnoreCase) ? null : path;
			}
		}

		/// <summary>The graphics card preference Windows keeps for this executable, or null when there is none.</summary>
		public static Preference? GetPreference(string executable)
		{
			if (!OperatingSystem.IsWindows() || executable == null)
				return null;

			try
			{
				using var key = Registry.CurrentUser.OpenSubKey(PreferencesKey);
				if (key?.GetValue(executable) is not string value)
					return null;

				foreach (var part in value.Split(';'))
				{
					var kv = part.Split('=');
					if (kv.Length == 2 && kv[0].Trim() == "GpuPreference" && Exts.TryParseInt32Invariant(kv[1].Trim(), out var p) && p >= 0 && p <= 2)
						return (Preference)p;
				}
			}
			catch
			{
				// No preference can be read: treat it as none
			}

			return null;
		}

		/// <summary>Sets the graphics card preference for this executable (it applies to processes started afterwards),
		/// keeping any other per-program settings Windows stored with it.</summary>
		public static bool SetPreference(string executable, Preference preference)
		{
			if (!OperatingSystem.IsWindows() || executable == null)
				return false;

			try
			{
				using var key = Registry.CurrentUser.CreateSubKey(PreferencesKey);
				var others = ((key.GetValue(executable) as string) ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries)
					.Where(p => !p.TrimStart().StartsWith("GpuPreference=", StringComparison.Ordinal));
				key.SetValue(executable, string.Join(";", others.Prepend($"GpuPreference={(int)preference}")) + ";");
				return true;
			}
			catch
			{
				return false;
			}
		}

		/// <summary>The graphics cards Windows has running (DXGI adapters, without the software renderer), in Windows'
		/// own order. Empty on other platforms or if they cannot be listed.</summary>
		public static IReadOnlyList<Adapter> Adapters()
		{
			var result = new List<Adapter>();
			if (!OperatingSystem.IsWindows())
				return result;

			try
			{
				var iid = typeof(IDXGIFactory1).GUID;
				if (CreateDXGIFactory1(ref iid, out var factory) != 0 || factory == null)
					return result;

				try
				{
					for (uint i = 0; factory.EnumAdapters1(i, out var adapter) == 0; i++)
					{
						try
						{
							// DXGI_ADAPTER_FLAG_SOFTWARE: the Basic Render Driver every PC has
							if (adapter.GetDesc1(out var desc) == 0 && (desc.Flags & 2) == 0 &&
								!result.Any(a => a.Name == desc.Description && a.VendorId == desc.VendorId))
								result.Add(new Adapter
								{
									Name = desc.Description.Trim(),
									VendorId = desc.VendorId,
									DedicatedMemory = (ulong)desc.DedicatedVideoMemory
								});
						}
						finally
						{
							Marshal.ReleaseComObject(adapter);
						}
					}
				}
				finally
				{
					Marshal.ReleaseComObject(factory);
				}
			}
			catch
			{
				// DXGI is missing or broken: no list, the game still runs
			}

			return result;
		}

		[DllImport("dxgi.dll", ExactSpelling = true)]
		static extern int CreateDXGIFactory1(ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out IDXGIFactory1 factory);

		// Only the methods called are declared with their real signatures; the others hold their vtable slots
		[ComImport]
		[Guid("770aae78-f26f-4dba-a829-253c83d1b387")]
		[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
		interface IDXGIFactory1
		{
			void SetPrivateData();
			void SetPrivateDataInterface();
			void GetPrivateData();
			void GetParent();
			void EnumAdapters();
			void MakeWindowAssociation();
			void GetWindowAssociation();
			void CreateSwapChain();
			void CreateSoftwareAdapter();

			[PreserveSig]
			int EnumAdapters1(uint index, out IDXGIAdapter1 adapter);
		}

		[ComImport]
		[Guid("29038f61-3839-4626-91fd-086879011a05")]
		[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
		interface IDXGIAdapter1
		{
			void SetPrivateData();
			void SetPrivateDataInterface();
			void GetPrivateData();
			void GetParent();
			void EnumOutputs();
			void GetDesc();
			void CheckInterfaceSupport();

			[PreserveSig]
			int GetDesc1(out AdapterDescription description);
		}

		// DXGI_ADAPTER_DESC1
		[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
		struct AdapterDescription
		{
			[MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
			public string Description;
			public uint VendorId;
			public uint DeviceId;
			public uint SubSysId;
			public uint Revision;
			public UIntPtr DedicatedVideoMemory;
			public UIntPtr DedicatedSystemMemory;
			public UIntPtr SharedSystemMemory;
			public uint AdapterLuidLowPart;
			public int AdapterLuidHighPart;
			public uint Flags;
		}
	}
}
