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
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using OpenRA.Support;
using SDL2;

namespace OpenRA.WindowsLauncher
{
	sealed class WindowsLauncher
	{
		[DllImport("user32.dll")]
		static extern bool SetForegroundWindow(IntPtr hWnd);

		[DllImport("user32.dll")]
		static extern bool AllowSetForegroundWindow(int dwProcessId);

		static Process gameProcess;
		static string modID;
		static string displayName;
		static string faqUrl;
		static string extraArgs;
		static DateTime gameStarted;

		static int Main(string[] args)
		{
			// The modID, displayName, faqUrl and extraArgs variables are embedded in the assembly metadata by defining
			// -p:ModID="mymod", -p:DisplayName="My Mod", -p:FaqUrl="https://my.tld/faq", -p:ExtraArgs="..." when compiling the project
			var attributes = Assembly.GetExecutingAssembly().GetCustomAttributes();
			foreach (var a in attributes)
			{
				if (a is AssemblyMetadataAttribute metadata)
				{
					switch (metadata.Key)
					{
						case "ModID": modID = metadata.Value; break;
						case "DisplayName": displayName = metadata.Value; break;
						case "FaqUrl": faqUrl = metadata.Value; break;
						case "ExtraArgs": extraArgs = metadata.Value; break;
					}
				}
			}

			if (Array.Exists(args, x => x.StartsWith("Engine.LaunchPath=", StringComparison.Ordinal)))
				return RunGame(args);

			return RunInnerLauncher(args);
		}

		static int RunGame(string[] args)
		{
			var launcherPath = Assembly.GetExecutingAssembly().Location;
			var directory = Path.GetDirectoryName(launcherPath);
			Directory.SetCurrentDirectory(directory);

			AppDomain.CurrentDomain.UnhandledException += (_, e) => ExceptionHandler.HandleFatalError((Exception)e.ExceptionObject);

			try
			{
				return (int)Game.InitializeAndRun(args);
			}
			catch (Exception e)
			{
				// We must grant permission for the launcher process to bring the error dialog to the foreground.
				// Finding the parent process id is unreasonably difficult on Windows, so instead pass -1 to enable for all processes.
				AllowSetForegroundWindow(-1);
				ExceptionHandler.HandleFatalError(e);
				return (int)RunStatus.Error;
			}
			finally
			{
				// Flushing logs in finally block is okay here, as the catch block handles the exception.
				Log.Dispose();
			}
		}

		static int RunInnerLauncher(string[] args)
		{
			var launcherPath = Environment.ProcessPath;
			var launcherArgs = args.ToList();

			if (!launcherArgs.Exists(x => x.StartsWith("Engine.LaunchPath=", StringComparison.Ordinal)))
				launcherArgs.Add("Engine.LaunchPath=\"" + launcherPath + "\"");

			if (!launcherArgs.Exists(x => x.StartsWith("Game.Mod=", StringComparison.Ordinal)))
				launcherArgs.Add("Game.Mod=" + modID);

			// ExtraArgs is a verbatim command line fragment rather than a list, so that a baked-in path
			// containing spaces keeps the quoting its author gave it. A launcher built against a source
			// tree uses it to point the engine at the directories it was built from.
			var commandLine = string.Join(" ", launcherArgs);
			if (!string.IsNullOrEmpty(extraArgs))
				commandLine += " " + extraArgs;

			// RAPX: laptops with integrated and dedicated graphics run programs on the power-saving card unless told
			// otherwise. Unless the player (or Windows) already chose for this game, ask Windows for the high-performance
			// card; the game process starts right after, so it applies straight away. Settings > Display changes it.
			var executable = WindowsGpu.GameExecutable;
			if (executable != null && WindowsGpu.GetPreference(executable) == null)
				WindowsGpu.SetPreference(executable, WindowsGpu.Preference.HighPerformance);

			gameStarted = DateTime.UtcNow;
			var psi = new ProcessStartInfo(launcherPath, commandLine);

			try
			{
				gameProcess = Process.Start(psi);
			}
			catch
			{
				return 1;
			}

			if (gameProcess == null)
				return 1;

			gameProcess.EnableRaisingEvents = true;
			gameProcess.Exited += GameProcessExited;
			gameProcess.WaitForExit();

			return 0;
		}

		static void ShowErrorDialog()
		{
			var viewLogs = new SDL.SDL_MessageBoxButtonData
			{
				buttonid = 2,
				text = "View Logs",
				flags = SDL.SDL_MessageBoxButtonFlags.SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT
			};

			var viewFaq = new SDL.SDL_MessageBoxButtonData
			{
				buttonid = 1,
				text = "View FAQ"
			};

			var quit = new SDL.SDL_MessageBoxButtonData
			{
				buttonid = 0,
				text = "Quit",
				flags = SDL.SDL_MessageBoxButtonFlags.SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT
			};

			var graphics = GraphicsFailed();
			var dialog = new SDL.SDL_MessageBoxData
			{
				flags = SDL.SDL_MessageBoxFlags.SDL_MESSAGEBOX_ERROR,
				title = graphics ? "Graphics Error" : "Fatal Error",
				message = graphics ? GraphicsErrorMessage() :
					displayName + " has encountered a fatal error and must close.\nRefer to the crash logs and FAQ for more information.",
				buttons = new[] { quit, viewFaq, viewLogs },
				numbuttons = 3
			};

			// SDL_ShowMessageBox may create the error dialog behind other windows.
			// We want to bring it to the foreground, but can't do it from the main thread
			// because SDL_ShowMessageBox blocks until the user presses a button.
			// HACK: Spawn a thread to raise it to the foreground after a short delay.
			Task.Run(() =>
			{
				Thread.Sleep(1000);
				SetForegroundWindow(Process.GetCurrentProcess().MainWindowHandle);
			});

			if (SDL.SDL_ShowMessageBox(ref dialog, out var buttonid) < 0)
				Exit();

			switch (buttonid)
			{
				case 0: Exit(); break;
				case 1:
				{
					try
					{
						SDL.SDL_OpenURL(faqUrl);
					}
					catch { }
					break;
				}

				case 2:
				{
					try
					{
						SDL.SDL_OpenURL(Path.Combine(Platform.SupportDir, "Logs"));
					}
					catch { }
					break;
				}
			}
		}

		// RAPX: errors the engine raises when it cannot get the graphics card to draw (see OpenRA.Platforms.Default)
		static readonly string[] GraphicsErrors =
		{
			"No supported OpenGL profiles were found", "OpenGL Version Error", "Failed to initialize low-level OpenGL bindings",
			"Failed to initialize OpenGL", "Failed to initialize an OpenGL debug message callback", "OpenGL Error:"
		};

		/// <summary>RAPX: whether the game that just closed failed on its graphics (its crash log says so).</summary>
		static bool GraphicsFailed()
		{
			try
			{
				var logs = new DirectoryInfo(Path.Combine(Platform.SupportDir, "Logs"));
				var crash = logs.GetFiles("exception-*.log")
					.Where(f => f.LastWriteTimeUtc >= gameStarted.AddSeconds(-2))
					.OrderByDescending(f => f.LastWriteTimeUtc)
					.FirstOrDefault();

				if (crash == null)
					return false;

				var text = File.ReadAllText(crash.FullName);
				return GraphicsErrors.Any(text.Contains);
			}
			catch
			{
				return false;
			}
		}

		/// <summary>RAPX: what went wrong with the graphics and what to try, naming the graphics cards Windows has running.</summary>
		static string GraphicsErrorMessage()
		{
			var adapters = WindowsGpu.Adapters();
			var found = adapters.Count > 0
				? "Graphics cards found: " + string.Join(", ", adapters.Select(a => a.Name)) + "."
				: "No graphics card was found.";

			var noDriver = adapters.Any(a => a.NoDriver)
				? "\nOne of them is Windows' basic display adapter: a graphics card is running without its driver."
				: "";

			return displayName + " could not start its graphics.\n\n" + found + noDriver + "\n\n" +
				"What to try:\n" +
				"- Install the latest driver for your graphics card from the NVIDIA, AMD or Intel website.\n" +
				"- On a laptop with two graphics cards, the game asks Windows for the faster one. Check that \"High performance\" " +
				"is chosen for the game in Windows Settings > System > Display > Graphics.\n\n" +
				"The logs show the details.";
		}

		static void GameProcessExited(object sender, EventArgs e)
		{
			if (gameProcess.ExitCode != (int)RunStatus.Success)
				ShowErrorDialog();

			Exit();
		}

		static void Exit()
		{
			Environment.Exit(0);
		}
	}
}
