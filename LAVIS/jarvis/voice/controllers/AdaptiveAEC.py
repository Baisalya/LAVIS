# AdaptiveAEC.py
from aiortc import MediaStreamTrack
import av
import numpy as np
import pyaudio
import asyncio


# AdaptiveAEC.py (patched recv_pcm16_sync)
class MicEchoCancellingTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, source_track):
        super().__init__()
        self.track = source_track
        # create a single event loop once
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

    async def recv(self):
        frame = await self.track.recv()
        return frame

    def recv_pcm16_sync(self):
        """Blocking PCM16 read using the persistent loop (no spam)."""
        frame = self._loop.run_until_complete(self.recv())
        pcm16 = frame.to_ndarray().astype("int16").tobytes()
        return pcm16


class PyAudioStreamTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, rate=16000, chunk=480):
        super().__init__()
        self.rate = rate
        self.chunk = chunk
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            input=True,
            frames_per_buffer=chunk
        )

    async def recv(self):
        """Async receive from mic (returns av.AudioFrame)."""
        data = self.stream.read(self.chunk, exception_on_overflow=False)
        frame = av.AudioFrame.from_ndarray(
            np.frombuffer(data, dtype=np.int16).reshape(1, -1),
            format="s16",
            layout="mono"
        )
        frame.sample_rate = self.rate
        return frame
