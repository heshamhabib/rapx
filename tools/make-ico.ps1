# Builds a multi-resolution Windows .ico from the packaging artwork PNGs.
#
# The Linux/macOS packaging path shells out to ImageMagick (packaging/windows/buildpackage.sh), which is
# not something a Windows dev box has. This does the same job with System.Drawing so that `make.ps1 all`
# can give the launcher its icon.
#
# Sizes up to 48px are written as uncompressed BGRA DIBs, which every Windows shell surface understands.
# 256px is embedded as PNG, the only form the icon directory can describe at that size.

param(
	[Parameter(Mandatory = $true)][string]$ArtworkDir,
	[Parameter(Mandatory = $true)][string]$OutFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

# System.Drawing resolves relative paths against the process working directory rather than PowerShell's
$ArtworkDir = (Resolve-Path $ArtworkDir).Path
if (-not [System.IO.Path]::IsPathRooted($OutFile))
{
	$OutFile = Join-Path (Get-Location).Path $OutFile
}

$dibSizes = @(16, 24, 32, 48)
$pngSizes = @(256)

function Get-SourceBitmap([int]$size)
{
	$exact = Join-Path $ArtworkDir ("icon_{0}x{0}.png" -f $size)
	if (Test-Path $exact)
	{
		return [System.Drawing.Bitmap]::new($exact)
	}

	# Fall back to the largest available source and scale down
	$source = Get-ChildItem (Join-Path $ArtworkDir "icon_*x*.png") | Sort-Object Length | Select-Object -Last 1
	$original = [System.Drawing.Bitmap]::new($source.FullName)
	try
	{
		$scaled = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
		$g = [System.Drawing.Graphics]::FromImage($scaled)
		try
		{
			$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
			$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
			$g.DrawImage($original, 0, 0, $size, $size)
		}
		finally { $g.Dispose() }

		return $scaled
	}
	finally { $original.Dispose() }
}

# An uncompressed icon image: BITMAPINFOHEADER, the colour rows bottom-up as BGRA, then the 1bpp AND mask.
# biHeight is doubled because the header describes colour rows plus mask rows.
function Get-DibBytes([System.Drawing.Bitmap]$bitmap)
{
	$size = $bitmap.Width
	$stream = [System.IO.MemoryStream]::new()
	$writer = [System.IO.BinaryWriter]::new($stream)
	try
	{
		$writer.Write([uint32]40)
		$writer.Write([int32]$size)
		$writer.Write([int32]($size * 2))
		$writer.Write([uint16]1)
		$writer.Write([uint16]32)
		$writer.Write([uint32]0)
		$writer.Write([uint32]($size * $size * 4))
		0..3 | ForEach-Object { $writer.Write([uint32]0) }

		for ($y = $size - 1; $y -ge 0; $y--)
		{
			for ($x = 0; $x -lt $size; $x++)
			{
				$p = $bitmap.GetPixel($x, $y)
				$writer.Write([byte]$p.B)
				$writer.Write([byte]$p.G)
				$writer.Write([byte]$p.R)
				$writer.Write([byte]$p.A)
			}
		}

		# AND mask: zeroed, since the alpha channel already carries the transparency.
		# Rows are padded to a 4 byte boundary.
		$maskStride = [math]::Floor(($size + 31) / 32) * 4
		$writer.Write([byte[]]::new($maskStride * $size))

		$writer.Flush()

		# Comma operator: without it PowerShell unrolls the array into single bytes
		return ,$stream.ToArray()
	}
	finally { $writer.Dispose(); $stream.Dispose() }
}

function Get-PngBytes([System.Drawing.Bitmap]$bitmap)
{
	$stream = [System.IO.MemoryStream]::new()
	try
	{
		$bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
		return ,$stream.ToArray()
	}
	finally { $stream.Dispose() }
}

$images = @()
foreach ($size in ($dibSizes + $pngSizes))
{
	$bitmap = Get-SourceBitmap $size
	try
	{
		if ($pngSizes -contains $size)
		{
			$bytes = Get-PngBytes $bitmap
		}
		else
		{
			$bytes = Get-DibBytes $bitmap
		}

		$images += [pscustomobject]@{ Size = $size; Bytes = [byte[]]$bytes }
	}
	finally { $bitmap.Dispose() }
}

$out = [System.IO.MemoryStream]::new()
$writer = [System.IO.BinaryWriter]::new($out)
try
{
	# ICONDIR
	$writer.Write([uint16]0)
	$writer.Write([uint16]1)
	$writer.Write([uint16]$images.Count)

	# ICONDIRENTRY per image; 256 is written as 0 because the field is a single byte
	$offset = 6 + 16 * $images.Count
	foreach ($image in $images)
	{
		$writer.Write([byte]($image.Size % 256))
		$writer.Write([byte]($image.Size % 256))
		$writer.Write([byte]0)
		$writer.Write([byte]0)
		$writer.Write([uint16]1)
		$writer.Write([uint16]32)
		$writer.Write([uint32]$image.Bytes.Length)
		$writer.Write([uint32]$offset)
		$offset += $image.Bytes.Length
	}

	foreach ($image in $images)
	{
		$writer.Write([byte[]]$image.Bytes, 0, $image.Bytes.Length)
	}

	$writer.Flush()
	$directory = Split-Path -Parent $OutFile
	if ($directory -and -not (Test-Path $directory))
	{
		New-Item -ItemType Directory -Force $directory | Out-Null
	}

	[System.IO.File]::WriteAllBytes($OutFile, $out.ToArray())
}
finally { $writer.Dispose(); $out.Dispose() }

Write-Host ("Wrote {0} ({1} images, {2:N0} bytes)" -f $OutFile, $images.Count, (Get-Item $OutFile).Length)
