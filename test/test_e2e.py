"""End-to-end tests: drive the real ffplay OCP backend through a real
``OCPMediaPlayer`` on a FakeBus via ovoscope's media harness.

The ffplay *engine* shells out via ``subprocess`` only when playback starts, so
``ovos_media_plugin_ffplay.ffplay.subprocess`` is mocked: no real ``ffplay``
binary is ever launched. Everything else is real: the OCP player routes the
play/pause/stop/seek requests to ``FFPlayOCPAudioService`` exactly as ovos-media
would at runtime.

Requires ``ovoscope[media]`` (pulls ovos-media).
"""
import unittest
from unittest.mock import MagicMock, patch

try:
    from ovoscope import OCPPlayerHarness
    from ovos_utils.ocp import MediaEntry, PlaybackType, PlayerState
    HAVE_HARNESS = True
except Exception:
    HAVE_HARNESS = False

import ovos_media_plugin_ffplay.ffplay as ffplay_engine
from ovos_media_plugin_ffplay import FFPlayOCPAudioService

URI = "http://example.com/song.mp3"


def _factory(bus):
    """Build the real ffplay audio backend for injection into the OCP player."""
    return FFPlayOCPAudioService({}, bus)


def _mock_subprocess():
    """A subprocess mock whose spawned process reports itself as running.

    ``poll()`` returning ``None`` keeps the engine's monitor thread alive so the
    pause/resume/stop transitions act on a live (mocked) process deterministically.
    """
    sub = MagicMock()
    sub.Popen.return_value.poll.return_value = None
    return sub


@unittest.skipUnless(HAVE_HARNESS, "ovoscope[media] not installed")
class TestFFPlayEndToEnd(unittest.TestCase):
    def test_play_pause_resume_stop_through_ocp(self):
        with patch.object(ffplay_engine, "subprocess", _mock_subprocess()):
            with OCPPlayerHarness(backend_factory=_factory) as h:
                entry = MediaEntry(uri=URI, playback=PlaybackType.AUDIO)

                h.play(entry)
                h.assert_player_state(PlayerState.PLAYING)
                h.assert_now_playing_uri(URI)
                # the real backend actually started its (mocked) ffplay engine
                self.assertIsNotNone(h.backend.ffplay.process)

                h.pause()
                h.assert_player_state(PlayerState.PAUSED)

                h.resume()
                h.assert_player_state(PlayerState.PLAYING)

                h.stop()
                h.assert_player_state(PlayerState.STOPPED)

    def test_backend_is_the_real_ffplay_plugin(self):
        with patch.object(ffplay_engine, "subprocess", _mock_subprocess()):
            with OCPPlayerHarness(backend_factory=_factory) as h:
                self.assertIsInstance(h.backend, FFPlayOCPAudioService)
                self.assertEqual(h.backend.supported_uris(),
                                 ["file", "http", "https"])


if __name__ == "__main__":
    unittest.main()
