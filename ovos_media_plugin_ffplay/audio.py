from typing import List

from ovos_media_plugin_ffplay.ffplay import FFPlayAudioPlayer
from ovos_plugin_manager.templates.audio import AudioBackend
from ovos_utils.log import LOG


class FFPlayAudioService(AudioBackend):
    """
        FFPlay Audio backend
    """

    def __init__(self, config, bus, name='ffplay'):
        super().__init__(config, bus, name)
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

    def on_track_start(self):
        if self._track_start_callback:
            self._track_start_callback(
                self.track_info().get('name', self.ffplay.media_path))

    def on_track_end(self):
        self._track_start_callback(None)

    def play(self, repeat=False):
        self.ffplay.stop()
        self.ffplay.play(self._now_playing)

    def stop(self):
        self.ffplay.stop()

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


def load_service(base_config, bus):
    backends = base_config.get('backends', {})
    services = [(b, backends[b]) for b in backends
                if backends[b].get('type') in ['ffplay', 'ovos_ffplay'] and
                backends[b].get('active', True)]
    instances = [FFPlayAudioService(s[1], bus, s[0]) for s in services]
    if len(instances) == 0:
        LOG.warning("No FFPlay backends have been configured")
    return instances
