"""Regression test: the real ffplay child must not be left as a zombie.

Spawns the real ``ffplay`` binary against a tiny generated wav file (no
subprocess mocking here, unlike test_backends.py / test_e2e.py) and checks
/proc/<pid>/stat directly for the 'Z' (zombie) state, both after natural
end-of-track and after an explicit mid-play stop().
"""
import os
import time
import unittest
import wave
from tempfile import NamedTemporaryFile

from ovos_media_plugin_ffplay.ffplay import FFPlayAudioPlayer


def _make_wav(path: str, duration: float = 0.3) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * int(8000 * duration))


def _is_zombie(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat") as f:
            # third field (after "pid (comm)") is the state
            return f.read().rsplit(")", 1)[1].split()[0] == "Z"
    except FileNotFoundError:
        return False  # already reaped, gone from /proc entirely


class TestNoZombies(unittest.TestCase):
    def setUp(self):
        self._wav = NamedTemporaryFile(suffix=".wav", delete=False)
        self._wav.close()
        _make_wav(self._wav.name)

    def tearDown(self):
        os.unlink(self._wav.name)

    def test_no_zombie_after_natural_end(self):
        player = FFPlayAudioPlayer()
        player.play(self._wav.name)
        pid = player.process.pid
        player.wait_for_end_of_playback()
        # give the monitor thread's reap a moment to land
        for _ in range(50):
            if not _is_zombie(pid):
                break
            time.sleep(0.1)
        self.assertFalse(_is_zombie(pid), f"pid {pid} left as zombie after natural end")

    def test_no_zombie_after_stop(self):
        player = FFPlayAudioPlayer()
        player.play(self._wav.name)
        pid = player.process.pid
        time.sleep(0.05)  # stop it mid-play, before it exits on its own
        player.stop()
        for _ in range(50):
            if not _is_zombie(pid):
                break
            time.sleep(0.1)
        self.assertFalse(_is_zombie(pid), f"pid {pid} left as zombie after stop()")


if __name__ == "__main__":
    unittest.main()
