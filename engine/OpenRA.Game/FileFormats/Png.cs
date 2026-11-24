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
using System.Net;
#if NET6_0_OR_GREATER
using System.Runtime.Intrinsics;
using AdvSimd = System.Runtime.Intrinsics.Arm.AdvSimd;
#endif
using System.Text;
using ICSharpCode.SharpZipLib.Checksum;
using ICSharpCode.SharpZipLib.Zip.Compression;
using ICSharpCode.SharpZipLib.Zip.Compression.Streams;
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA.FileFormats
{
	public class Png
	{
		static readonly byte[] Signature = { 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a };

		public int Width { get; }
		public int Height { get; }
		public Color[] Palette { get; }
		public byte[] Data { get; }
		public SpriteFrameType Type { get; }
		public Dictionary<string, string> EmbeddedData = new();

		public int PixelStride => Type == SpriteFrameType.Indexed8 ? 1 : Type == SpriteFrameType.Rgb24 ? 3 : 4;

		public Png(Stream s)
		{
			if (!Verify(s))
				throw new InvalidDataException("PNG Signature is bogus");

			s.Position += 8;
			var headerParsed = false;
			var data = new List<byte>();
			Type = SpriteFrameType.Rgba32;

			byte bitDepth = 8;
			while (true)
			{
				var length = IPAddress.NetworkToHostOrder(s.ReadInt32());
				var type = s.ReadASCII(4);
				var content = s.ReadBytes(length);
				s.ReadInt32(); // crc

				if (!headerParsed && type != "IHDR")
					throw new InvalidDataException("Invalid PNG file - header does not appear first.");

				using (var ms = new MemoryStream(content))
				{
					switch (type)
					{
						case "IHDR":
						{
							if (headerParsed)
								throw new InvalidDataException("Invalid PNG file - duplicate header.");
							Width = IPAddress.NetworkToHostOrder(ms.ReadInt32());
							Height = IPAddress.NetworkToHostOrder(ms.ReadInt32());

							bitDepth = ms.ReadUInt8();
							var colorType = (PngColorType)ms.ReadUInt8();
							if (IsPaletted(bitDepth, colorType))
								Type = SpriteFrameType.Indexed8;
							else if (colorType == PngColorType.Color)
								Type = SpriteFrameType.Rgb24;

							Data = new byte[Width * Height * PixelStride];

							var compression = ms.ReadUInt8();
							ms.ReadUInt8(); // filter
							var interlace = ms.ReadUInt8();

							if (compression != 0)
								throw new InvalidDataException("Compression method not supported");

							if (interlace != 0)
								throw new InvalidDataException("Interlacing not supported");

							headerParsed = true;

							break;
						}

						case "PLTE":
						{
							Palette = new Color[length / 3];
							for (var i = 0; i < Palette.Length; i++)
							{
								var r = ms.ReadUInt8(); var g = ms.ReadUInt8(); var b = ms.ReadUInt8();
								Palette[i] = Color.FromArgb(r, g, b);
							}

							break;
						}

						case "tRNS":
						{
							if (Palette == null)
								throw new InvalidDataException("Non-Palette indexed PNG are not supported.");

							for (var i = 0; i < length; i++)
								Palette[i] = Color.FromArgb(ms.ReadUInt8(), Palette[i]);

							break;
						}

						case "IDAT":
						{
							data.AddRange(content);

							break;
						}

						case "tEXt":
						{
							var key = ms.ReadASCIIZ();
							EmbeddedData.Add(key, ms.ReadASCII(length - key.Length - 1));

							break;
						}

						case "IEND":
						{
							using (var ns = new MemoryStream(data.ToArray()))
							{
								// RAPX: the runtime's native zlib inflates several times faster than SharpZipLib's managed one
#if NET6_0_OR_GREATER
								using (var ds = new System.IO.Compression.ZLibStream(ns, System.IO.Compression.CompressionMode.Decompress))
#else
								using (var ds = new InflaterInputStream(ns))
#endif
								{
									var pxStride = PixelStride;
									var rowStride = Width * pxStride;
									var pixelsPerByte = 8 / bitDepth;
									var sourceRowStride = Exts.IntegerDivisionRoundingAwayFromZero(rowStride, pixelsPerByte);

									Span<byte> prevLine = new byte[rowStride];
									for (var y = 0; y < Height; y++)
									{
										var filter = (PngFilter)ds.ReadUInt8();
										ds.ReadBytes(Data, y * rowStride, sourceRowStride);
										var line = Data.AsSpan(y * rowStride, rowStride);

										// If the source has a bit depth of 1, 2 or 4 it packs multiple pixels per byte.
										// Unpack to bit depth of 8, yielding 1 pixel per byte.
										// This makes life easier for consumers of palleted data.
										if (bitDepth < 8)
										{
											var mask = 0xFF >> (8 - bitDepth);
											for (var i = sourceRowStride - 1; i >= 0; i--)
											{
												var packed = line[i];
												for (var j = 0; j < pixelsPerByte; j++)
												{
													var dest = i * pixelsPerByte + j;
													if (dest < line.Length) // Guard against last byte being only partially packed
														line[dest] = (byte)(packed >> (8 - (j + 1) * bitDepth) & mask);
												}
											}
										}

										// RAPX: 8-bit rows (all true colour art) take the vectorised path; packed low bit depths keep the original code
										if (bitDepth == 8)
										{
											UnfilterRow(filter, line, prevLine, pxStride);
											prevLine = line;
											continue;
										}

										switch (filter)
										{
											case PngFilter.None:
												break;
											case PngFilter.Sub:
												for (var i = pxStride; i < rowStride; i++)
													line[i] += line[i - pxStride];
												break;
											case PngFilter.Up:
												for (var i = 0; i < rowStride; i++)
													line[i] += prevLine[i];
												break;
											case PngFilter.Average:
												for (var i = 0; i < pxStride; i++)
													line[i] += Average(0, prevLine[i]);
												for (var i = pxStride; i < rowStride; i++)
													line[i] += Average(line[i - pxStride], prevLine[i]);
												break;
											case PngFilter.Paeth:
												for (var i = 0; i < pxStride; i++)
													line[i] += Paeth(0, prevLine[i], 0);
												for (var i = pxStride; i < rowStride; i++)
													line[i] += Paeth(line[i - pxStride], prevLine[i], prevLine[i - pxStride]);
												break;
											default:
												throw new InvalidOperationException("Unsupported Filter");
										}

										prevLine = line;
									}

									static byte Average(byte a, byte b) => (byte)((a + b) / 2);

									static byte Paeth(byte a, byte b, byte c)
									{
										var p = a + b - c;
										var pa = Math.Abs(p - a);
										var pb = Math.Abs(p - b);
										var pc = Math.Abs(p - c);

										return (pa <= pb && pa <= pc) ? a :
											(pb <= pc) ? b : c;
									}
								}
							}

							if (Type == SpriteFrameType.Indexed8 && Palette == null)
								throw new InvalidDataException("Non-Palette indexed PNG are not supported.");

							return;
						}
					}
				}
			}
		}

		public Png(byte[] data, SpriteFrameType type, int width, int height, Color[] palette = null,
			Dictionary<string, string> embeddedData = null)
		{
			var expectLength = width * height;
			if (palette == null)
				expectLength *= 4;

			if (data.Length != expectLength)
				throw new InvalidDataException("Input data does not match expected length");

			Type = type;
			Width = width;
			Height = height;

			switch (type)
			{
				case SpriteFrameType.Indexed8:
				case SpriteFrameType.Rgba32:
				case SpriteFrameType.Rgb24:
				{
					// Data is already in a compatible format
					Data = data;
					if (type == SpriteFrameType.Indexed8)
						Palette = palette;

					break;
				}

				case SpriteFrameType.Bgra32:
				case SpriteFrameType.Bgr24:
				{
					// Convert to big endian
					Data = new byte[data.Length];
					var stride = PixelStride;
					for (var i = 0; i < width * height; i++)
					{
						Data[stride * i] = data[stride * i + 2];
						Data[stride * i + 1] = data[stride * i + 1];
						Data[stride * i + 2] = data[stride * i + 0];

						if (type == SpriteFrameType.Bgra32)
							Data[stride * i + 3] = data[stride * i + 3];
					}

					break;
				}

				default:
					throw new InvalidDataException($"Unhandled SpriteFrameType {type}");
			}

			if (embeddedData != null)
				EmbeddedData = embeddedData;
		}

		public static bool Verify(Stream s)
		{
			var pos = s.Position;
			var isPng = Signature.Aggregate(true, (current, t) => current && s.ReadUInt8() == t);
			s.Position = pos;
			return isPng;
		}

		/// <summary>
		/// RAPX: undoes one row's filter in place, with NEON for the four-byte (RGBA) pixels nearly all HD art uses.
		/// Gives exactly the same bytes as the per-byte loops in the constructor, about three times faster.
		/// </summary>
		static unsafe void UnfilterRow(PngFilter filter, Span<byte> lineSpan, Span<byte> prevSpan, int bpp)
		{
			var n = lineSpan.Length;
			fixed (byte* line = lineSpan)
			fixed (byte* prev = prevSpan)
			{
				// Four-byte pixels, read and written as one uint each
				var line32 = (uint*)line;
				var prev32 = (uint*)prev;
				switch (filter)
				{
					case PngFilter.None:
						break;

					case PngFilter.Sub when bpp == 4:
					{
						var count = n / 4;
						for (var i = 1; i < count; i++)
							line32[i] = AddBytes(line32[i], line32[i - 1]);
						break;
					}

					case PngFilter.Sub:
						for (var i = bpp; i < n; i++)
							line[i] += line[i - bpp];
						break;

					case PngFilter.Up:
					{
						var count = n / 4;
						for (var i = 0; i < count; i++)
							line32[i] = AddBytes(line32[i], prev32[i]);
						for (var i = count * 4; i < n; i++)
							line[i] += prev[i];
						break;
					}

#if NET6_0_OR_GREATER
					case PngFilter.Average when bpp == 4 && AdvSimd.IsSupported:
					{
						var a = Vector128<ushort>.Zero;
						for (var i = 0; i < n; i += 4)
						{
							var b = Widen(prev + i);
							var x = AdvSimd.ExtractNarrowingLower(AdvSimd.Add(Widen(line + i), AdvSimd.ShiftRightLogical(AdvSimd.Add(a, b), 1)));
							line32[i / 4] = x.AsUInt32().ToScalar();
							a = AdvSimd.ZeroExtendWideningLower(x);
						}

						break;
					}
#endif

					case PngFilter.Average:
						for (var i = 0; i < bpp; i++)
							line[i] += (byte)(prev[i] >> 1);
						for (var i = bpp; i < n; i++)
							line[i] += (byte)((line[i - bpp] + prev[i]) >> 1);
						break;

#if NET6_0_OR_GREATER
					case PngFilter.Paeth when bpp == 4 && AdvSimd.IsSupported:
					{
						// a = left (already decoded), b = up, c = up-left: one pixel per step, its four channels in 16-bit lanes
						var a = Vector128<short>.Zero;
						var c = a;
						for (var i = 0; i < n; i += 4)
						{
							var b = Widen(prev + i).AsInt16();
							var pa0 = AdvSimd.Subtract(b, c);
							var pb0 = AdvSimd.Subtract(a, c);
							var pc = AdvSimd.Abs(AdvSimd.Add(pa0, pb0));
							var pa = AdvSimd.Abs(pa0);
							var pb = AdvSimd.Abs(pb0);
							var useA = AdvSimd.And(AdvSimd.CompareLessThanOrEqual(pa, pb), AdvSimd.CompareLessThanOrEqual(pa, pc)).AsInt16();
							var useB = AdvSimd.CompareLessThanOrEqual(pb, pc).AsInt16();
							var predicted = AdvSimd.BitwiseSelect(useA, a, AdvSimd.BitwiseSelect(useB, b, c));
							var x = AdvSimd.ExtractNarrowingLower(AdvSimd.Add(Widen(line + i).AsInt16(), predicted).AsUInt16());
							line32[i / 4] = x.AsUInt32().ToScalar();
							a = AdvSimd.ZeroExtendWideningLower(x).AsInt16();
							c = b;
						}

						break;
					}
#endif

					case PngFilter.Paeth:
						for (var i = 0; i < bpp; i++)
							line[i] += prev[i];
						for (var i = bpp; i < n; i++)
						{
							int a = line[i - bpp], b = prev[i], c = prev[i - bpp];
							var pa = b - c;
							var pb = a - c;
							var pc = Math.Abs(pa + pb);
							pa = Math.Abs(pa);
							pb = Math.Abs(pb);
							line[i] += (byte)(pa <= pb && pa <= pc ? a : pb <= pc ? b : c);
						}

						break;

					default:
						throw new InvalidOperationException("Unsupported Filter");
				}
			}

#if NET6_0_OR_GREATER
			static Vector128<ushort> Widen(byte* p) => AdvSimd.ZeroExtendWideningLower(Vector64.CreateScalar(((uint*)p)[0]).AsByte());
#endif

			// Adds four bytes to four bytes, each wrapping on its own (no carry into the next byte)
			static uint AddBytes(uint x, uint y)
			{
				const uint High = 0x80808080u;
				return ((x & ~High) + (y & ~High)) ^ ((x ^ y) & High);
			}
		}

		[Flags]
		enum PngColorType : byte { Indexed = 1, Color = 2, Alpha = 4 }
		enum PngFilter : byte { None, Sub, Up, Average, Paeth }

		static bool IsPaletted(byte bitDepth, PngColorType colorType)
		{
			if (bitDepth <= 8 && colorType == (PngColorType.Indexed | PngColorType.Color))
				return true;

			if (bitDepth == 8 && colorType == (PngColorType.Color | PngColorType.Alpha))
				return false;

			if (bitDepth == 8 && colorType == PngColorType.Color)
				return false;

			throw new InvalidDataException("Unknown pixel format");
		}

		static void WritePngChunk(Stream output, string type, Stream input)
		{
			input.Position = 0;

			var typeBytes = Encoding.ASCII.GetBytes(type);
			output.Write(IPAddress.HostToNetworkOrder((int)input.Length));
			output.Write(typeBytes);

			var data = input.ReadAllBytes();
			output.Write(data);

			var crc32 = new Crc32();
			crc32.Update(typeBytes);
			crc32.Update(data);
			output.Write(IPAddress.NetworkToHostOrder((int)crc32.Value));
		}

		public byte[] Save()
		{
			using (var output = new MemoryStream())
			{
				output.Write(Signature);
				using (var header = new MemoryStream())
				{
					header.Write(IPAddress.HostToNetworkOrder(Width));
					header.Write(IPAddress.HostToNetworkOrder(Height));
					header.WriteByte(8); // Bit depth

					var colorType = Type == SpriteFrameType.Indexed8 ? PngColorType.Indexed | PngColorType.Color :
						Type == SpriteFrameType.Rgb24 ? PngColorType.Color : PngColorType.Color | PngColorType.Alpha;
					header.WriteByte((byte)colorType);

					header.WriteByte(0); // Compression
					header.WriteByte(0); // Filter
					header.WriteByte(0); // Interlacing

					WritePngChunk(output, "IHDR", header);
				}

				var alphaPalette = false;
				if (Palette != null)
				{
					using (var palette = new MemoryStream())
					{
						foreach (var c in Palette)
						{
							palette.WriteByte(c.R);
							palette.WriteByte(c.G);
							palette.WriteByte(c.B);
							alphaPalette |= c.A > 0;
						}

						WritePngChunk(output, "PLTE", palette);
					}
				}

				if (alphaPalette)
				{
					using (var alpha = new MemoryStream())
					{
						foreach (var c in Palette)
							alpha.WriteByte(c.A);

						WritePngChunk(output, "tRNS", alpha);
					}
				}

				using (var data = new MemoryStream())
				{
					using (var compressed = new DeflaterOutputStream(data, new Deflater(Deflater.BEST_COMPRESSION)))
					{
						var rowStride = Width * PixelStride;
						for (var y = 0; y < Height; y++)
						{
							// Assuming no filtering for simplicity
							const byte FilterType = 0;
							compressed.WriteByte(FilterType);
							compressed.Write(Data, y * rowStride, rowStride);
						}

						compressed.Flush();
						compressed.Finish();

						WritePngChunk(output, "IDAT", data);
					}
				}

				foreach (var kv in EmbeddedData)
				{
					using (var text = new MemoryStream())
					{
						text.Write(Encoding.ASCII.GetBytes(kv.Key + (char)0 + kv.Value));
						WritePngChunk(output, "tEXt", text);
					}
				}

				WritePngChunk(output, "IEND", new MemoryStream());
				return output.ToArray();
			}
		}

		public void Save(string path)
		{
			File.WriteAllBytes(path, Save());
		}
	}
}
