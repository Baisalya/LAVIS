# aec.py
import numpy as np
import speexdsp

class AEC:
    def __init__(self, sample_rate=16000, frame_size=160, filter_length=1600):
        """
        Acoustic Echo Canceller using SpeexDSP
        - sample_rate: audio rate (16000 recommended for STT)
        - frame_size: number of samples per frame (160 = 10ms at 16kHz)
        - filter_length: how long the echo tail can be (in samples)
        """
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.aec = speexdsp.EchoCanceller(frame_size, filter_length, sample_rate)

    def process(self, mic_bytes: bytes, spk_bytes: bytes) -> bytes:
        """
        mic_bytes: raw PCM16 audio from microphone
        spk_bytes: raw PCM16 audio sent to speaker (TTS output)
        returns: PCM16 audio with echo removed
        """
        # Convert bytes → numpy int16
        mic_frame = np.frombuffer(mic_bytes, dtype=np.int16)
        spk_frame = np.frombuffer(spk_bytes, dtype=np.int16)

        # Process echo cancellation
        clean_frame = self.aec.process(mic_frame, spk_frame)

        # Return back as bytes
        return clean_frame.astype(np.int16).tobytes()
