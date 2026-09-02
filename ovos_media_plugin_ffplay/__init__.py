import time
from typing import List

from ovos_media_plugin_ffplay.ffplay import FFPlayAudioPlayer
from ovos_plugin_manager.templates.media import AudioPlayerBackend


class FFPlayOCPAudioService(AudioPlayerBackend):
    """
        FFPlay Audio backend
    """

    def __init__(self, config, bus=None):
        super().__init__(config, bus)
        self.ffplay = FFPlayAudioPlayer(on_track_start=self.on_track_start,
                                        on_track_end=self.on_track_end)
        self.normal_volume = self.config.get('initial_volume', 100)
        self.low_volume = self.config.get('low_volume', 50)

    def supported_uris(self) -> List[str]:
        """List of supported uri types.

        Returns:
            list: Supported uri's
        """
        return ['file', 'http', 'https']

    def on_track_start(self, uri: str = ""):
        if self._track_start_callback:
            self._track_start_callback(self._now_playing)

    def on_track_end(self, uri: str = ""):
        # Called from FFPlayAudioPlayer's monitor thread whenever the
        # ffplay process exits, whether that is a natural end-of-media
        # (autoexit) or a stop() we requested ourselves. ocp_stop() is
        # idempotent (it no-ops once self._now_playing is None), so it is
        # safe to call here even when stop() already triggered it - this
        # is the only path that reports a *natural* end-of-media upward,
        # since nothing else calls ocp_stop() for that case.
        if self._track_start_callback:
            self._track_start_callback(None)
        self.ocp_stop()

    def play(self):
        self.ffplay.play(self._now_playing)

    def stop(self):
        self.ffplay.stop()
        return True

    def pause(self):
        self.ffplay.pause()

    def resume(self):
        self.ffplay.resume()

    def lower_volume(self):
        self.ffplay.set_volume(self.low_volume)

    def restore_volume(self):
        self.ffplay.set_volume(self.normal_volume)

    def get_track_length(self) -> int:
        """
        getting the duration of the audio in milliseconds
        """
        return self.ffplay.track_length  # TODO not supported by ffplay

    def get_track_position(self) -> int:
        """
        get current position in milliseconds
        """
        return self.ffplay.playback_time

    def set_track_position(self, milliseconds):
        """
        go to position in milliseconds
          Args:
                milliseconds (int): number of milliseconds of final position
        """
        self.ffplay.set_track_position(milliseconds / 1000)


if __name__ == "__main__":
    from ovos_utils.fakebus import FakeBus

    url = "https://github.com/OpenVoiceOS/ovos-skill-easter-eggs/raw/refs/heads/dev/sounds/sing/drnimpo-robots.mp3"

    ffplay = FFPlayOCPAudioService({}, bus=FakeBus())
    ffplay.load_track(url)
    time.sleep(1)
    ffplay.play()
    from ovos_utils import wait_for_exit_signal

    wait_for_exit_signal()
