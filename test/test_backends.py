"""Unit tests for the FFPlay backends.

``ffplay`` shells out via ``subprocess`` only when playback starts, so the
backends construct without launching anything. To be safe, ``subprocess`` is
patched so a stray ``play()`` cannot spawn a process. The tests assert
wiring/contract, not real playback: both the new ovos-media backend and the
legacy ovos-audio adapter build, expose the right base classes, and the
supported URIs + entry points are declared correctly.
"""
import unittest
from unittest.mock import MagicMock, patch

from ovos_plugin_manager.templates.media import AudioPlayerBackend, PlaybackEvent
from ovos_plugin_manager.templates.audio import AudioBackend
from ovos_utils.fakebus import FakeBus

from ovos_media_plugin_ffplay import FFPlayOCPAudioService
from ovos_media_plugin_ffplay.audio import FFPlayAudioService, load_service

URI = "http://example.com/song.mp3"


# guard: nothing in these tests should ever launch ffplay
@patch("ovos_media_plugin_ffplay.ffplay.subprocess", MagicMock())
class TestNewBackend(unittest.TestCase):
    def test_audio_backend_is_audioplayerbackend(self):
        svc = FFPlayOCPAudioService({}, bus=MagicMock())
        self.assertIsInstance(svc, AudioPlayerBackend)
        self.assertTrue(hasattr(svc, "play"))
        self.assertTrue(hasattr(svc, "lower_volume"))

    def test_supported_uris(self):
        svc = FFPlayOCPAudioService({}, bus=MagicMock())
        self.assertEqual(svc.supported_uris(), ['file', 'http', 'https'])

    def test_capabilities(self):
        svc = FFPlayOCPAudioService({}, bus=MagicMock())
        self.assertFalse(svc.can_seek)
        self.assertTrue(svc.can_pause)


@patch("ovos_media_plugin_ffplay.ffplay.subprocess", MagicMock())
class TestV2EventReporting(unittest.TestCase):
    """MediaBackend v2 contract: physical events go through report(), never
    the bus - the daemon owns every ``ovos.common_play.*`` transition."""

    def _service(self):
        svc = FFPlayOCPAudioService({}, bus=MagicMock())
        events = []
        svc.bind_event_reporter(lambda event, **data: events.append((event, data)))
        return svc, events

    def test_load_track_returns_bool_and_reports_nothing(self):
        svc, events = self._service()
        self.assertTrue(svc.load_track(URI))
        self.assertEqual(events, [], "load_track must not report - the "
                                      "daemon owns LOADED_MEDIA")

    def test_track_start_reports_with_uri(self):
        svc, events = self._service()
        svc.load_track(URI)
        svc.on_track_start()
        self.assertIn((PlaybackEvent.TRACK_START, {"uri": URI}), events)

    def test_explicit_stop_reports_stopped_not_end_of_media(self):
        svc, events = self._service()
        # keep the monitor thread's poll() loop alive until stop() kills it,
        # like test_e2e.py's _mock_subprocess
        with patch("ovos_media_plugin_ffplay.ffplay.subprocess") as sub:
            sub.Popen.return_value.poll.return_value = None
            svc.load_track(URI)
            svc.play()
            self.assertIsNotNone(svc.ffplay.process)
            svc.stop()
        # the monitor thread's on_track_end fires once the (mocked)
        # process is gone - simulate that here since subprocess is mocked
        svc.on_track_end()
        self.assertIn((PlaybackEvent.STOPPED, {"uri": URI}), events)
        self.assertNotIn((PlaybackEvent.END_OF_MEDIA, {"uri": URI}), events)

    def test_stop_when_not_playing_reports_nothing(self):
        svc, events = self._service()
        svc.load_track(URI)
        self.assertFalse(svc.stop())
        self.assertEqual(events, [])

    def test_nonzero_exit_reports_error_not_end_of_media(self):
        # live-found bug: a nonexistent/failed uri's ffplay child exits
        # with a nonzero return code; that must never be mistaken for a
        # successful end-of-media just because the process exited.
        svc, events = self._service()
        with patch("ovos_media_plugin_ffplay.ffplay.subprocess") as sub:
            sub.Popen.return_value.poll.return_value = None
            sub.Popen.return_value.returncode = 1
            svc.load_track(URI)
            svc.play()
            svc.on_track_end()
        error_events = [e for e in events if e[0] == PlaybackEvent.ERROR]
        self.assertEqual(len(error_events), 1)
        event, data = error_events[0]
        self.assertEqual(data.get("uri"), URI)
        self.assertIn("1", data.get("error", ""))
        self.assertNotIn((PlaybackEvent.END_OF_MEDIA, {"uri": URI}), events)

    def test_zero_exit_reports_end_of_media(self):
        svc, events = self._service()
        with patch("ovos_media_plugin_ffplay.ffplay.subprocess") as sub:
            sub.Popen.return_value.poll.return_value = None
            sub.Popen.return_value.returncode = 0
            svc.load_track(URI)
            svc.play()
            svc.on_track_end()
        self.assertIn((PlaybackEvent.END_OF_MEDIA, {"uri": URI}), events)

    def test_full_verb_cycle_emits_no_common_play_bus_messages(self):
        bus = FakeBus()
        seen = []

        def _catch_all(msg):
            if msg.msg_type.startswith("ovos.common_play."):
                seen.append(msg.msg_type)

        bus.on("message", _catch_all)

        svc = FFPlayOCPAudioService({}, bus=bus)
        svc.bind_event_reporter(lambda event, **data: None)
        with patch("ovos_media_plugin_ffplay.ffplay.subprocess") as sub:
            sub.Popen.return_value.poll.return_value = None
            svc.load_track(URI)
            svc.play()
            svc.on_track_start()
            svc.pause()
            svc.resume()
            svc.get_track_position()
            svc.set_track_position(1000)
            svc.stop()
            svc.on_track_end()

        self.assertEqual(seen, [], f"backend emitted state on the bus: {seen}")


@patch("ovos_media_plugin_ffplay.ffplay.subprocess", MagicMock())
class TestLegacyAdapter(unittest.TestCase):
    def test_legacy_is_audiobackend(self):
        svc = FFPlayAudioService({}, bus=MagicMock(), name='ffplay')
        self.assertIsInstance(svc, AudioBackend)
        self.assertTrue(hasattr(svc, "play"))
        self.assertTrue(hasattr(svc, "lower_volume"))

    def test_supported_uris(self):
        svc = FFPlayAudioService({}, bus=MagicMock(), name='ffplay')
        self.assertEqual(svc.supported_uris(), ['file', 'http', 'https'])

    def test_load_service_builds_active_ffplay_backends(self):
        cfg = {"backends": {
            "myffplay": {"type": "ffplay", "active": True},
            "off": {"type": "ovos_ffplay", "active": False},
            "other": {"type": "vlc", "active": True},
        }}
        services = load_service(cfg, bus=MagicMock())
        self.assertEqual(len(services), 1)
        self.assertIsInstance(services[0], FFPlayAudioService)

    def test_load_service_empty(self):
        self.assertEqual(load_service({"backends": {}}, bus=MagicMock()), [])


class TestEntryPoints(unittest.TestCase):
    """Both the new and legacy entry-point groups must be declared."""

    def test_setup_declares_new_and_legacy_groups(self):
        import os
        here = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(here, "pyproject.toml")) as f:
            setup_src = f.read()
        self.assertIn("opm.media.audio", setup_src)
        self.assertIn("mycroft.plugin.audioservice", setup_src)
        self.assertIn(
            "ovos_media_plugin_ffplay:FFPlayOCPAudioService", setup_src)
        self.assertIn("ovos_media_plugin_ffplay.audio", setup_src)


if __name__ == "__main__":
    unittest.main()
