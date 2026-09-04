"""Regression test: a track that ends naturally (ffplay -autoexit exits on
its own, no stop() ever called) must report ``PlaybackEvent.END_OF_MEDIA``
to the daemon, carrying the loaded uri for staleness checks.

Live symptom (ser9, ovos-media-plugin-ffplay 0.0.4a1): after a 6s wav
finished playing, ffplay exited but the daemon's player state stayed
PLAYING/LOADED_MEDIA forever - on_track_end() only fired the dead
_track_start_callback(None) path (ovos-media's now-unused
'ovos.audio.queue_end' message) and never reported anything upward.
"""
import os
import subprocess
import tempfile
import time
import unittest
import wave

from ovos_plugin_manager.templates.media import PlaybackEvent

from ovos_media_plugin_ffplay import FFPlayOCPAudioService


def _make_silent_wav(path: str, duration: float = 0.5, rate: int = 8000):
    n_frames = int(duration * rate)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * n_frames)


@unittest.skipUnless(subprocess.run(["which", "ffplay"],
                                     stdout=subprocess.DEVNULL).returncode == 0,
                      "ffplay binary not installed")
class TestNaturalEndOfMedia(unittest.TestCase):

    def test_natural_track_end_reports_end_of_media_with_uri(self):
        with tempfile.TemporaryDirectory() as d:
            wav_path = os.path.join(d, "silence.wav")
            _make_silent_wav(wav_path, duration=0.5)
            uri = f"file://{wav_path}"

            events = []
            service = FFPlayOCPAudioService({})
            service.bind_event_reporter(
                lambda event, **data: events.append((event, data)))
            service.load_track(uri)
            service.play()

            # wav is 0.5s; give ffplay generous time to exit and the
            # monitor thread to report it, without ever calling stop()
            # ourselves.
            deadline = time.time() + 10
            while time.time() < deadline and not any(
                    e == PlaybackEvent.END_OF_MEDIA for e, _ in events):
                time.sleep(0.1)

            self.assertIn(
                (PlaybackEvent.END_OF_MEDIA, {"uri": uri}), events,
                f"natural end-of-media never reported END_OF_MEDIA with uri; saw: {events}")


if __name__ == "__main__":
    unittest.main()
