# vad.py
import torch
import numpy as np
from silero_vad import VADIterator

class VadSilero:
    def __init__(self, sample_rate=16000):
        # Load silero model once
        self.sample_rate = sample_rate
        self.model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        (_, _, _, VADIterator, _) = utils
        self.vad_iterator = VADIterator(self.model)

    def is_speech(self, audio_bytes: bytes) -> bool:
        """
        Check if the audio frame contains speech.
        audio_bytes: raw PCM16 audio frame
        Returns True if speech, False if silence/noise
        """
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(samples)
        speech_dict = self.vad_iterator(tensor, sample_rate=self.sample_rate)
        return speech_dict is not None
