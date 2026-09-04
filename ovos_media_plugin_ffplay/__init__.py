from typing import List

from ovos_media_plugin_ffplay.ffplay import FFPlayAudioPlayer
from ovos_plugin_manager.templates.media import AudioPlayerBackend, PlaybackEvent


class FFPlayOCPAudioService(AudioPlayerBackend):
    """
        FFPlay Audio backend
    """
    can_seek = False
    can_pause = True

    def __init__(self, config, bus=None):
        super().__init__(config, bus)
        self.ffplay = FFPlayAudioPlayer(on_track_start=self.on_track_start,
                                        on_track_end=self.on_track_end)
        self.normal_volume = self.config.get('initial_volume', 100)
        self.low_volume = self.config.get('low_volume', 50)
        self._loaded_uri = None

    def supported_uris(self) -> List[str]:
        """List of supported uri types.

        Returns:
            list: Supported uri's
        """
        return ['file', 'http', 'https']

    def on_track_start(self, uri: str = ""):
        self.report(PlaybackEvent.TRACK_START, uri=self._loaded_uri)

    def on_track_end(self, uri: str = ""):
        # Called from FFPlayAudioPlayer's monitor thread whenever the
        # ffplay process exits - whether that is a natural end-of-media
        # (autoexit), a stop() we requested, or the child dying because the
        # uri was bad/unreachable. report_track_end() is the only place
        # that classifies the exit: a nonzero/failed exit is always an
        # ERROR (never mistaken for a successful end-of-media just because
        # the process exited), and otherwise it uses the base class's
        # pending _stop_requested flag to tell an explicit stop from a
        # natural end. Never call report_track_end from _stop() - it is
        # observed exactly once, here.
        proc = self.ffplay.process
        rc = proc.returncode if proc is not None else None
        error = f"ffplay exited with code {rc}" if rc else None
        self.report_track_end(uri=self._loaded_uri, error=error)

    def load_track(self, uri: str, metadata: dict = None) -> bool:
        """Load a track for playback.

        ffplay has no separate load step - spawning *is* playing - so this
        just records the uri to play and reports nothing; the daemon owns
        the LOADED_MEDIA transition on the True return.
        """
        self._loaded_uri = uri
        return True

    def play(self):
        try:
            self.ffplay.play(self._loaded_uri)
        except Exception as e:
            self.report(PlaybackEvent.ERROR, error=str(e), uri=self._loaded_uri)

    def _stop(self) -> bool:
        was_playing = self.ffplay.process is not None
        self.ffplay.stop()
        return was_playing

    def pause(self):
        self.ffplay.pause()

    def resume(self):
        self.ffplay.resume()

    def lower_volume(self):
        self.ffplay.set_volume(self.low_volume)

    def restore_volume(self):
        self.ffplay.set_volume(self.normal_volume)


if __name__ == "__main__":
    from ovos_utils.fakebus import FakeBus

    url = "https://github.com/OpenVoiceOS/ovos-skill-easter-eggs/raw/refs/heads/dev/sounds/sing/drnimpo-robots.mp3"

    ffplay = FFPlayOCPAudioService({}, bus=FakeBus())
    ffplay.bind_event_reporter(lambda event, **data: print(event, data))
    ffplay.load_track(url)
    ffplay.play()
    from ovos_utils import wait_for_exit_signal

    wait_for_exit_signal()
