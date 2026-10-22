import wave

import numpy as np
from fastapi.testclient import TestClient

from melody_snake.server import app
from melody_snake.theory.midi import continuous_midi_to_frequency
from tests.audio_utils import sine


def _write_wav(path, samples, sr):
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_sources_endpoint():
    client = TestClient(app)
    r = client.get("/sources")
    assert r.status_code == 200
    data = r.json()
    assert "loopback" in data
    assert "microphone" in data


def test_ws_file_source_streams_pitch_frames(tmp_path):
    sr = 44100
    notes = [60, 64, 62, 67]
    segs = [sine(continuous_midi_to_frequency(m), 0.4, sr) for m in notes]
    gap = np.zeros(int(0.1 * sr), dtype=np.float32)
    samples = np.concatenate([segs[0], gap, segs[1], gap, segs[2], gap, segs[3]])
    wav = tmp_path / "melody.wav"
    _write_wav(wav, samples, sr)

    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start", "source": "file", "file": str(wav)})
        frames = []
        for _ in range(1000):
            msg = ws.receive_json()
            if msg.get("type") == "status" and msg.get("state") == "ended":
                break
            if msg.get("type") == "pitch":
                frames.append(msg)

    voiced = [f for f in frames if f["voiced"] and f["confidence"] > 0.5]
    seq = []
    for f in voiced:
        m = f["roundedMidi"]
        if not seq or m != seq[-1]:
            seq.append(m)

    assert seq == notes
