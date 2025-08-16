# ✅ speaker.py — Hybrid Edge TTS (online) + pyttsx3 (offline) with word-aware barge-in + smart resume
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

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

voice_name = "en-US-AriaNeural"
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)
try:
    voices = engine.getProperty('voices')
    if len(voices) > 1:
        engine.setProperty('voice', voices[1].id)
except Exception as e:
    print(f"[TTS] Voice setup error: {e}")

stop_speaking = False
speaking = False
_session_lock = threading.RLock()
_resume_text = None
_resume_word_index = 0
_current_words = []

_engine_event_supported = True

def _mark_speaking(active):
    global speaking
    speaking = active

def _reset_resume_buffers():
    global _resume_text, _resume_word_index, _current_words
    _resume_text = None
    _resume_word_index = 0
    _current_words = []

def _split_into_words(text):
    return re.findall(r"\S+", text)

def stop_speech():
    global stop_speaking
    stop_speaking = True
    try:
        engine.stop()
    except Exception as e:
        print("⚠️ engine.stop() failed:", e)
    append_hud_console("⛔ Speech stopped")
    _mark_speaking(False)

def clear_resume():
    _reset_resume_buffers()

# ===== OFFLINE (pyttsx3) =====

def _play_words_offline(words, start_index=0):
    global stop_speaking
    for i in range(start_index, len(words)):
        if stop_speaking:
            append_hud_console(f"⏸️ Interrupted at word {i}: {words[i]}")
            return i
        try:
            engine.say(words[i] + " ")
            engine.runAndWait()
        except Exception:
            traceback.print_exc()
            return i
    return len(words)

def _speak_offline_word_aware(text):
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _split_into_words(text)
    played_to = _play_words_offline(words, _resume_word_index)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

# ===== ONLINE (Edge TTS) =====

def _play_words_online(words, start_index=0):
    global stop_speaking
    chunk_size = 6
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

async def _edge_tts_fetch_audio(text):
    buf = io.BytesIO()
    communicate = edge_tts.Communicate(text, voice_name)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return AudioSegment.from_file(buf, format="mp3")

def _play_audio_segment(audio_segment):
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
            stream.write(raw[i:i+chunk])
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

def _speak_online_word_aware(text):
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _split_into_words(text)
    played_to = _play_words_online(words, _resume_word_index)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

# ===== Resume =====

def _resume_word_if_any():
    global _resume_text
    if not _resume_text:
        return False
    if is_connected():
        return _speak_online_word_aware(_resume_text)
    else:
        return _speak_offline_word_aware(_resume_text)

# ===== Public API =====

def speak(text):
    global stop_speaking
    with _session_lock:
        stop_speaking = False
        _mark_speaking(True)
        set_last_spoken_text(text)

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
                resume_listening()

        threading.Thread(target=run_tts, daemon=True).start()

def resume_if_ignored_interruption():
    return _resume_word_if_any()

def human_speak(answer):
    filler = random.choice(["Got it...", "Let me respond...", "One second...", "Alright...", "Okay, here's what I found..."])
    def run_human():
        global stop_speaking
        try:
            stop_speaking = False
            speak(filler)
            time.sleep(0.7)
            stop_speaking = False
            speak(answer.strip() if answer else "Sorry, I don't have anything useful.")
        except Exception:
            traceback.print_exc()
    threading.Thread(target=run_human, daemon=True).start()
