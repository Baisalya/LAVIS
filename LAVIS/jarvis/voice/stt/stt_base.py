# stt_base.py
from abc import ABC, abstractmethod
from typing import Tuple


class STTBase(ABC):
    """Abstract base class for Speech-to-Text engines."""

    @abstractmethod
    def accept_waveform(self, audio_data: bytes) -> bool:
        """
        Feed audio frame into the recognizer.
        Returns True if a full utterance is ready to fetch with get_result().
        """
        pass

    @abstractmethod
    def get_result(self) -> Tuple[str, str]:
        """
        Return a tuple (text, category) after a full utterance is recognized.

        text:      Final recognized transcription.
        category:  Suggested category (e.g. "command", "freeform", "stop", "noise").
        """
        pass

    @abstractmethod
    def get_partial(self) -> str:
        """
        Return the current partial transcription (if available).
        This is mainly for live feedback to the user.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        Reset the recognizer state (e.g. after silence timeout).
        """
        pass
