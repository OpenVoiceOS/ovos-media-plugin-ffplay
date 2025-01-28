import os
import signal
import subprocess
import threading
import time
from typing import Optional, Callable

Callback = Callable[[], None]  # for typing


class FFPlayAudioPlayer:
    """
    A simple media player class that uses `ffplay` (part of ffmpeg) to play audio or video.

    Requirements:
        - ffmpeg must be installed on your system and accessible in the PATH.
        - `ffplay` command should be available.

    Methods:
        - play(media_path: str): Starts playing the media from the specified path.
        - pause(): Pauses the media.
        - resume(): Resumes the media if it was paused.
        - stop(): Stops the media playback.
        - is_media_playing() -> bool: Checks if the media is currently playing.
        - playback_time -> int: Returns the current playback time in milliseconds.
    """

    def __init__(self,
                 on_track_start: Optional[Callback] = None,
                 on_track_end: Optional[Callback] = None,
                 on_pause: Optional[Callback] = None,
                 on_resume: Optional[Callback] = None) -> None:
        """
        Initializes the FFPlayMediaPlayer with default values.
        """
        self.process: Optional[subprocess.Popen] = None
        self._start_ts: float = 0.0
        self._playback_time_accumulator: float = 0.0
        self.is_playing: threading.Event = threading.Event()
        self.end_of_media: threading.Event = threading.Event()
        self.media_path: Optional[str] = None
        self.on_track_start = on_track_start
        self.on_track_end = on_track_end
        self.on_pause = on_pause
        self.on_resume = on_resume
        self._callbacks_enabled = True
        self._volume = 100

    @property
    def volume(self) -> int:
        """0 to 100"""
        return min(100, max(0, self._volume))

    @property
    def playback_time(self) -> int:
        """
        Returns the current playback time in milliseconds. If the media is playing,
        the time elapsed since the last start is added to the accumulated playback time.

        Returns:
            int: The current playback time in milliseconds.
        """
        delta = 0
        if self._start_ts and self.is_playing.is_set():
            delta = time.time() - self._start_ts
        return int((self._playback_time_accumulator + delta) * 1000)

    @property
    def track_length(self) -> int:
        """
        getting the duration of the audio in milliseconds
        """
        return self.playback_time + 1  # TODO - parse stdout from ffplay

    def play(self, media_path: str,
             start_time: float = 0,
             volume: Optional[int] = None) -> None:
        """
        Starts playing the media from the specified file path or URL.

        Args:
            media_path (str): The path or URL to the media file to play.
            start_time (int): position to start playback in seconds
            volume (int): volume from 1 to 100
        """
        volume = volume or self._volume
        volume = min(100, max(0, volume))
        if self.process and self.process.poll() is None:
            self.stop()

        self.media_path = media_path
        self._volume = volume
        if start_time:
            cmd = ['ffplay', '-volume', str(volume), '-ss', str(start_time), '-nodisp', '-autoexit', '-vn', media_path]
        else:
            cmd = ['ffplay', '-volume', str(volume), '-nodisp', '-autoexit', '-vn', media_path]
        # Redirect stdout and stderr to /dev/null to avoid buffer overflow
        self.process = subprocess.Popen(cmd,
                                        stdout=open(os.devnull, 'w'),  # Redirect stdout to /dev/null
                                        stderr=open(os.devnull, 'w')  # Redirect stderr to /dev/null
                                        )
        self.is_playing.set()
        self._start_ts = time.time()
        self._playback_time_accumulator = start_time
        if self.on_track_start and self._callbacks_enabled:
            try:
                self.on_track_start()
            except Exception as e:
                print(f"Error in on_track_start callback: {e}")

        # Monitor the process to detect when it finishes
        self._monitor_playback()

    def _monitor_playback(self) -> None:
        """
        Monitors the playback and calls the end-of-track callback when the process finishes.
        """
        self.end_of_media.clear()

        def check_process():
            try:
                while self.process.poll() is None:  # Check if process is still running
                    self.end_of_media.wait(1)  # Sleep a bit before checking again
            except AttributeError:
                pass # self.stop() called
            self.is_playing.clear()
            self.end_of_media.set()
            # Once process ends, call the on_track_end callback
            if self.on_track_end and self._callbacks_enabled:
                try:
                    self.on_track_end()
                except Exception as e:
                    print(f"Error in on_track_end callback: {e}")
            self.process = None

        # Start a background thread to monitor the playback process
        monitor_thread = threading.Thread(target=check_process, daemon=True)
        monitor_thread.start()

    def wait_for_end_of_playback(self):
        self.end_of_media.wait()

    def pause(self) -> None:
        """
        Pauses the media by sending the SIGSTOP signal to the process.
        """
        if self.is_playing.is_set():
            self.process.send_signal(signal.SIGSTOP)  # Send SIGSTOP signal to pause the process
            self.is_playing.clear()
            self._playback_time_accumulator += time.time() - self._start_ts
            self._start_ts = 0
            if self.on_pause and self._callbacks_enabled:
                try:
                    self.on_pause()
                except Exception as e:
                    print(f"Error in on_pause callback: {e}")

    def resume(self) -> None:
        """
        Resumes the media by sending the SIGCONT signal to the process.
        """
        if not self.is_playing.is_set():
            self.process.send_signal(signal.SIGCONT)  # Send SIGCONT signal to resume the process
            self.is_playing.set()
            self._start_ts = time.time()
            if self.on_resume and self._callbacks_enabled:
                try:
                    self.on_resume()
                except Exception as e:
                    print(f"Error in on_resume callback: {e}")

    def stop(self) -> None:
        """
        Stops the media playback and kills the `ffplay` process.
        """
        if self.process:
            self.process.kill()
            self.is_playing.clear()
            self.end_of_media.set()
            self._playback_time_accumulator = self._start_ts = 0
            self.process = None

    def set_track_position(self, seconds: float):
        """
        go to position in seconds
          Args:
                seconds (float): number of seconds of final position
        """
        self._callbacks_enabled = False
        self.play(media_path=self.media_path,
                  start_time=seconds,
                  volume=self._volume)
        self._callbacks_enabled = True

    def set_volume(self, volume: int):
        """
        go to position in seconds
          Args:
                seconds (float): number of seconds of final position
        """
        if self.is_playing.is_set():
            self._callbacks_enabled = False
            self.play(media_path=self.media_path,
                      start_time=self.playback_time / 1000,
                      volume=volume)
            self._callbacks_enabled = True
        else:
            self._volume = volume

if __name__ == "__main__":
    # Example usage: playing an MP3 file from a URL
    url = "https://github.com/OpenVoiceOS/ovos-skill-easter-eggs/raw/refs/heads/dev/sounds/sing/drnimpo-robots.mp3"

    # Create player instance
    player = FFPlayAudioPlayer()

    # Play media
    player.play(url, volume=100)
    print(f"Playback time: {player.playback_time} ms")
    time.sleep(5)
    print(f"Playback time: {player.playback_time} ms")

    # Pause media
    player.pause()
    time.sleep(2)
    print(f"Playback time: {player.playback_time} ms")

    # Resume media
    player.resume()
    time.sleep(1)
    player.set_track_position(65)
    print(f"Playback time: {player.playback_time} ms")
    print(f"Volume: {player.volume}")
    time.sleep(3)
    player.set_volume(30)
    print(f"Volume: {player.volume}")
    time.sleep(6)
    player.set_volume(70)
    print(f"Volume: {player.volume}")
    player.wait_for_end_of_playback()
