# tts_engines.py
import threading
import pyttsx3
import edge_tts
import asyncio
import io
from pydub import AudioSegment
import pyaudio
import time

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

            # If stop requested before we finished streaming, bail out.
            if self._stop_event.is_set():
                return

            # Play buffer (mp3) using pydub + pyaudio but write raw in chunks
            if buf.getbuffer().nbytes == 0:
                return

            buf.seek(0)
            audio = AudioSegment.from_file(buf, format="mp3")

            # prepare pyaudio stream
            p = pyaudio.PyAudio()
            format_ = p.get_format_from_width(audio.sample_width)
            channels = audio.channels
            rate = audio.frame_rate

            stream = None
            try:
                stream = p.open(format=format_, channels=channels, rate=rate, output=True)
                raw = audio.raw_data
                chunk_size = 2048
                pos = 0
                while pos < len(raw):
                    if self._stop_event.is_set():
                        break
                    end = min(len(raw), pos + chunk_size)
                    # write chunk
                    stream.write(raw[pos:end])
                    pos = end
                    # tiny sleep to allow other threads to run and for ping logic
                    time.sleep(0.001)
            finally:
                try:
                    if stream is not None:
                        stream.stop_stream()
                        stream.close()
                except Exception:
                    pass
                try:
                    p.terminate()
                except Exception:
                    pass

        except Exception as e:
            # Keep printing to console/HUD to help debugging
            print(f"[HUD CONSOLE] ❌ EdgeTTS error: {e}")
        finally:
            self._speaking.clear()
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
        try:
            self.engine = pyttsx3.init()
        except Exception as e:
            print(f"[HUD CONSOLE] ❌ pyttsx3 init failed: {e}")
            self.engine = None
        self._speaking = threading.Event()
        self._stop_event = threading.Event()
        self.voice = voice
        self.rate = rate
        if self.engine and voice:
            try:
                self.engine.setProperty("voice", voice)
            except Exception:
                pass
        if self.engine:
            try:
                self.engine.setProperty("rate", rate)
            except Exception:
                pass

    def speak(self, text, on_word=None, on_sentence=None):
        if self.engine is None:
            return

        def _run():
            try:
                self._stop_event.clear()
                self._speaking.set()
                # Note: pyttsx3 supports events but callbacks are platform/driver-dependent.
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print(f"[HUD CONSOLE] ❌ pyttsx3 error: {e}")
            finally:
                self._speaking.clear()
                self._stop_event.clear()

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def stop(self):
        try:
            self._stop_event.set()
            if self.engine:
                self.engine.stop()
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
        if self.engine and voice:
            try:
                self.engine.setProperty("voice", voice)
            except Exception:
                pass

    def set_rate(self, rate):
        self.rate = rate
        if self.engine:
            try:
                self.engine.setProperty("rate", rate)
            except Exception:
                pass
