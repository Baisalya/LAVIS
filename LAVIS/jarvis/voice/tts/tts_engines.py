# tts_engines.py
import threading
import pyttsx3
import edge_tts
import asyncio
import io
from pydub import AudioSegment
import pyaudio
import time
import queue
import logging

# Silence comtypes verbose debug logs
logging.getLogger('comtypes').setLevel(logging.WARNING)
logging.getLogger('comtypes.client').setLevel(logging.WARNING)

# -------------------------
# Base Interface
# -------------------------
class BaseTTS:
    def speak(self, text, on_word=None, on_sentence=None):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def is_speaking(self):
        raise NotImplementedError

    def set_voice(self, voice):
        """Optional: set voice before next speak"""
        raise NotImplementedError

    def set_rate(self, rate):
        raise NotImplementedError


# -------------------------
# EdgeTTS (online, async) - play buffered audio but allow mid-play stop
# -------------------------
class EdgeTTS(BaseTTS):
    def __init__(self, voice="en-US-AriaNeural", rate="+0%", volume="+0%"):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self._speaking = threading.Event()
        self._stop_event = threading.Event()
        self._loop = asyncio.new_event_loop()
        # run loop on a dedicated thread
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _async_speak(self, text, on_word, on_sentence):
        """
        Collect mp3 audio from edge_tts stream, fire word/sentence callbacks,
        then play the collected mp3 via pyaudio in chunked writes so stop() can interrupt.
        """
        try:
            self._stop_event.clear()
            self._speaking.set()
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, volume=self.volume)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                # allow cooperative cancellation while streaming
                if self._stop_event.is_set():
                    # stop early
                    break
                if chunk.get("type") == "audio":
                    buf.write(chunk.get("data", b""))
                elif chunk.get("type") == "word_boundary" and on_word:
                    try:
                        on_word(chunk)
                    except Exception:
                        pass
                elif chunk.get("type") == "sentence_boundary" and on_sentence:
                    try:
                        on_sentence(chunk)
                    except Exception:
                        pass

            if self._stop_event.is_set() or buf.getbuffer().nbytes == 0:
                self._speaking.clear()
                return

            buf.seek(0)
            
            # Run the blocking PyAudio playback in a separate thread
            # to avoid blocking the asyncio event loop!
            def _play_audio():
                stream = None
                p = None
                try:
                    audio = AudioSegment.from_file(buf, format="mp3")
                    p = pyaudio.PyAudio()
                    format_ = p.get_format_from_width(audio.sample_width)
                    channels = audio.channels
                    rate = audio.frame_rate

                    stream = p.open(format=format_, channels=channels, rate=rate, output=True)
                    raw = audio.raw_data
                    chunk_size = 2048
                    pos = 0
                    while pos < len(raw):
                        if self._stop_event.is_set():
                            break
                        end = min(len(raw), pos + chunk_size)
                        stream.write(raw[pos:end])
                        pos = end
                        time.sleep(0.001)
                except FileNotFoundError as e:
                    print(f"[HUD CONSOLE] ❌ EdgeTTS Audio Error (ffmpeg missing?): {e}\nTry installing ffmpeg and adding it to PATH.")
                except Exception as e:
                    print(f"[HUD CONSOLE] ❌ EdgeTTS Playback Error: {e}")
                finally:
                    try:
                        if stream is not None:
                            stream.stop_stream()
                            stream.close()
                    except Exception:
                        pass
                    try:
                        if p is not None:
                            p.terminate()
                    except Exception:
                        pass
                    self._speaking.clear()

            threading.Thread(target=_play_audio, daemon=True).start()

        except Exception as e:
            # Keep printing to console/HUD to help debugging
            print(f"[HUD CONSOLE] ❌ EdgeTTS error: {e}")
            self._speaking.clear()
        finally:
            self._stop_event.clear()

    def speak(self, text, on_word=None, on_sentence=None):
        # schedule coroutine on loop, returns immediately
        if not text or not text.strip():
            return
        # make sure any previous stop flag is cleared
        self._stop_event.clear()
        asyncio.run_coroutine_threadsafe(self._async_speak(text, on_word, on_sentence), self._loop)

    def stop(self):
        # cooperative stop: signal event and also clear speaking flag
        try:
            self._stop_event.set()
        except Exception:
            pass
        try:
            self._speaking.clear()
        except Exception:
            pass

    def is_speaking(self):
        return self._speaking.is_set()

    def set_voice(self, voice):
        self.voice = voice

    def set_rate(self, rate):
        self.rate = rate


# -------------------------
# Pyttsx3 (offline)
# -------------------------
class Pyttsx3TTS(BaseTTS):
    def __init__(self, voice=None, rate=180):
        self.voice = voice
        self.rate = rate
        self._speaking = threading.Event()
        self._stop_event = threading.Event()
        self.engine = None
        
        self._queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._worker_thread.start()

    def _tts_worker(self):
        # Initialize COM for this thread specifically (crucial on Windows)
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
            
        try:
            self.engine = pyttsx3.init()
            if self.voice:
                self.engine.setProperty("voice", self.voice)
            self.engine.setProperty("rate", self.rate)
        except Exception as e:
            print(f"[HUD CONSOLE] ❌ pyttsx3 init failed: {e}")
            self.engine = None

        while True:
            text = self._queue.get()
            if text is None:
                break
                
            self._stop_event.clear()
            self._speaking.set()
            
            if self.engine:
                try:
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e:
                    print(f"[HUD CONSOLE] ❌ pyttsx3 error: {e}")
                    
            self._speaking.clear()
            self._queue.task_done()

    def speak(self, text, on_word=None, on_sentence=None):
        if not text or not text.strip():
            return
        self._queue.put(text)

    def stop(self):
        try:
            self._stop_event.set()
            if hasattr(self, 'engine') and self.engine:
                self.engine.stop()
        except Exception:
            pass
        try:
            with self._queue.mutex:
                self._queue.queue.clear()
            self._speaking.clear()
        except Exception:
            pass

    def is_speaking(self):
        return self._speaking.is_set()

    def set_voice(self, voice):
        self.voice = voice
        if hasattr(self, 'engine') and self.engine:
            try:
                self.engine.setProperty("voice", voice)
            except Exception:
                pass

    def set_rate(self, rate):
        self.rate = rate
        if hasattr(self, 'engine') and self.engine:
            try:
                self.engine.setProperty("rate", rate)
            except Exception:
                pass
