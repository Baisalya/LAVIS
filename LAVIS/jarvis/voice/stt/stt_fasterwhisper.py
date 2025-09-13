# stt_fasterwhisper_streaming_humanlike.py
import numpy as np
import collections
from faster_whisper import WhisperModel
from .stt_base import STTBase
import time

class FasterWhisperSTT(STTBase):
    def __init__(self, model_name: str = "small", sample_rate: int = 16000,
                 device: str = "cpu", compute_type: str = "int8"):
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self.sample_rate = sample_rate

        # Rolling buffer for last 10s
        self.audio_buffer = collections.deque(maxlen=sample_rate * 10)

        # For partial streaming
        self._unprocessed_buffer = collections.deque()
        self.min_buffer_secs = 0.3  # process at least 300ms
        self.max_buffer_secs = 5.0  # force transcription if waiting too long
        self.overlap_secs = 0.1     # 100ms overlap between partials
        self.last_transcribe_time = time.time()

        self._last_text = ""
        self._last_partial = ""
        self._last_category = "freeform"

    # --- STTBase methods ---
    def accept_waveform(self, audio_data: bytes) -> bool:
        pcm16 = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        self.audio_buffer.extend(pcm16.tolist())
        self._unprocessed_buffer.extend(pcm16.tolist())

        now = time.time()
        buffer_len_secs = len(self.audio_buffer) / self.sample_rate
        return buffer_len_secs >= self.min_buffer_secs or (now - self.last_transcribe_time) > self.max_buffer_secs

    def get_partial(self) -> str:
        """Process only unprocessed audio with overlap for smooth real-time streaming."""
        if not self._unprocessed_buffer:
            return self._last_partial or self._last_text

        buffer_len_secs = len(self._unprocessed_buffer) / self.sample_rate
        if buffer_len_secs < self.min_buffer_secs:
            # Too short, wait for more audio
            return self._last_partial or self._last_text

        # Convert unprocessed audio to numpy
        samples = np.array(self._unprocessed_buffer, dtype=np.float32)
        segments, _ = self.model.transcribe(samples, language="en")
        partial_text = " ".join([s.text for s in segments]).strip().lower()

        # Update last partial only if text changed
        if partial_text and partial_text != self._last_partial:
            self._last_partial = partial_text

        # Keep last overlap for next partial to prevent word cutting
        overlap_samples = int(self.overlap_secs * self.sample_rate)
        tail = list(self._unprocessed_buffer)[-overlap_samples:] if len(self._unprocessed_buffer) > overlap_samples else list(self._unprocessed_buffer)
        self._unprocessed_buffer = collections.deque(tail)

        return self._last_partial

    def get_result(self):
        """Finalize transcription and classify."""
        if not self.audio_buffer:
            return "", "freeform"

        samples = np.array(self.audio_buffer, dtype=np.float32)
        self.audio_buffer.clear()
        self._unprocessed_buffer.clear()
        self.last_transcribe_time = time.time()

        segments, _ = self.model.transcribe(samples, language="en")
        text = " ".join([s.text for s in segments]).strip().lower()

        self._last_text = text
        self._last_partial = text
        self._last_category = self._classify(text)
        return text, self._last_category

    def reset(self):
        self.audio_buffer.clear()
        self._unprocessed_buffer.clear()
        self._last_text = ""
        self._last_partial = ""
        self._last_category = "freeform"
        self.last_transcribe_time = time.time()

    # --- Internal classification ---
    def _classify(self, text: str) -> str:
        if not text:
            return "freeform"
        if text in ("stop", "cancel", "abort"):
            return "stop"
        return "command" if len(text.split()) <= 3 else "freeform"
