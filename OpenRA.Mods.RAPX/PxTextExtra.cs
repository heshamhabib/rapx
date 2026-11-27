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
using System.Linq;

namespace OpenRA.Mods.RAPX
{
	/// <summary>
	/// English words that reach the screen from rules data rather than from a literal (sides, production queues,
	/// armour and target types, description terms), listed so tools/lang/l10n.py collects them for translation.
	/// </summary>
	public static class PxTextExtra
	{
		public static readonly string[] DataWords =
		{
			// Sides
			PxText.N("Union"), PxText.N("Vanguard"), PxText.N("Random"),

			// Production queues and Produces types
			PxText.N("Building"), PxText.N("Defense"), PxText.N("Infantry"), PxText.N("Vehicle"), PxText.N("Aircraft"),
			PxText.N("Ship"), PxText.N("Airlift"), PxText.N("Bomber"), PxText.N("Helicopter"), PxText.N("Plane"),
			PxText.N("Satellite"), PxText.N("Dog"), PxText.N("Soldier"), PxText.N("Boat"), PxText.N("Submarine"),

			// Armour types
			PxText.N("Light"), PxText.N("Heavy"),

			// Missile classes an interceptor can stop
			PxText.N("ATGM"), PxText.N("Ballistic"), PxText.N("Cruise"), PxText.N("Drone"), PxText.N("Hypersonic"), PxText.N("Rocket"),

			// "Strong vs X and Y" wording, parsed by PxTooltipDescWidget
			PxText.N("Strong vs "), PxText.N("Weak vs "), PxText.N(", and "), PxText.N(" and "), PxText.N(", "),
		};

		/// <summary>Target words in unit descriptions; translations must use exactly these words.</summary>
		public static readonly string[] Terms =
		{
			PxText.N("Aircraft"), PxText.N("Vehicles"), PxText.N("Infantry"), PxText.N("Buildings"), PxText.N("Anti-Air"),
			PxText.N("Tanks"), PxText.N("Ships"), PxText.N("Submarines"), PxText.N("Light armor"), PxText.N("Missiles"),
			PxText.N("Ground units"), PxText.N("Fighters"), PxText.N("Naval units"), PxText.N("Drones"), PxText.N("Robots"),
			PxText.N("Light vehicles"), PxText.N("Helicopters"), PxText.N("Satellites"), PxText.N("Rockets"), PxText.N("Dogs"),
		};

		/// <summary>The English description term a translated one stands for (for the term's icon); unknown terms pass through.</summary>
		public static string EnglishTerm(string term)
		{
			var english = Terms.FirstOrDefault(t => string.Equals(PxText.T(t), term, StringComparison.OrdinalIgnoreCase));
			return english ?? term;
		}
	}
}
