# ✅ speaker.py — Hybrid Edge TTS (online) + pyttsx3 (offline worker)
# Full-featured: word-aware barge-in, smart resume, sentence pings for echo suppression,
# echo-mitigation pings to recognizer, mic pause/resume shield, HUD logs, and no-overlap guard.

import asyncio
import threading
import re
import time
import random
import traceback
import io
import queue
from typing import List, Tuple, Optional

import edge_tts
import pyttsx3
from pydub import AudioSegment
import pyaudio

# ---- Integration points into the rest of the stack ---------------------------------------------
from LAVIS.jarvis.network import is_connected

try:
    from LAVIS.jarvis.voice.recognizer import (
        set_last_spoken_text,
        resume_listening,
        pause_listening,
        tts_playback_ping,
        set_current_spoken_sentence,
    )
except Exception:
    def set_last_spoken_text(_t): pass
    def resume_listening(): pass
    def pause_listening(): pass
    def tts_playback_ping(): pass
    def set_current_spoken_sentence(_t): pass
# Add near other constants at top of speaker.py
ALLOW_BARGE_IN = True  # when True, do NOT pause the recognizer during TTS; allow live barge-in

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

VOICE_NAME = "en-US-AriaNeural"
OFFLINE_RATE = 190
OFFLINE_VOLUME = 1.0
OFFLINE_VOICE_INDEX = 1
ONLINE_CHUNK_WORDS = 12
OFFLINE_PHRASE_WORDS = 5
PY_AUDIO_CHUNK = 2048
FILLER_MAX_WAIT = 5.0

_engine: Optional[pyttsx3.Engine] = None
stop_speaking = False
speaking = False
_tts_thread: Optional[threading.Thread] = None
_session_lock = threading.RLock()

# === Offline worker state ===
_offline_queue = queue.Queue()
_offline_thread: Optional[threading.Thread] = None
_engine_ready = threading.Event()

_resume_text: Optional[str] = None
_resume_word_index: int = 0
_current_words: List[str] = []
_sentence_spans: List[Tuple[str, int, int]] = []

def _init_pyttsx3():
    global _engine
    if _engine is not None:
        return _engine
    try:
        engine = pyttsx3.init()

        # 🔥 Disable SAPI event subscriptions to prevent COM crash
        try:
            if hasattr(engine, "_driver") and hasattr(engine._driver, "tts"):
                engine._driver.tts.ConnectEvent = lambda *a, **k: None
                engine._driver.tts._event_loop = None
        except Exception:
            pass  # ignore if driver structure changes

        # Basic settings
        engine.setProperty('rate', OFFLINE_RATE)
        engine.setProperty('volume', OFFLINE_VOLUME)

        # Voice selection
        try:
            voices = engine.getProperty('voices')
            if isinstance(voices, list) and len(voices) > OFFLINE_VOICE_INDEX:
                engine.setProperty('voice', voices[OFFLINE_VOICE_INDEX].id)
        except Exception as ve:
            append_hud_console(f"[TTS] Voice setup warning: {ve}")

        _engine = engine
        return _engine
    except Exception as e:
        append_hud_console(f"[TTS] pyttsx3 init failed: {e}")
        _engine = None
        return None

def _offline_worker():
    global _engine
    eng = _init_pyttsx3()
    if eng is None:
        return
    _engine_ready.set()
    while True:
        try:
            phrase = _offline_queue.get()
            if phrase is None:
                break
            if stop_speaking:
                continue
            tts_playback_ping()
            eng.say(phrase + " ")
            eng.runAndWait()
        except Exception:
            traceback.print_exc()

def _ensure_offline_worker():
    global _offline_thread
    if _offline_thread is None or not _offline_thread.is_alive():
        _offline_thread = threading.Thread(target=_offline_worker, daemon=True)
        _offline_thread.start()
        _engine_ready.wait(timeout=3)

def _mark_speaking(active: bool):
    global speaking
    # only print when state actually changes (avoids spam)
    if speaking != active:
        speaking = active
        print(f"[DEBUG] 🔊 Speaking = {speaking}")
    else:
        speaking = active

def _reset_resume_buffers():
    global _resume_text, _resume_word_index, _current_words, _sentence_spans
    _resume_text = None
    _resume_word_index = 0
    _current_words = []
    _sentence_spans = []

def clear_resume():
    _reset_resume_buffers()

def _split_into_words(text: str) -> List[str]:
    return re.findall(r"\S+", text or "")

_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

def _split_into_sentences(text: str) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    parts = _SENTENCE_RE.split(t)
    return [re.sub(r'\s+', ' ', p).strip() for p in parts if p.strip()]

def _build_sentence_spans(text: str, words: List[str]) -> List[Tuple[str, int, int]]:
    sentences = _split_into_sentences(text)
    spans: List[Tuple[str, int, int]] = []
    wi = 0
    for sent in sentences:
        sent_words = _split_into_words(sent)
        start = wi
        wi += len(sent_words)
        end = wi
        spans.append((sent, start, end))
    if wi < len(words):
        tail_text = " ".join(words[wi:])
        spans.append((tail_text, wi, len(words)))
    return spans

def _find_sentence_for_index(word_index: int) -> str:
    for sent, start, end in _sentence_spans:
        if start <= word_index < end:
            return sent
    return _sentence_spans[-1][0] if _sentence_spans else ""

def stop_speech():
    global stop_speaking
    stop_speaking = True
    try:
        with _offline_queue.mutex:
            _offline_queue.queue.clear()
        eng = _init_pyttsx3()
        if eng is not None:
            eng.stop()
    except Exception as e:
        append_hud_console(f"[TTS] stop failed: {e}")
    # ensure speaking flag cleared once we actually stop
    _mark_speaking(False)
    # only resume listening if we paused it earlier
    try:
        if not ALLOW_BARGE_IN:
            resume_listening()
    except Exception:
        pass
    append_hud_console("⛔ Speech stopped")

def resume_if_ignored_interruption() -> bool:
    return _resume_word_if_any()

def _play_audio_segment(audio_segment: AudioSegment):
    sr = audio_segment.frame_rate
    ch = audio_segment.channels
    sw = audio_segment.sample_width
    raw = audio_segment.raw_data
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(sw), channels=ch, rate=sr, output=True)
    try:
        for i in range(0, len(raw), PY_AUDIO_CHUNK):
            if stop_speaking:
                break
            tts_playback_ping()
            stream.write(raw[i:i+PY_AUDIO_CHUNK])
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        p.terminate()

async def _edge_tts_fetch_audio(text: str) -> AudioSegment:
    buf = io.BytesIO()
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return AudioSegment.from_file(buf, format="mp3")

def _play_online_phrases(words: List[str], start_index: int = 0, chunk_size: int = ONLINE_CHUNK_WORDS) -> int:
    global stop_speaking
    i = start_index
    while i < len(words):
        if stop_speaking:
            append_hud_console(f"⏸️ Interrupted at word {i}: {words[i] if i < len(words) else ''}")
            return i
        sentence_here = _find_sentence_for_index(i)
        if sentence_here:
            try:
                set_current_spoken_sentence(sentence_here)
            except Exception:
                pass
        phrase = " ".join(words[i:i+chunk_size])
        try:
            audio = asyncio.run(_edge_tts_fetch_audio(phrase))
            _play_audio_segment(audio)
        except Exception:
            traceback.print_exc()
            return i
        i += chunk_size
    return len(words)

def _speak_online_word_aware(text: str) -> bool:
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _current_words if _current_words else _split_into_words(text)
    played_to = _play_online_phrases(words, _resume_word_index, chunk_size=ONLINE_CHUNK_WORDS)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

def _play_offline_phrases(words: List[str], start_index: int = 0, phrase_size: int = OFFLINE_PHRASE_WORDS) -> int:
    global stop_speaking
    _ensure_offline_worker()
    i = start_index
    while i < len(words):
        if stop_speaking:
            return i
        sentence_here = _find_sentence_for_index(i)
        if sentence_here:
            try:
                set_current_spoken_sentence(sentence_here)
            except Exception:
                pass
        phrase = " ".join(words[i:i+phrase_size])
        _offline_queue.put(phrase)
        i += phrase_size
    return len(words)

def _speak_offline_word_aware(text: str) -> bool:
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _current_words if _current_words else _split_into_words(text)
    played_to = _play_offline_phrases(words, _resume_word_index, phrase_size=OFFLINE_PHRASE_WORDS)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

def _resume_word_if_any() -> bool:
    if not _resume_text:
        return False
    if is_connected():
        return _speak_online_word_aware(_resume_text)
    else:
        return _speak_offline_word_aware(_resume_text)

def _prepare_resume_maps(text: str):
    global _current_words, _sentence_spans, _resume_text
    _resume_text = text
    _current_words = _split_into_words(text)
    _sentence_spans = _build_sentence_spans(text, _current_words)

def speak(text: str):
    global stop_speaking, _tts_thread, _resume_word_index
    if not text or not text.strip():
        return
    with _session_lock:
        if _tts_thread and _tts_thread.is_alive():
            stop_speaking = True
            try:
                with _offline_queue.mutex:
                    _offline_queue.queue.clear()
                eng = _init_pyttsx3()
                if eng is not None:
                    eng.stop()
            except Exception:
                pass
            _tts_thread.join(timeout=0.25)
        stop_speaking = False
        _resume_word_index = 0
        _prepare_resume_maps(text)

        # mark speaking BEFORE starting audio playback
        _mark_speaking(True)
        set_last_spoken_text(text)

        # Only pause recognizer if caller explicitly disabled barge-in
        try:
            if not ALLOW_BARGE_IN:
                pause_listening()
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
                # mark speaking false once finished
                _mark_speaking(False)
                # Only resume recognizer if we paused it earlier
                try:
                    if not ALLOW_BARGE_IN:
                        resume_listening()
                except Exception:
                    pass

        _tts_thread = threading.Thread(target=run_tts, daemon=True)
        _tts_thread.start()

def human_speak(answer: str):
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
            stop_speaking = False
            speak(filler)
            t0 = time.time()
            while speaking and (time.time() - t0) < FILLER_MAX_WAIT:
                time.sleep(0.05)
            stop_speaking = True
            try:
                with _offline_queue.mutex:
                    _offline_queue.queue.clear()
                eng = _init_pyttsx3()
                if eng is not None:
                    eng.stop()
            except Exception:
                pass
            time.sleep(0.02)
            stop_speaking = False
            final = (answer or "").strip() or "Sorry, I don't have anything useful."
            speak(final)
        except Exception:
            traceback.print_exc()
    threading.Thread(target=run_human, daemon=True).start()