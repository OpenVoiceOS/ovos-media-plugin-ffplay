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

from ovos_plugin_manager.templates.media import AudioPlayerBackend
from ovos_plugin_manager.templates.audio import AudioBackend

from ovos_media_plugin_ffplay import FFPlayOCPAudioService
from ovos_media_plugin_ffplay.audio import FFPlayAudioService, load_service


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
        with open(os.path.join(here, "setup.py")) as f:
            setup_src = f.read()
        self.assertIn("opm.media.audio", setup_src)
        self.assertIn("mycroft.plugin.audioservice", setup_src)
        self.assertIn(
            "ovos_media_plugin_ffplay:FFPlayOCPAudioService", setup_src)
        self.assertIn("ovos_media_plugin_ffplay.audio", setup_src)


if __name__ == "__main__":
    unittest.main()
