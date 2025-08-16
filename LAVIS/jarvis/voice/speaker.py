# ✅ speaker.py — Hybrid Edge TTS (online) + pyttsx3 (offline)
# Word-aware barge-in + smart resume + echo-mitigation pings + no-overlap guard
import asyncio
import threading
import re
import time
import random
import traceback
import io
import edge_tts
import pyttsx3
from pydub import AudioSegment
import pyaudio

from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.voice.recognizer import set_last_spoken_text, resume_listening
# Optional ping the recognizer so it can mask mic frames while we're outputting audio
try:
    from LAVIS.jarvis.voice.recognizer import tts_playback_ping  # new helper we'll add in recognizer.py
except Exception:
    def tts_playback_ping():
        pass

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

voice_name = "en-US-AriaNeural"
engine = pyttsx3.init()
engine.setProperty('rate', 190)  # a touch faster to reduce perceived latency
engine.setProperty('volume', 1.0)
try:
    voices = engine.getProperty('voices')
    if len(voices) > 1:
        engine.setProperty('voice', voices[1].id)
except Exception as e:
    print(f"[TTS] Voice setup error: {e}")

# ===== Runtime state =====
stop_speaking = False
speaking = False
_session_lock = threading.RLock()
_tts_thread: threading.Thread | None = None

# Resume state (word index works for both online/offline paths)
_resume_text: str | None = None
_resume_word_index: int = 0
_current_words: list[str] = []

# ===== Internals =====

def _mark_speaking(active: bool):
    global speaking
    speaking = active

def _reset_resume_buffers():
    global _resume_text, _resume_word_index, _current_words
    _resume_text = None
    _resume_word_index = 0
    _current_words = []

def _split_into_words(text: str):
    return re.findall(r"\S+", text)

# ===== External controls =====

def stop_speech():
    """Hard stop for barge-in; cancels playback and resumes listening immediately."""
    global stop_speaking
    stop_speaking = True
    try:
        engine.stop()
    except Exception:
        pass
    append_hud_console("⛔ Speech stopped")
    _mark_speaking(False)
    # 🔓 Always resume mic on stop
    try:
        from LAVIS.jarvis.voice import recognizer
        recognizer.resume_listening()
    except Exception:
        pass
def clear_resume():
    _reset_resume_buffers()

# ===== OFFLINE (pyttsx3, phrase-sized for speed) =====

def _play_offline_phrases(words: list[str], start_index: int = 0, phrase_size: int = 5) -> int:
    """Speak with pyttsx3 in short phrases for better prosody/speed. Returns index of next word to speak."""
    global stop_speaking
    i = start_index
    while i < len(words):
        if stop_speaking:
            append_hud_console(f"⏸️ Interrupted at word {i}: {words[i]}")
            return i
        phrase = " ".join(words[i:i+phrase_size])
        try:
            tts_playback_ping()  # hint to recognizer that TTS output is happening now
            engine.say(phrase + " ")
            engine.runAndWait()
        except Exception:
            traceback.print_exc()
            return i
        i += phrase_size
    return len(words)

def _speak_offline_word_aware(text: str) -> bool:
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _split_into_words(text)
    played_to = _play_offline_phrases(words, _resume_word_index, phrase_size=5)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

# ===== ONLINE (Edge TTS, chunked phrases) =====

def _play_online_phrases(words: list[str], start_index: int = 0, chunk_size: int = 12) -> int:
    """Fetch Edge TTS audio for small phrases and play; returns next word index."""
    global stop_speaking
    i = start_index
    while i < len(words):
        if stop_speaking:
            append_hud_console(f"⏸️ Interrupted at word {i}: {words[i]}")
            return i
        phrase = " ".join(words[i:i+chunk_size])
        try:
            audio = asyncio.run(_edge_tts_fetch_audio(phrase))
            _play_audio_segment(audio)
        except Exception:
            traceback.print_exc()
            return i
        i += chunk_size
    return len(words)

async def _edge_tts_fetch_audio(text: str) -> AudioSegment:
    buf = io.BytesIO()
    communicate = edge_tts.Communicate(text, voice_name)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return AudioSegment.from_file(buf, format="mp3")

def _play_audio_segment(audio_segment: AudioSegment):
    sr = audio_segment.frame_rate
    ch = audio_segment.channels
    sw = audio_segment.sample_width
    raw = audio_segment.raw_data
    chunk = 2048
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(sw), channels=ch, rate=sr, output=True)
    try:
        for i in range(0, len(raw), chunk):
            if stop_speaking:
                break
            # Ping recognizer just before pushing audio to speakers to improve echo masking
            tts_playback_ping()
            stream.write(raw[i:i+chunk])
    finally:
        try:
            stream.stop_stream(); stream.close()
        except Exception:
            pass
        p.terminate()

def _speak_online_word_aware(text: str) -> bool:
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _split_into_words(text)
    played_to = _play_online_phrases(words, _resume_word_index, chunk_size=12)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

# ===== Resume =====

def _resume_word_if_any() -> bool:
    if not _resume_text:
        return False
    if is_connected():
        return _speak_online_word_aware(_resume_text)
    else:
        return _speak_offline_word_aware(_resume_text)

# ===== Public API =====

def speak(text: str):
    """Main TTS entry — cancels any previous TTS thread to prevent overlap."""
    global stop_speaking, _tts_thread
    with _session_lock:
        # Cancel ongoing speech
        if _tts_thread and _tts_thread.is_alive():
            stop_speech()
            _tts_thread.join(timeout=0.2)

        stop_speaking = False
        _mark_speaking(True)
        set_last_spoken_text(text)

        # 🔒 Pause recognizer while speaking
        try:
            from LAVIS.jarvis.voice import recognizer
            recognizer.pause_listening()
        except Exception:
            pass

        def run_tts():
            try:
                if is_connected():
                    append_hud_console(f"🗣️ (online) {text}")
                    _speak_online_word_aware(text)
                else:
                    append_hud_console(f"🗣️ (offline) {text}")
                    _speak_offline_word_aware(text)
            finally:
                _mark_speaking(False)
                # 🔓 Resume recognizer after speaking ends
                try:
                    from LAVIS.jarvis.voice import recognizer
                    recognizer.resume_listening()
                except Exception:
                    pass

        _tts_thread = threading.Thread(target=run_tts, daemon=True)
        _tts_thread.start()
def resume_if_ignored_interruption() -> bool:
    return _resume_word_if_any()


def human_speak(answer: str):
    """Speak a short filler, then the final answer without overlap/double-voice."""
    filler = random.choice([
        "Got it...",
        "Let me respond...",
        "One second...",
        "Alright...",
        "Okay, here's what I found...",
    ])

    def run_human():
        global stop_speaking
        try:
            # Filler
            stop_speaking = False
            speak(filler)
            # Wait for filler to finish (or timeout) before starting final
            t0 = time.time()
            while speaking and time.time() - t0 < 5.0:
                time.sleep(0.05)
            # Ensure no overlap
            stop_speaking = True
            try:
                engine.stop()
            except Exception:
                pass
            time.sleep(0.02)
            stop_speaking = False
            final = answer.strip() if answer else "Sorry, I don't have anything useful."
            speak(final)
        except Exception:
            traceback.print_exc()

    threading.Thread(target=run_human, daemon=True).start()
