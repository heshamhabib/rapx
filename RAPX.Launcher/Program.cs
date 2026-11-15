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
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace RAPX.Launcher
{
	/// <summary>
	/// The game executable that sits at the top of the source tree, so there is something to double click
	/// without digging through it.
	///
	/// It cannot be the real launcher: OpenRA loads a mod's assemblies from the directory holding the
	/// executable (ObjectCreator, "Assemblies must exist in the game binary directory next to the main game
	/// executable"), so the real launcher has to live in engine/bin beside them. Rather than keep a second
	/// copy of the engine binaries up here - which would go stale the moment anyone built without make -
	/// this hands over to that one and gets out of the way. It carries the same icon, and so does the
	/// process that ends up owning the game window.
	/// </summary>
	static class Program
	{
		const string LauncherRelativePath = @"engine\bin";

		[DllImport("user32.dll", CharSet = CharSet.Unicode)]
		static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

		static int Main(string[] args)
		{
			// AppContext.BaseDirectory rather than the working directory, so the shortcut, the command line
			// and a pinned taskbar entry all resolve the same way
			var root = AppContext.BaseDirectory;
			var name = Path.GetFileName(Environment.ProcessPath ?? "RAPX.exe");
			var launcher = Path.Combine(root, LauncherRelativePath, name);

			if (!File.Exists(launcher))
			{
				Fail($"{launcher}\n\ncould not be found.\n\nRun make.cmd in {root.TrimEnd(Path.DirectorySeparatorChar)} to build the game, then try again.");
				return 1;
			}

			var psi = new ProcessStartInfo(launcher)
			{
				UseShellExecute = false,
				WorkingDirectory = Path.GetDirectoryName(launcher)
			};

			// Pass our own arguments straight through, so `RAPX.exe Launch.Map=...` still works
			foreach (var arg in args)
				psi.ArgumentList.Add(arg);

			try
			{
				// Started and forgotten: the launcher we just handed over to owns the game and its error
				// reporting from here, and lingering would only put a second entry in the task list.
				using (Process.Start(psi))
					return 0;
			}
			catch (Exception e)
			{
				Fail($"Could not start\n\n{launcher}\n\n{e.Message}");
				return 1;
			}
		}

		static void Fail(string message)
		{
			// MB_OK | MB_ICONERROR. There is no console to write to: this is a winexe so that double
			// clicking it does not flash up a terminal.
			MessageBoxW(IntPtr.Zero, message, "RAPX", 0x00000010);
		}
	}
}
