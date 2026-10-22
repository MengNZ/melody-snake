"""FastAPI + WebSocket server.

The backend owns ONLY audio capture + pitch estimation. It streams
`PitchEstimate` frames (JSON) to the frontend, which does note segmentation,
track building, intervals and solfege.

Protocol (client -> server, JSON over /ws):
  {"type": "start", "source": "system"|"microphone"|"file", "file": "..."}
  {"type": "pause"}
  {"type": "resume"}
  {"type": "stop"}

Protocol (server -> client):
  {"type": "pitch", ...PitchEstimate fields...}
  {"type": "status", "state": "running"|"paused"|"ended"|"error",
   "sampleRate": N, "source": "...", "error": "..."|null}
"""

import asyncio
import os
import threading
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .audio.devices import list_sources
from .audio.file_source import FileAudioSource
from .audio.loopback_source import LoopbackSource
from .audio.mic_source import MicSource
from .engine import StreamingPitchProcessor

app = FastAPI(title="Melody Snake backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/sources")
def sources():
    return list_sources()


def _build_source(source_type, file_path, device_index):
    if source_type == "file":
        if not file_path:
            raise ValueError("file source requires a 'file' path")
        src = FileAudioSource(file_path)
    elif source_type == "microphone":
        src = MicSource(device_index)
    elif source_type == "system":
        src = LoopbackSource(device_index)
    else:
        raise ValueError(f"unknown source type: {source_type}")
    src.open()
    return src


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()

    frame_queue: asyncio.Queue = asyncio.Queue(maxsize=4096)
    stop_event = threading.Event()
    pause_event = threading.Event()
    audio_thread = None

    def send_status_threadsafe(payload):
        def _put():
            if not frame_queue.full():
                frame_queue.put_nowait(payload)
        loop.call_soon_threadsafe(_put)

    def on_frame(frame):
        def _put():
            if not frame_queue.full():
                frame_queue.put_nowait(frame)
        loop.call_soon_threadsafe(_put)

    def audio_loop(source):
        processor = StreamingPitchProcessor(source.sample_rate, on_frame=on_frame)
        try:
            while not stop_event.is_set():
                if pause_event.is_set():
                    time.sleep(0.01)
                    continue
                block = source.read()
                if block is None:
                    break  # end of stream (file) or device closed
                processor.push(block.samples)
        finally:
            source.close()
            send_status_threadsafe({"type": "status", "state": "ended", "sampleRate": source.sample_rate, "source": None, "error": None})

    async def send_loop():
        while True:
            frame = await frame_queue.get()
            await websocket.send_json(frame)

    async def recv_loop():
        nonlocal audio_thread
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            t = msg.get("type")
            if t == "start":
                stop_event.clear()
                pause_event.clear()
                try:
                    source = _build_source(
                        msg.get("source", "system"),
                        msg.get("file"),
                        msg.get("deviceIndex"),
                    )
                except Exception as exc:  # noqa: BLE001 - report to client
                    await frame_queue.put({"type": "status", "state": "error", "sampleRate": None, "source": msg.get("source"), "error": str(exc)})
                    continue
                await frame_queue.put({"type": "status", "state": "running", "sampleRate": source.sample_rate, "source": msg.get("source"), "error": None})
                audio_thread = threading.Thread(target=audio_loop, args=(source,), daemon=True)
                audio_thread.start()
            elif t == "pause":
                pause_event.set()
                await frame_queue.put({"type": "status", "state": "paused", "sampleRate": None, "source": None, "error": None})
            elif t == "resume":
                pause_event.clear()
                await frame_queue.put({"type": "status", "state": "running", "sampleRate": None, "source": None, "error": None})
            elif t == "stop":
                stop_event.set()
                break

    send_task = asyncio.create_task(send_loop())
    try:
        await recv_loop()
    finally:
        stop_event.set()
        if audio_thread is not None:
            audio_thread.join(timeout=2.0)
        send_task.cancel()
        try:
            await send_task
        except (asyncio.CancelledError, RuntimeError):
            pass


# Serve the built frontend (production single-process mode). Registered last so
# /health, /sources and /ws take precedence over the SPA fallback.
_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="static")
