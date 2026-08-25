"""Audio-device and notebook-UI plumbing for the Gemini Live voice notebook.

The teaching code (Live session config, tool declaration, the send/receive loop)
lives in the notebook. This module holds the boilerplate around it: bridging
PortAudio's callback threads to asyncio at the sample rates the Live API expects,
the widgets that show captions and deep-agent activity, and the task juggling that
ends a session cleanly.

    Gemini Live: microphone input is 16 kHz PCM, model audio output is 24 kHz PCM,
    both mono, signed 16-bit little-endian.
"""

import asyncio
import html as html_lib
import traceback
import threading
import time
from collections.abc import AsyncIterator, Callable, Coroutine

import ipywidgets as widgets
import sounddevice as sd
from IPython.display import display

from util.pretty import LiveActivityPanel

MIC_RATE = 16000
SPEAKER_RATE = 24000
_CHANNELS = 1
_DTYPE = "int16"
# Buffer sizes, measured on a MacBook Pro mic — they dominate the gap between you
# speaking and the model hearing you. Forcing an input blocksize makes it *worse*:
# blocksize=1600 reports 765 ms of input latency, 800 -> 459 ms, while letting
# PortAudio choose (0) with a small latency hint gives ~218 ms. Asking CoreAudio for
# 16 kHz costs ~230 ms of that in resampling (the device runs at 48 kHz natively,
# where the same stream measures ~51 ms); closing that gap needs a filtered
# downsampler, which is more machinery than this notebook wants.
_MIC_BLOCK = 0        # 0 = let PortAudio pick the lowest-latency block size
_LATENCY_IN = 0.02    # seconds; raise it if the mic starts dropping frames
_LATENCY_OUT = "low"  # output is cheap: ~34 ms here vs sounddevice's "high" default


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
        # blocksize 0 yields variable-length frames, which is fine: the Live API takes
        # a stream of PCM and does not care where the chunk boundaries fall.
        self._rate = rate
        self._blocksize = blocksize
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: sd.RawInputStream | None = None

    def _on_audio(self, indata, frames, time, status):
        # Runs on PortAudio's thread; hop back onto the event loop thread-safely.
        data = bytes(indata)
        self._loop.call_soon_threadsafe(self._queue.put_nowait, data)

    def _open(self) -> sd.RawInputStream:
        stream = sd.RawInputStream(
            samplerate=self._rate,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=self._blocksize,
            latency=_LATENCY_IN,
            callback=self._on_audio,
        )
        try:
            stream.start()
        except Exception:
            stream.close()
            raise
        return stream

    def __enter__(self) -> "MicInput":
        self._loop = asyncio.get_running_loop()
        try:
            self._stream = self._open()
        except Exception:
            # The mic may still be claimed by a previous interrupted run (see
            # reset_audio). Clear PortAudio's state and try once more, so a live demo
            # can just re-run the cell instead of restarting the kernel.
            reset_audio()
            self._stream = self._open()
        return self

    def __exit__(self, *exc):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, None)

    async def frames(
        self,
        mute_while: Callable[[], bool] | None = None,
        chunk_ms: int = 20,
    ) -> AsyncIterator[bytes]:
        """Yield captured PCM in chunks of at least `chunk_ms`, until the stream closes.

        With `blocksize=0` PortAudio favours latency and can hand back ~1 ms buffers.
        Forwarding those one per WebSocket message would mean ~1000 JSON+base64 sends a
        second — enough event-loop churn to starve the connection's own keepalive — so
        they are coalesced here. 20 ms costs an order of magnitude less overhead and is
        noise next to the ~200 ms the input device already adds.

        `mute_while` is polled once per captured buffer; audio arriving while it returns
        True is dropped. Pass `SpeakerOutput.is_speaking` for half-duplex capture: the
        mic goes deaf while the assistant speaks, so the speakers cannot echo back into
        it. That costs barge-in — you wait for the assistant to finish before speaking —
        and it is the only reliable answer without acoustic echo cancellation. On
        headphones there is no echo path at all: omit `mute_while` for true barge-in.
        """
        min_bytes = int(self._rate * 2 * chunk_ms / 1000)  # 2 bytes per int16 sample
        pending = bytearray()
        while True:
            frame = await self._queue.get()
            if frame is None:
                if pending:
                    yield bytes(pending)
                return
            if mute_while is not None and mute_while():
                pending.clear()  # drop it: this is the assistant's own voice
                continue
            pending.extend(frame)
            if len(pending) >= min_bytes:
                yield bytes(pending)
                pending.clear()


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
        self._finished_at = float("-inf")  # when the queue last ran dry

    def _on_request(self, outdata, frames, time_info, status):
        # Runs on PortAudio's thread. Fill the request from the buffer; pad with
        # silence when we've run dry so the stream never underflows/crackles.
        wanted = len(outdata)
        with self._lock:
            chunk = bytes(self._buffer[:wanted])
            del self._buffer[: len(chunk)]
            drained = not self._buffer
        outdata[: len(chunk)] = chunk
        if len(chunk) < wanted:
            outdata[len(chunk):] = b"\x00" * (wanted - len(chunk))
        if chunk and drained:
            # The last queued audio just went to the device: start the tail timer.
            self._finished_at = time.monotonic()

    def __enter__(self) -> "SpeakerOutput":
        self._stream = sd.RawOutputStream(
            samplerate=self._rate,
            channels=_CHANNELS,
            dtype=_DTYPE,
            latency=_LATENCY_OUT,
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
        self._finished_at = time.monotonic()  # nothing left to play: start the tail

    async def drain(self, timeout: float = 10.0) -> None:
        """Wait until queued audio has finished playing (including the tail).

        Use before closing the devices on a deliberate hang-up, so a farewell is not
        clipped the way an interrupted sentence would be.

        Bounded, because the wait is for silence that something else has to produce:
        if the device stops consuming the buffer — a stream that never started, a
        headset unplugged mid-sentence — an unbounded loop would hang the hang-up and
        the session would never end.
        """
        deadline = time.monotonic() + timeout
        while self.is_speaking() and time.monotonic() < deadline:
            await asyncio.sleep(0.05)

    def is_speaking(self, tail: float = 0.8) -> bool:
        """True while audio is still coming out of the speakers.

        Gate the microphone on this, not on when audio last *arrived*. Gemini Live
        sends a turn's audio in a burst — several seconds of speech can land in under
        one — so "a packet arrived recently" says nothing about whether the speakers
        are still going. Playing audio is what the microphone can hear, so this reports
        queued-and-not-yet-played, plus a short `tail` for the sound already in
        PortAudio's own buffer and the room's echo.
        """
        with self._lock:
            queued = bool(self._buffer)
        if queued:
            return True
        return time.monotonic() - self._finished_at < tail


_TRANSCRIPT_FONT = 24  # big type so the transcript reads from the back of a room


class VoiceUI:
    """Stop button, live captions, and a deep-agent activity panel for a voice session.

    Owns the notebook widgets so the session loop itself keeps only the Live protocol.
    Feed it each message's `server_content` via `caption()`, hand `activity` to a
    streamed research run, and wait on the `stopped` event.
    """

    def __init__(self, font_size: int = _TRANSCRIPT_FONT, show_latency: bool = False):
        self.stopped = asyncio.Event()
        self._font_size = font_size
        self._show_latency = show_latency
        self._spoke_at: float | None = None  # when your last transcribed word arrived
        self._button = widgets.Button(description="Stop", button_style="danger", icon="stop")
        self._button.on_click(lambda _: self.stopped.set())
        self._transcript = widgets.HTML(value="")
        display(self._button, self._transcript)
        self.activity = LiveActivityPanel()  # displays itself, below the transcript
        self._user: list[str] = []
        self._assistant: list[str] = []
        self._resumed = False  # the next assistant line continues an interrupted one

    def reset(self) -> None:
        """Clear the transcript and the stop flag, ready for another session."""
        self.stopped.clear()
        self._transcript.value = ""
        self._user.clear()
        self._assistant.clear()
        self._resumed = False

    def log(self, role: str, text: str = "") -> None:
        """Append one attributed line to the transcript."""
        self._transcript.value += (
            f"<div style='margin:8px 0;font-size:{self._font_size}px;line-height:1.5;'>"
            f"<b>{html_lib.escape(role)}</b> {html_lib.escape(text)}</div>"
        )

    def caption(self, server_content) -> None:
        """Accumulate Live input/output transcription into speaker-attributed lines.

        Transcripts stream in fragments, so they are buffered: the user's line is
        flushed when the assistant starts replying, the assistant's when the server
        marks the turn complete.
        """
        transcription = server_content.input_transcription
        if transcription and transcription.text:
            self._user.append(transcription.text)
            self._spoke_at = time.monotonic()

        transcription = server_content.output_transcription
        if transcription and transcription.text:
            self.flush_user()
            self._assistant.append(transcription.text)

        if server_content.interrupted and self._assistant:
            self.log(self._assistant_label(), "".join(self._assistant) + " —")
            self._assistant.clear()
            # What the model says next is a fresh generation continuing the same reply,
            # not a new turn — and it often re-words the tail it was cut off mid-way
            # through, so splicing the two together would read as garbled repetition.
            self._resumed = True

        if server_content.turn_complete and self._assistant:
            self.log(self._assistant_label(), "".join(self._assistant))
            self._assistant.clear()
            self._resumed = False

    def flush_user(self) -> None:
        """Print the buffered user line, before a reply or tool call interleaves."""
        if self._user:
            self.log("🧑 You:", "".join(self._user))
            self._user.clear()
            self._resumed = False  # a real user turn ends any resumed reply

    def note_reply_audio(self) -> None:
        """Report how long the first audio of a reply took, once per turn.

        Measured from your last transcribed word, so it covers the server's
        end-of-speech wait plus the model's own time to first audio — the two parts
        of the turnaround that live outside this notebook.
        """
        if not self._show_latency or self._spoke_at is None:
            return
        self.flush_user()  # your line is still buffered; print it before its timing
        self.log("⚡", f"{time.monotonic() - self._spoke_at:.1f}s to first audio")
        self._spoke_at = None

    def _assistant_label(self) -> str:
        """Label the assistant line, marking one that resumes after an interruption."""
        return "↳ Assistant:" if self._resumed else "🤖 Assistant:"

    def researching(self, topic: str) -> None:
        """Note a hand-off to the deep agent in the transcript."""
        self.flush_user()
        self.log("🔎 Researching:", topic)

    def hanging_up(self) -> None:
        """Note that the assistant is ending the session."""
        self.flush_user()
        self.log("👋 Goodbye:", "ending the session")


async def run_until_stopped(
    *coro_fns: Callable[[], Coroutine],
    stop: asyncio.Event,
    timeout: float | None = None,
) -> None:
    """Run coroutine functions concurrently until `stop` is set or `timeout` elapses.

    A coroutine that *returns* is fine and does not end the session — a message pump
    can legitimately finish (Gemini Live's `receive()` ends at every turn) while the
    rest keep going. A coroutine that *raises* does end it: the error is re-raised
    here rather than swallowed, so a dropped WebSocket cannot look like a quiet exit.

    However the session ends — stop button, time cap, failing task, kernel interrupt —
    every task is cancelled and awaited before returning, so the audio device context
    managers unwind cleanly.
    """
    errors: list[BaseException] = []

    async def guarded(fn: Callable[[], Coroutine]) -> None:
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # noqa: BLE001 - a dead pump must end the session
            errors.append(exc)
            stop.set()

    tasks = [asyncio.create_task(guarded(fn)) for fn in coro_fns]
    try:
        await asyncio.wait_for(stop.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    if errors:
        raise errors[0]


class LatestJob:
    """Run at most one background job; starting a new one supersedes the old.

    A detached task needs an owner. Something has to hold the reference, cancel the
    previous job when it is replaced, wait for that cancellation to actually land
    before the replacement starts touching shared state, and cancel whatever is still
    running when the session ends. That bookkeeping is the same every time, so it
    lives here rather than in the loop.
    """

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._key = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, coro, key=None):
        """Start `coro`, cancelling any job still running. Returns the superseded key.

        The cancellation is awaited, not just requested: the outgoing job may hold
        something the replacement is about to reuse (the activity panel), and without
        the await the two would race over it.
        """
        superseded = None
        if self.running:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            superseded = self._key
        self._task, self._key = asyncio.create_task(coro), key
        return superseded

    def cancel(self) -> None:
        """Cancel the running job, if any — the session is over."""
        if self.running:
            self._task.cancel()


_current_session: asyncio.Task | None = None


async def start_session(coro, ui=None) -> asyncio.Task:
    """Run a voice session as a background task and hand back the task.

    Not `await`ed, deliberately. A cell parked on `await` stops the kernel handling
    further shell messages, so every ipywidgets callback — the Stop button included —
    sits queued until the cell finishes, which is precisely when it is no longer
    needed. Letting the cell return keeps the kernel free to deliver clicks while the
    event loop goes on driving the session.

    Re-running the cell supersedes the previous session instead of leaving two of them
    fighting over the microphone, and a detached task's exception would otherwise be
    swallowed, so failures are reported here.
    """
    global _current_session
    if _current_session is not None and not _current_session.done():
        _current_session.cancel()
        await asyncio.gather(_current_session, return_exceptions=True)

    task = asyncio.create_task(coro)

    def _report(finished: asyncio.Task) -> None:
        if finished.cancelled():
            return
        error = finished.exception()
        if error is None:
            return
        if ui is not None:
            ui.log("⚠️ Session error:", f"{type(error).__name__}: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)

    task.add_done_callback(_report)
    _current_session = task
    return task
