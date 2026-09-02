"""Regression test: a track that ends naturally (ffplay -autoexit exits on
its own, no stop() ever called) must report MediaState.END_OF_MEDIA /
PlayerState.STOPPED on the real bus, exactly like an explicit stop does.

Live symptom (ser9, ovos-media-plugin-ffplay 0.0.4a1): after a 6s wav
finished playing, ffplay exited but the daemon's player state stayed
PLAYING/LOADED_MEDIA forever - on_track_end() only fired the dead
_track_start_callback(None) path (ovos-media's now-unused
'ovos.audio.queue_end' message) and never called ocp_stop(), which is the
only thing that emits MediaState.END_OF_MEDIA on
'ovos.common_play.media.state'.
"""
import os
import subprocess
import tempfile
import time
import unittest
import wave

from ovos_utils.fakebus import FakeBus
from ovos_utils.ocp import MediaState, PlayerState

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

    def test_natural_track_end_emits_end_of_media(self):
        with tempfile.TemporaryDirectory() as d:
            wav_path = os.path.join(d, "silence.wav")
            _make_silent_wav(wav_path, duration=0.5)

            bus = FakeBus()
            states = []
            bus.on("ovos.common_play.media.state",
                   lambda msg: states.append(msg.data.get("state")))
            player_states = []
            bus.on("ovos.common_play.player.state",
                   lambda msg: player_states.append(msg.data.get("state")))

            service = FFPlayOCPAudioService({}, bus=bus)
            service.load_track(f"file://{wav_path}")
            service.play()

            # wav is 0.5s; give ffplay generous time to exit and the
            # monitor thread to report it, without ever calling stop()
            # ourselves.
            deadline = time.time() + 10
            while time.time() < deadline and MediaState.END_OF_MEDIA not in states:
                time.sleep(0.1)

            self.assertIn(
                MediaState.END_OF_MEDIA, states,
                f"natural end-of-media never emitted END_OF_MEDIA; saw: {states}")
            self.assertIn(
                PlayerState.STOPPED, player_states,
                f"natural end-of-media never emitted PlayerState.STOPPED; saw: {player_states}")


if __name__ == "__main__":
    unittest.main()
