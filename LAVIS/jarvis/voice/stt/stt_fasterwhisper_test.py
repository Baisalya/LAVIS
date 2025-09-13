# live_stt.py
import threading
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

class LiveSTT:
    def __init__(self, model_name="small", sample_rate=16000, chunk_size=2048, device="cpu", compute_type="int8", update_interval=0.5):
        """
        model_name: 'tiny', 'base', 'small', 'medium', 'large'
        sample_rate: microphone sample rate
        chunk_size: samples per audio callback
        device: 'cpu' or 'cuda'
        compute_type: int8/float16/float32
        update_interval: seconds between transcription updates
        """
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.update_interval = update_interval

        self.audio_buffer = []
        self.lock = threading.Lock()
        self.last_text = ""

        self.running = False
        self.thread = None

    # --- Audio input ---
    def accept_waveform(self, audio_data: np.ndarray):
        with self.lock:
            self.audio_buffer.extend(audio_data.tolist())

    # --- Partial transcription ---
    def get_partial_result(self):
        with self.lock:
            if not self.audio_buffer:
                return ""
            samples = np.array(self.audio_buffer, dtype=np.float32)

        segments_gen, _ = self.model.transcribe(samples, language="en")
        last_text = ""
        for segment in segments_gen:
            last_text = segment.text.strip().lower()
        return last_text

    # --- Transcription thread ---
    def _transcribe_loop(self):
        while self.running:
            text = self.get_partial_result()
            if text and text != self.last_text:
                print("\rLive:", text, end="", flush=True)
                self.last_text = text
            time.sleep(self.update_interval)

    # --- Start live STT ---
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self.thread.start()

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(status)
            audio_data = indata[:, 0].astype(np.float32) / 32768.0
            self.accept_waveform(audio_data)

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16',
                                blocksize=self.chunk_size, callback=audio_callback):
                print("Start speaking... Press Ctrl+C to stop.")
                while self.running:
                    sd.sleep(1000)
        except KeyboardInterrupt:
            self.stop()

    # --- Stop live STT ---
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print("\nStopped.")

# ----------------- Example usage -----------------
if __name__ == "__main__":
    stt = LiveSTT(model_name="small", chunk_size=2048, update_interval=0.5)
    stt.start()
