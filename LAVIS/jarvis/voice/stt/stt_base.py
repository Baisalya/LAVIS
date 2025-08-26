# stt_base.py
from abc import ABC, abstractmethod

class STTBase(ABC):
    """Abstract base class for Speech-to-Text engines."""

    @abstractmethod
    def accept_waveform(self, audio_data: bytes) -> bool:
        """Feed audio frame. Returns True if a full utterance was recognized."""
        pass

    @abstractmethod
    def get_result(self) -> str:
        """Return final recognized text after AcceptWaveform = True."""
        pass

    @abstractmethod
    def get_partial(self) -> str:
        """Return current partial transcription (if available)."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset recognizer state (for silence resets)."""
        pass
