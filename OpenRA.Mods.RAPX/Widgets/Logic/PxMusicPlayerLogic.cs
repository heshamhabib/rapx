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
using OpenRA.GameRules;
using OpenRA.Mods.Common.Traits;
using OpenRA.Mods.Common.Widgets;
using OpenRA.Widgets;

namespace OpenRA.Mods.RAPX.Widgets.Logic
{
	/// <summary>
	/// The Project X music player: a "now playing" header with the track cover and a grid of track cards.
	/// Same controls as the stock MusicPlayerLogic (play/pause, stop, next/previous, shuffle, loop, volume).
	/// </summary>
	public class PxMusicPlayerLogic : ChromeLogic
	{
		readonly MusicPlaylist playlist;
		readonly MusicInfo[] songs;

		// The track Play starts when nothing is playing: the last one picked or played
		MusicInfo selected;

		[ObjectCreator.UseCtor]
		public PxMusicPlayerLogic(Widget widget, World world, Action onExit)
		{
			playlist = world.WorldActor.Trait<MusicPlaylist>();
			songs = playlist.IsMusicAvailable ? playlist.AvailablePlaylist() : Array.Empty<MusicInfo>();
			selected = playlist.CurrentSong();

			MusicInfo Playing() => Game.Sound.CurrentMusic;
			MusicInfo Shown() => Playing() ?? selected;
			bool NoMusic() => !playlist.IsMusicAvailable;

			var hero = widget.Get<PxMusicHeroWidget>("HERO");
			hero.GetSong = Shown;
			hero.IsPlaying = () => Game.Sound.MusicPlaying;
			hero.GetSeek = () => Playing() != null ? Game.Sound.MusicSeekPosition : 0;
			hero.GetStatus = () =>
			{
				if (NoMusic())
					return "NO MUSIC INSTALLED";

				if (Playing() == null)
					return Shown() == null ? "STANDING BY" : "STOPPED";

				if (playlist.CurrentSongIsBackground)
					return Game.Sound.MusicPlaying ? "MENU THEME" : "MENU THEME · PAUSED";

				return Game.Sound.MusicPlaying ? "NOW PLAYING" : "PAUSED";
			};

			var totalLength = songs.Sum(s => s.Length);
			hero.GetSubtitle = () =>
			{
				var index = Array.IndexOf(songs, Shown());
				const string Album = "PROJECT X · ORIGINAL SOUNDTRACK";
				return index < 0 ? $"{songs.Length} TRACKS · {Album}" : $"TRACK {index + 1:D2} / {songs.Length:D2} · {Album}";
			};

			hero.GetNote = () => Game.Settings.Sound.Mute ? "SOUND IS MUTED" : "";
			hero.CanSeek = () => Playing() != null;
			hero.OnSeek = fraction =>
			{
				var song = Playing();
				if (song != null)
					Game.Sound.SeekMusic(fraction * song.Length);
			};

			var play = widget.Get<PxMusicButtonWidget>("BUTTON_PLAY");
			play.GetGlyph = () => Game.Sound.MusicPlaying ? PxMusicGlyph.Pause : PxMusicGlyph.Play;
			play.IsDisabled = NoMusic;
			play.OnClick = () =>
			{
				if (Game.Sound.MusicPlaying)
					Game.Sound.PauseMusic();
				else
					Play(Shown() ?? playlist.GetNextSong());
			};

			var stop = widget.Get<PxMusicButtonWidget>("BUTTON_STOP");
			stop.IsDisabled = () => NoMusic() || Playing() == null;
			stop.OnClick = () =>
			{
				selected = Playing() ?? selected;
				playlist.Stop();
			};

			var next = widget.Get<PxMusicButtonWidget>("BUTTON_NEXT");
			next.IsDisabled = NoMusic;
			next.OnClick = () => Play(playlist.GetNextSong());

			var prev = widget.Get<PxMusicButtonWidget>("BUTTON_PREV");
			prev.IsDisabled = NoMusic;
			prev.OnClick = () => Play(playlist.GetPrevSong());

			var shuffle = widget.Get<PxMusicButtonWidget>("BUTTON_SHUFFLE");
			shuffle.IsHighlighted = () => Game.Settings.Sound.Shuffle;
			shuffle.IsDisabled = NoMusic;
			shuffle.OnClick = () => Game.Settings.Sound.Shuffle ^= true;
			shuffle.GetTooltipText = () => Game.Settings.Sound.Shuffle ? "Shuffle: on" : "Shuffle: off";

			var loop = widget.Get<PxMusicButtonWidget>("BUTTON_LOOP");
			loop.IsHighlighted = () => Game.Settings.Sound.Repeat;
			loop.IsDisabled = NoMusic;
			loop.OnClick = () => Game.Sound.SetMusicLooped(!Game.Settings.Sound.Repeat);
			loop.GetTooltipText = () => Game.Settings.Sound.Repeat ? "Repeat track: on" : "Repeat track: off";

			var volume = widget.Get<SliderWidget>("VOLUME");
			volume.OnChange += x => Game.Sound.MusicVolume = x;
			volume.Value = Game.Sound.MusicVolume;

			// Speaker toggles the music volume between silent and the last level
			var speaker = widget.Get<PxMusicButtonWidget>("BUTTON_VOLUME");
			var lastVolume = Game.Sound.MusicVolume > 0.01f ? Game.Sound.MusicVolume : 0.5f;
			speaker.GetTooltipText = () => Game.Sound.MusicVolume > 0.01f ? "Mute music" : "Unmute music";
			speaker.OnClick = () =>
			{
				if (Game.Sound.MusicVolume > 0.01f)
				{
					lastVolume = Game.Sound.MusicVolume;
					volume.UpdateValue(0);
				}
				else
					volume.UpdateValue(lastVolume);
			};

			// Remember what is playing so Play resumes it after Stop
			var watcher = widget.GetOrNull<LogicTickerWidget>("SONG_WATCHER");
			if (watcher != null)
				watcher.OnTick = () =>
				{
					if (Playing() != null && !playlist.CurrentSongIsBackground)
						selected = Playing();
				};

			var grid = widget.Get<ScrollPanelWidget>("TRACK_GRID");
			var template = grid.Get<PxMusicCardWidget>("TRACK_TEMPLATE");
			grid.RemoveChildren();
			grid.Layout = new GridLayout(grid);

			var count = widget.GetOrNull<LabelWidget>("TRACK_COUNT");
			if (count != null)
				count.GetText = () => $"{songs.Length} TRACKS · {PxMusicCovers.Clock(totalLength)}";

			widget.Get("NO_MUSIC_LABEL").IsVisible = NoMusic;

			for (var i = 0; i < songs.Length; i++)
			{
				var song = songs[i];
				var card = (PxMusicCardWidget)template.Clone();
				card.Song = song;
				card.Number = i + 1;
				card.IsVisible = () => true;
				card.IsCurrent = () => Shown() == song;
				card.IsPlaying = () => Game.Sound.MusicPlaying;
				card.OnClick = () =>
				{
					if (Playing() == song && !playlist.CurrentSongIsBackground)
					{
						if (Game.Sound.MusicPlaying)
							Game.Sound.PauseMusic();
						else
							Game.Sound.PlayMusic();
					}
					else
						Play(song);
				};

				grid.AddChild(card);
			}
		}

		void Play(MusicInfo song)
		{
			if (song == null)
				return;

			selected = song;
			playlist.Play(song);
		}
	}
}
