"""Enumerate audio sources for the UI's source selector."""

import pyaudiowpatch as pyaudio


def list_sources():
    """Return loopback + microphone devices plus default indices."""
    p = pyaudio.PyAudio()
    result = {"loopback": [], "microphone": [], "defaultLoopbackIndex": None, "defaultMicIndex": None}
    try:
        for d in p.get_loopback_device_info_generator():
            result["loopback"].append({
                "index": int(d["index"]),
                "name": d["name"],
                "sampleRate": int(d["defaultSampleRate"]),
                "channels": int(d["maxInputChannels"]),
            })

        for d in p.get_device_info_generator():
            if d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice", False):
                result["microphone"].append({
                    "index": int(d["index"]),
                    "name": d["name"],
                    "sampleRate": int(d["defaultSampleRate"]),
                    "channels": int(d["maxInputChannels"]),
                })

        try:
            result["defaultLoopbackIndex"] = int(p.get_default_wasapi_loopback()["index"])
        except OSError:
            pass
        try:
            result["defaultMicIndex"] = int(p.get_default_input_device_info()["index"])
        except OSError:
            pass
    finally:
        p.terminate()
    return result
