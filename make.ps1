####### The starting point for the script is the bottom #######

###############################################################
########################## FUNCTIONS ##########################
###############################################################
function All-Command
{
	If (!(Test-Path "*.sln"))
	{
		Write-Host "No custom solution file found. Aborting." -ForegroundColor Red
		return
	}

	if ((CheckForDotnet) -eq 1)
	{
		return
	}

	Write-Host "Building $modID in" $configuration "configuration..." -ForegroundColor Cyan
	dotnet build -c $configuration --nologo -p:TargetPlatform=win-x64

	if ($lastexitcode -ne 0)
	{
		Write-Host "Build failed. If just the development tools failed to build, try installing Visual Studio. You may also still be able to run the game." -ForegroundColor Red
		return
	}

	Write-Host "Build succeeded." -ForegroundColor Green
	Launcher-Command
}

# MSBuild reads a space, comma or semicolon in a -p: value as the end of the switch, so anything that
# can contain one - a display name, a path, the engine arguments below - has to be percent escaped.
function EscapeProperty($value)
{
	if (!$value)
	{
		return ""
	}

	return $value.Replace('%', '%25').Replace(' ', '%20').Replace(',', '%2C').Replace(';', '%3B')
}

function LauncherName
{
	if ($env:PACKAGING_WINDOWS_LAUNCHER_NAME)
	{
		return $env:PACKAGING_WINDOWS_LAUNCHER_NAME
	}

	return $modID
}

# On a laptop with switchable graphics, Windows hands OpenGL to the integrated GPU unless the executable
# is listed here, which costs a lot of frames. The engine's own OpenRA.exe may already be registered from
# before the launcher existed; this names the executables the game now actually runs as.
# GpuPreference=2 is "High performance". Undo it in Settings > Display > Graphics.
function Gpu-Command
{
	$launcherName = LauncherName
	$key = "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences"

	if (!(Test-Path $key))
	{
		New-Item -Path $key -Force | Out-Null
	}

	$targets = @(
		[System.IO.Path]::GetFullPath((Join-Path $templateDir "$launcherName.exe")),
		[System.IO.Path]::GetFullPath((Join-Path $templateDir ($env:ENGINE_DIRECTORY + "/bin/$launcherName.exe")))
	)

	foreach ($target in $targets)
	{
		Set-ItemProperty -Path $key -Name $target -Value "GpuPreference=2;"
		Write-Host "High performance GPU: $target" -ForegroundColor Green
	}
}

function Launcher-Command
{
	$launcherName = LauncherName

	$artworkDir = [System.IO.Path]::GetFullPath((Join-Path $templateDir "packaging/artwork"))
	$icon = Join-Path $artworkDir ($modID + ".ico")
	$newestArtwork = Get-ChildItem (Join-Path $artworkDir "icon_*.png") | Sort-Object LastWriteTimeUtc | Select-Object -Last 1

	if (!(Test-Path $icon) -or (Get-Item $icon).LastWriteTimeUtc -lt $newestArtwork.LastWriteTimeUtc)
	{
		Write-Host "Building icon from $($artworkDir)..." -ForegroundColor Cyan
		& (Join-Path $templateDir "tools/make-ico.ps1") -ArtworkDir $artworkDir -OutFile $icon
	}

	# The launcher relaunches itself to host the game, so the game window belongs to the launcher and
	# wears its icon. That second process needs to be told where this source tree keeps the engine and
	# the mods, because neither sits next to the binaries the way they do in a packaged install. Both
	# paths are relative to the launcher, so the tree can still be moved or renamed.
	$extraArgs = "Engine.EngineDir=.. Engine.ModSearchPaths=../../mods,./mods"

	$project = [System.IO.Path]::GetFullPath((Join-Path $templateDir ($env:ENGINE_DIRECTORY + "/OpenRA.WindowsLauncher/OpenRA.WindowsLauncher.csproj")))

	Write-Host "Building $launcherName.exe..." -ForegroundColor Cyan
	dotnet build $project -c $configuration --nologo -p:TargetPlatform=win-x64 `
		"-p:LauncherName=$(EscapeProperty $launcherName)" `
		"-p:LauncherIcon=$(EscapeProperty $icon)" `
		"-p:ModID=$(EscapeProperty $modID)" `
		"-p:DisplayName=$(EscapeProperty $env:PACKAGING_DISPLAY_NAME)" `
		"-p:FaqUrl=$(EscapeProperty $env:PACKAGING_FAQ_URL)" `
		"-p:ExtraArgs=$(EscapeProperty $extraArgs)"

	if ($lastexitcode -ne 0)
	{
		Write-Host "Launcher build failed. Run the game with launch-game.cmd instead." -ForegroundColor Red
		return
	}

	$exe = [System.IO.Path]::GetFullPath((Join-Path $templateDir ($env:ENGINE_DIRECTORY + "/bin/$launcherName.exe")))
	if (!(Test-Path $exe))
	{
		Write-Host "Launcher build reported success but $exe is missing." -ForegroundColor Red
		return
	}

	# That exe has to live next to the engine assemblies it loads, which is no place to go looking for a
	# game, so build a second small one at the top of the tree that hands over to it. See RAPX.Launcher.
	$stub = Join-Path $templateDir "RAPX.Launcher/RAPX.Launcher.csproj"

	dotnet build $stub -c $configuration --nologo `
		"-p:LauncherName=$(EscapeProperty $launcherName)" `
		"-p:LauncherIcon=$(EscapeProperty $icon)" `
		"-p:DisplayName=$(EscapeProperty $env:PACKAGING_DISPLAY_NAME)"

	if ($lastexitcode -ne 0)
	{
		Write-Host "Failed to build $launcherName.exe. Run the game with $exe instead." -ForegroundColor Red
		return
	}

	Write-Host "Built $(Join-Path $templateDir "$launcherName.exe")" -ForegroundColor Green
	Write-Host "Double click $launcherName.exe in this folder to play." -ForegroundColor Green
}

function Clean-Command
{
	If (!(Test-Path "*.sln"))
	{
		Write-Host "No custom solution file found - nothing to clean. Aborting." -ForegroundColor Red
		return
	}

	if ((CheckForDotnet) -eq 1)
	{
		return
	}

	Write-Host "Cleaning $modID..." -ForegroundColor Cyan

	dotnet clean /nologo
	Remove-Item ./*/obj -Recurse -ErrorAction Ignore
	Remove-Item env:ENGINE_DIRECTORY/bin -Recurse -ErrorAction Ignore
	Remove-Item env:ENGINE_DIRECTORY/*/obj -Recurse -ErrorAction Ignore

	Write-Host "Clean complete." -ForegroundColor Green
}

function Version-Command
{
	if ($command.Length -gt 1)
	{
		$version = $command[1]
	}
	elseif (Get-Command 'git' -ErrorAction SilentlyContinue)
	{
		$gitRepo = git rev-parse --is-inside-work-tree
		if ($gitRepo)
		{
			$version = git name-rev --name-only --tags --no-undefined HEAD 2>$null
			if ($version -eq $null)
			{
				$version = "git-" + (git rev-parse --short HEAD)
			}
		}
		else
		{
			Write-Host "Not a git repository. The version will remain unchanged." -ForegroundColor Red
		}
	}
	else
	{
		Write-Host "Unable to locate Git. The version will remain unchanged." -ForegroundColor Red
	}

	if ($version -ne $null)
	{
		$mod = "mods/" + $modID + "/mod.yaml"
		$replacement = (gc $mod) -Replace "Version:.*", ("Version: {0}" -f $version)
		sc $mod $replacement

		$prefix = $(gc $mod) | Where { $_.ToString().EndsWith(": User") }
		if ($prefix -and $prefix.LastIndexOf("/") -ne -1)
		{
			$prefix = $prefix.Substring(0, $prefix.LastIndexOf("/"))
		}
		$replacement = (gc $mod) -Replace ".*: User", ("{0}/{1}: User" -f $prefix, $version)
		sc $mod $replacement

		Write-Host ("Version strings set to '{0}'." -f $version)
	}
}

function Test-Command
{
	if ((CheckForUtility) -eq 1)
	{
		return
	}

	Write-Host "Testing $modID mod MiniYAML..." -ForegroundColor Cyan
	InvokeCommand "$utilityPath $modID --check-yaml"
}

function Check-Command
{
	If (!(Test-Path "*.sln"))
	{
		Write-Host "No custom solution file found. Skipping static code checks." -ForegroundColor Cyan
		return
	}

	Write-Host "Compiling $modID in Debug configuration..." -ForegroundColor Cyan

	dotnet clean -c Debug --nologo --verbosity minimal
	dotnet build -c Debug --nologo -warnaserror -p:TargetPlatform=win-x64

	if ($lastexitcode -ne 0)
	{
		Write-Host "Build failed." -ForegroundColor Red
	}

	if ((CheckForUtility) -eq 0)
	{
		Write-Host "Checking $modID for explicit interface violations..." -ForegroundColor Cyan
		InvokeCommand "$utilityPath $modID --check-explicit-interfaces"

		Write-Host "Checking $modID for incorrect conditional trait interface overrides..." -ForegroundColor Cyan
		InvokeCommand "$utilityPath $modID --check-conditional-trait-interface-overrides"
	}
}

function Check-Scripts-Command
{
	if ((Get-Command "luac.exe" -ErrorAction SilentlyContinue) -ne $null)
	{
		Write-Host "Testing Lua scripts..." -ForegroundColor Cyan
		foreach ($script in ls "mods/*/maps/*/*.lua")
		{
			luac -p $script
		}
		Write-Host "Check completed!" -ForegroundColor Green
	}
	else
	{
		Write-Host "luac.exe could not be found. Please install Lua." -ForegroundColor Red
	}
}

function CheckForUtility
{
	if (Test-Path $utilityPath)
	{
		return 0
	}

	Write-Host "OpenRA.Utility.exe could not be found. Build the project first using the `"all`" command." -ForegroundColor Red
	return 1
}

function CheckForDotnet
{
	if ((Get-Command "dotnet" -ErrorAction SilentlyContinue) -eq $null)
	{
		Write-Host "The 'dotnet' tool is required to compile OpenRA. Please install the .NET 6.0 SDK and try again. https://dotnet.microsoft.com/download/dotnet/6.0" -ForegroundColor Red
		return 1
	}

	return 0
}

function WaitForInput
{
	Write-Host "Press enter to continue."
	while ($true)
	{
		if ([System.Console]::KeyAvailable)
		{
			exit
		}
		Start-Sleep -Milliseconds 50
	}
}

function ReadConfigLine($line, $name)
{
	$prefix = $name + '='
	if ($line.StartsWith($prefix))
	{
		[Environment]::SetEnvironmentVariable($name, $line.Replace($prefix, '').Replace('"', ''))
	}
}

function ParseConfigFile($fileName)
{
	$names = @("MOD_ID", "ENGINE_VERSION", "AUTOMATIC_ENGINE_MANAGEMENT", "AUTOMATIC_ENGINE_SOURCE",
		"AUTOMATIC_ENGINE_EXTRACT_DIRECTORY", "AUTOMATIC_ENGINE_TEMP_ARCHIVE_NAME", "ENGINE_DIRECTORY")

	# Used by the Windows launcher. Not required: it falls back to the mod id and empty strings.
	$optionalNames = @("PACKAGING_WINDOWS_LAUNCHER_NAME", "PACKAGING_DISPLAY_NAME", "PACKAGING_FAQ_URL")

	$reader = [System.IO.File]::OpenText($fileName)
	while($null -ne ($line = $reader.ReadLine()))
	{
		foreach ($name in ($names + $optionalNames))
		{
			ReadConfigLine $line $name
		}
	}
	$reader.Close()

	$missing = @()
	foreach ($name in $names)
	{
		if (!([System.Environment]::GetEnvironmentVariable($name)))
		{
			$missing += $name
		}
	}

	if ($missing)
	{
		Write-Host "Required mod.config variables are missing:"
		foreach ($m in $missing)
		{
			Write-Host "   $m"
		}
		Write-Host "Repair your mod.config (or user.config) and try again."
		WaitForInput
		exit
	}
}

function InvokeCommand
{
	param($expression)
	# $? is the return value of the called expression
	# Invoke-Expression itself will always succeed, even if the invoked expression fails
	# So temporarily store the return value in $success
	$expression += '; $success = $?'
	Invoke-Expression $expression
	if ($success -eq $False)
	{
		exit 1
	}
}

###############################################################
############################ Main #############################
###############################################################
if ($PSVersionTable.PSVersion.Major -clt 3)
{
    Write-Host "The makefile requires PowerShell version 3 or higher." -ForegroundColor Red
    Write-Host "Please download and install the latest Windows Management Framework version from Microsoft." -ForegroundColor Red
    WaitForInput
}

if ($args.Length -eq 0)
{
	Write-Host "Command list:"
	Write-Host ""
	Write-Host "  all             Builds the game, its development tools and the mod dlls."
	Write-Host "  version         Sets the version strings for all mods to the latest"
	Write-Host "                  version for the current Git branch."
	Write-Host "  clean           Removes all built and copied files."
	Write-Host "                  from the mods and the engine directories."
	Write-Host "  test            Tests the mod's MiniYAML for errors."
	Write-Host "  check           Checks .cs files for StyleCop violations."
	Write-Host "  check-scripts   Checks .lua files for syntax errors."
	Write-Host ""
	$command = (Read-Host "Enter command").Split(' ', 2)
}
else
{
	$command = $args
}

# Set the working directory for our IO methods
$templateDir = $pwd.Path
[System.IO.Directory]::SetCurrentDirectory($templateDir)

# Load the environment variables from the config file
# and get the mod ID from the local environment variable
ParseConfigFile "mod.config"

if (Test-Path "user.config")
{
	ParseConfigFile "user.config"
}

$modID = $env:MOD_ID

$env:MOD_SEARCH_PATHS = "./mods,$env:ENGINE_DIRECTORY/mods"
$env:ENGINE_DIR = ".." # Set to potentially be used by the Utility and different than $env:ENGINE_DIRECTORY, which is for the script.

# Fetch the engine if required
if ($command -eq "all" -or $command -eq "clean" -or $command -eq "check")
{
	$versionFile = $env:ENGINE_DIRECTORY + "/VERSION"
	$currentEngine = ""
	if (Test-Path $versionFile)
	{
		$reader = [System.IO.File]::OpenText($versionFile)
		$currentEngine = $reader.ReadLine()
		$reader.Close()
	}

	if ($currentEngine -ne "" -and $currentEngine -eq $env:ENGINE_VERSION)
	{
		cd $env:ENGINE_DIRECTORY
		Invoke-Expression ".\make.cmd $command"
		Write-Host ""
		cd $templateDir
	}
	elseif ($env:AUTOMATIC_ENGINE_MANAGEMENT -ne "True")
	{
		Write-Host "Automatic engine management is disabled."
		Write-Host "Please manually update the engine to version $env:ENGINE_VERSION."
		WaitForInput
	}
	else
	{
		Write-Host "OpenRA engine version $env:ENGINE_VERSION is required."

		if (Test-Path $env:ENGINE_DIRECTORY)
		{
			if ($currentEngine -ne "")
			{
				Write-Host "Deleting engine version $currentEngine."
			}
			else
			{
				Write-Host "Deleting existing engine (unknown version)."
			}

			rm $env:ENGINE_DIRECTORY -r
		}

		Write-Host "Downloading engine..."

		if (Test-Path $env:AUTOMATIC_ENGINE_EXTRACT_DIRECTORY)
		{
			rm $env:AUTOMATIC_ENGINE_EXTRACT_DIRECTORY -r
		}

		$url = $env:AUTOMATIC_ENGINE_SOURCE
		$url = $url.Replace("$", "").Replace("{ENGINE_VERSION}", $env:ENGINE_VERSION)

		mkdir $env:AUTOMATIC_ENGINE_EXTRACT_DIRECTORY > $null
		$dlPath = Join-Path $pwd (Split-Path -leaf $env:AUTOMATIC_ENGINE_EXTRACT_DIRECTORY)
		$dlPath = Join-Path $dlPath (Split-Path -leaf $env:AUTOMATIC_ENGINE_TEMP_ARCHIVE_NAME)

		$client = new-object System.Net.WebClient
		[Net.ServicePointManager]::SecurityProtocol = 'Tls12'
		$client.DownloadFile($url, $dlPath)

		Add-Type -assembly "system.io.compression.filesystem"
		[io.compression.zipfile]::ExtractToDirectory($dlPath, $env:AUTOMATIC_ENGINE_EXTRACT_DIRECTORY)
		rm $dlPath

		$extractedDir = Get-ChildItem $env:AUTOMATIC_ENGINE_EXTRACT_DIRECTORY -Recurse | ?{ $_.PSIsContainer } | Select-Object -First 1
		Move-Item $extractedDir.FullName -Destination $templateDir
		Rename-Item $extractedDir.Name (Split-Path -leaf $env:ENGINE_DIRECTORY)

		rm $env:AUTOMATIC_ENGINE_EXTRACT_DIRECTORY -r

		# HACK: Remove bogus lint check that the Example mod can't possibly pass
		# because to do so it would need to define a lot of excess things surrounding resources.
		rm $env:ENGINE_DIRECTORY/OpenRA.Mods.Common/Lint/CheckFluentReferences.cs

		cd $env:ENGINE_DIRECTORY
		Invoke-Expression ".\make.cmd version $env:ENGINE_VERSION"
		Invoke-Expression ".\make.cmd $command"
		Write-Host ""
		cd $templateDir
	}
}

$utilityPath = $env:ENGINE_DIRECTORY + "/bin/OpenRA.Utility.exe"

$configuration = "Release"
if ($args.Contains("CONFIGURATION=Debug"))
{
	$configuration = "Debug"
}

$execute = $command
if ($command.Length -gt 1)
{
	$execute = $command[0]
}

switch ($execute)
{
	"all" { All-Command }
	"launcher" { Launcher-Command }
	"gpu" { Gpu-Command }
	"version" { Version-Command }
	"clean" { Clean-Command }
	"test" { Test-Command }
	"check" { Check-Command }
	"check-scripts" { Check-Scripts-Command }
	Default { Write-Host ("Invalid command '{0}'" -f $command) }
}

# In case the script was called without any parameters we keep the window open
if ($args.Length -eq 0)
{
	WaitForInput
}
