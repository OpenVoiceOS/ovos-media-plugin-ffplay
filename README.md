# ovos-media-plugin-ffplay

ffplay plugin for [ovos-audio](https://github.com/OpenVoiceOS/ovos-audio) and [ovos-media](https://github.com/OpenVoiceOS/ovos-media)

## Install

`pip install ovos-media-plugin-ffplay`

## Configuration

edit your mycroft.conf with any ffplay players you want to expose

```javascript
{
  "Audio": {
    "backends": {
      "ffplay": {
        "type": "ovos_ffplay",
        "active": true
      }
    }
  }
}
```

## Python usage

direct access to ffplay is provided via `FFPlayAudioPlayer`

```python
import time
from ovos_media_plugin_ffplay.ffplay import FFPlayAudioPlayer

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

```
