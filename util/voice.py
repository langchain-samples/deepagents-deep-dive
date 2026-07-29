"""Audio-device plumbing for the Gemini Live voice notebook.

The teaching code (Live session config, tool handling, the async loop) lives in
the notebook. This module holds only the boilerplate: bridging PortAudio's
callback threads to asyncio, at the sample rates the Live API expects.

    Gemini Live: microphone input is 16 kHz PCM, model audio output is 24 kHz PCM,
    both mono, signed 16-bit little-endian.
"""

import asyncio
import threading
from collections.abc import AsyncIterator

import sounddevice as sd

MIC_RATE = 16000
SPEAKER_RATE = 24000
_CHANNELS = 1
_DTYPE = "int16"
_MIC_BLOCK = 1600  # 100 ms of 16 kHz mono int16 per frame sent to the model


def reset_audio() -> None:
    """Release any wedged audio device from a previous (interrupted) run.

    In a notebook, interrupting a cell mid-capture — or a run that ends in
    CancelledError before __exit__ fires — can leave the input stream open and the
    microphone still claimed by the kernel. The next run then fails to open it with
    PortAudio -9986 / CoreAudio AUHAL -10851 ("Invalid Property Value"), even though
    the device is otherwise fine. Re-initialising PortAudio clears that state in place,
    so a live demo can just re-run the cell instead of restarting the kernel.
    """
    try:
        sd._terminate()
    except Exception:
        pass
    sd._initialize()


class MicInput:
    """Capture microphone PCM and hand it to asyncio as raw byte frames.

    Use as an async-context resource inside a running event loop:

        with MicInput() as mic:
            async for frame in mic.frames():
                await session.send_realtime_input(audio=Blob(data=frame, ...))
    """

    def __init__(self, rate: int = MIC_RATE, blocksize: int = _MIC_BLOCK):
        self._rate = rate
        self._blocksize = blocksize
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: sd.RawInputStream | None = None

    def _on_audio(self, indata, frames, time, status):
        # Runs on PortAudio's thread; hop back onto the event loop thread-safely.
        data = bytes(indata)
        self._loop.call_soon_threadsafe(self._queue.put_nowait, data)

    def __enter__(self) -> "MicInput":
        self._loop = asyncio.get_running_loop()
        self._stream = sd.RawInputStream(
            samplerate=self._rate,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=self._blocksize,
            callback=self._on_audio,
        )
        self._stream.start()
        return self

    def __exit__(self, *exc):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, None)

    async def frames(self) -> AsyncIterator[bytes]:
        """Yield captured PCM frames until the stream is closed."""
        while True:
            frame = await self._queue.get()
            if frame is None:
                return
            yield frame


class SpeakerOutput:
    """Play 24 kHz PCM the model streams back, with barge-in support.

    Audio arrives in bursts; a callback drains an internal buffer so playback is
    gapless. `flush()` drops everything still queued — call it when the model
    reports it was interrupted so stale speech stops immediately.
    """

    def __init__(self, rate: int = SPEAKER_RATE):
        self._rate = rate
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._stream: sd.RawOutputStream | None = None

    def _on_request(self, outdata, frames, time, status):
        # Runs on PortAudio's thread. Fill the request from the buffer; pad with
        # silence when we've run dry so the stream never underflows/crackles.
        wanted = len(outdata)
        with self._lock:
            chunk = bytes(self._buffer[:wanted])
            del self._buffer[: len(chunk)]
        outdata[: len(chunk)] = chunk
        if len(chunk) < wanted:
            outdata[len(chunk):] = b"\x00" * (wanted - len(chunk))

    def __enter__(self) -> "SpeakerOutput":
        self._stream = sd.RawOutputStream(
            samplerate=self._rate,
            channels=_CHANNELS,
            dtype=_DTYPE,
            callback=self._on_request,
        )
        self._stream.start()
        return self

    def __exit__(self, *exc):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

    def play(self, pcm: bytes) -> None:
        """Queue a chunk of PCM for gapless playback."""
        with self._lock:
            self._buffer.extend(pcm)

    def flush(self) -> None:
        """Drop all queued audio (barge-in): the user interrupted the model."""
        with self._lock:
            self._buffer.clear()
