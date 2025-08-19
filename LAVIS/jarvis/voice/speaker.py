# ✅ speaker.py — Humanized playback + multi-voice support (v4)
# - Adds multiple voice profiles (Edge TTS + pyttsx3) with runtime switching and per-call overrides
# - Keeps previous token-based double-play prevention and humanized cadence
# - Public API:
#     set_voice_profile(name)           -> set default voice profile
#     list_voice_profiles()             -> list available profiles
#     speak(text, voice=None)           -> speak using optional per-call voice override
#     human_speak(answer, voice=None)   -> human filler + final reply with optional voice

import asyncio
import threading
import re
import time
import random
import traceback
import io
import queue
from typing import List, Tuple, Optional, Dict

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

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

ALLOW_BARGE_IN = True
# put near the top of speaker.py (with other globals)
_resume_lock = threading.Lock()
def _trace_resume_caller(tag: str):
    try:
        frm = inspect.stack()[2]
        caller = f"{frm.filename}:{frm.lineno}"
    except Exception:
        caller = "unknown"
    append_hud_console(f"[TTS-TRACE] {tag} called by {caller} @ {int(time.time()*1000)}")
# === Voice profile system ===
# A voice profile contains the Edge TTS voice name and an optional pyttsx3 voice index + rate
VOICE_PROFILES: Dict[str, Dict] = {
    "aria_female": {
        "edge": "en-US-AriaNeural",
        "pyttsx3_index": 1,
        "rate": 190,
        "volume": 1.0
    },
    "guy_male": {
        "edge": "en-US-GuyNeural",
        "pyttsx3_index": 2,
        "rate": 185,
        "volume": 1.0
    },
    "neutral": {
        "edge": "en-US-JennyNeural",
        "pyttsx3_index": 0,
        "rate": 188,
        "volume": 1.0
    }
}
_current_voice_profile = "aria_female"

# Public helpers
def list_voice_profiles():
    return list(VOICE_PROFILES.keys())

def set_voice_profile(name: str) -> bool:
    global _current_voice_profile
    if name in VOICE_PROFILES:
        _current_voice_profile = name
        append_hud_console(f"🎤 Voice profile set to: {name}")
        return True
    append_hud_console(f"⚠️ Voice profile not found: {name}")
    return False

def get_current_voice_profile() -> Dict:
    return VOICE_PROFILES.get(_current_voice_profile, VOICE_PROFILES[list(VOICE_PROFILES.keys())[0]])

# --- internal helper to resolve a voice name for Edge and to configure pyttsx3 ---
def _resolve_edge_voice(profile_name: Optional[str]) -> str:
    if profile_name and profile_name in VOICE_PROFILES:
        return VOICE_PROFILES[profile_name]["edge"]
    return VOICE_PROFILES.get(_current_voice_profile, VOICE_PROFILES["aria_female"])["edge"]

def _configure_pyttsx3_voice(engine: pyttsx3.Engine, profile_name: Optional[str]):
    try:
        profile = VOICE_PROFILES.get(profile_name or _current_voice_profile)
        if not profile:
            return
        voices = engine.getProperty('voices')
        idx = profile.get('pyttsx3_index')
        if isinstance(idx, int) and idx < len(voices):
            engine.setProperty('voice', voices[idx].id)
        if 'rate' in profile:
            engine.setProperty('rate', profile.get('rate', 190))
        if 'volume' in profile:
            engine.setProperty('volume', profile.get('volume', 1.0))
    except Exception as e:
        append_hud_console(f"[TTS] pyttsx3 voice config failed: {e}")

# ---- Existing playback/token safety & humanization variables -----------------------------------
VOICE_NAME = _resolve_edge_voice(None)
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

_offline_queue: "queue.Queue[Tuple[int, str]]" = queue.Queue()
_offline_thread: Optional[threading.Thread] = None
_engine_ready = threading.Event()

_resume_text: Optional[str] = None
_resume_word_index: int = 0
_current_words: List[str] = []
_sentence_spans: List[Tuple[str, int, int]] = []

_paused_for_barge_in = False
_playback_token = 0
_playback_lock = threading.Lock()

def _next_playback_token() -> int:
    global _playback_token
    with _playback_lock:
        _playback_token += 1
        return _playback_token

# --- pyttsx3 init (unchanged, but we configure voice per-play) ---
def _init_pyttsx3():
    global _engine
    if _engine is not None:
        return _engine
    try:
        engine = pyttsx3.init()
        try:
            if hasattr(engine, "_driver") and hasattr(engine._driver, "tts"):
                engine._driver.tts.ConnectEvent = lambda *a, **k: None
                engine._driver.tts._event_loop = None
        except Exception:
            pass
        _engine = engine
        return _engine
    except Exception as e:
        append_hud_console(f"[TTS] pyttsx3 init failed: {e}")
        _engine = None
        return None

# --- Offline worker: expects (token, phrase, profile_name) ---
def _offline_worker():
    global _engine
    eng = _init_pyttsx3()
    if eng is None:
        return
    _engine_ready.set()
    while True:
        try:
            item = _offline_queue.get()
            if item is None:
                break
            token, phrase, profile_name = item
            # if playback token changed, discard this queued phrase
            if token != _playback_token:
                continue
            if stop_speaking:
                continue
            tts_playback_ping()
            try:
                # configure voice before speaking
                _configure_pyttsx3_voice(eng, profile_name)
                eng.say(phrase + " ")
                eng.runAndWait()
            except Exception:
                traceback.print_exc()
        except Exception:
            traceback.print_exc()

def _ensure_offline_worker():
    global _offline_thread
    if _offline_thread is None or not _offline_thread.is_alive():
        _offline_thread = threading.Thread(target=_offline_worker, daemon=True)
        _offline_thread.start()
        _engine_ready.wait(timeout=3)

# --- rest of playback helpers (kept as before but accept an optional profile_name) ----------------

def _mark_speaking(active: bool):
    global speaking
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

# --- Stop / Pause / Resume (token-aware) --------------------------------------------------------
def stop_speech():
    global stop_speaking, _paused_for_barge_in, _playback_token
    _paused_for_barge_in = False
    stop_speaking = True
    # bump playback token to invalidate any queued offline phrases
    with _playback_lock:
        _playback_token += 1
    try:
        with _offline_queue.mutex:
            _offline_queue.queue.clear()
        eng = _init_pyttsx3()
        if eng is not None:
            eng.stop()
    except Exception as e:
        append_hud_console(f"[TTS] stop failed: {e}")
    _mark_speaking(False)
    try:
        if not ALLOW_BARGE_IN:
            resume_listening()
    except Exception:
        pass
    append_hud_console("⛔ Speech stopped")

def pause_speech():
    global stop_speaking, _paused_for_barge_in
    _paused_for_barge_in = True
    stop_speaking = True
    try:
        eng = _init_pyttsx3()
        if eng is not None:
            eng.stop()
    except Exception as e:
        append_hud_console(f"[TTS] pause failed: {e}")
    _mark_speaking(False)
    append_hud_console("⏸️ Speech paused (barge-in)")

def resume_if_ignored_interruption() -> bool:
    return _resume_word_if_any()

# --- Playback helpers that check token and accept a profile_name ---------------------------------

def _play_audio_segment(audio_segment: AudioSegment, token: int):
    if token != _playback_token:
        return
    sr = audio_segment.frame_rate
    ch = audio_segment.channels
    sw = audio_segment.sample_width
    raw = audio_segment.raw_data
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(sw), channels=ch, rate=sr, output=True)
    try:
        for i in range(0, len(raw), PY_AUDIO_CHUNK):
            if stop_speaking or token != _playback_token:
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

async def _edge_tts_fetch_audio(text: str, voice_name: str) -> AudioSegment:
    buf = io.BytesIO()
    communicate = edge_tts.Communicate(text, voice_name)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return AudioSegment.from_file(buf, format="mp3")

# adaptive chunk size
def _adaptive_chunk_size(words: List[str], index: int, default: int) -> int:
    w = words[index] if index < len(words) else ""
    if w.endswith(('.', '!', '?')):
        return max(3, default//2)
    if w.endswith(','):
        return max(4, default//2)
    if random.random() < 0.08:
        return max(3, default//2)
    return default

# Online play that checks token and adds short pauses, accepts profile_name
def _play_online_phrases(words: List[str], start_index: int = 0, chunk_size: int = ONLINE_CHUNK_WORDS, token: int = 0, profile_name: Optional[str] = None) -> int:
    global stop_speaking
    i = start_index
    voice_name = _resolve_edge_voice(profile_name)
    while i < len(words):
        if stop_speaking or token != _playback_token:
            append_hud_console(f"⏸️ Interrupted at word {i}: {words[i] if i < len(words) else ''}")
            return i
        sentence_here = _find_sentence_for_index(i)
        if sentence_here:
            try:
                set_current_spoken_sentence(sentence_here)
            except Exception:
                pass
        adaptive = _adaptive_chunk_size(words, i, chunk_size)
        phrase = " ".join(words[i:i+adaptive])
        try:
            audio = asyncio.run(_edge_tts_fetch_audio(phrase, voice_name))
            _play_audio_segment(audio, token)
            if token == _playback_token and not stop_speaking:
                time.sleep(random.uniform(0.05, 0.18))
                if phrase.rstrip().endswith(('.', '!', '?')):
                    time.sleep(random.uniform(0.12, 0.28))
        except Exception:
            traceback.print_exc()
            return i
        i += adaptive
    return len(words)

def _speak_online_word_aware(text: str, token: int, profile_name: Optional[str] = None) -> bool:
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _current_words if _current_words else _split_into_words(text)
    played_to = _play_online_phrases(words, _resume_word_index, chunk_size=ONLINE_CHUNK_WORDS, token=token, profile_name=profile_name)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

# Offline: queue (token, phrase, profile_name)
def _play_offline_phrases(words: List[str], start_index: int = 0, phrase_size: int = OFFLINE_PHRASE_WORDS, token: int = 0, profile_name: Optional[str] = None) -> int:
    global stop_speaking
    _ensure_offline_worker()
    i = start_index
    while i < len(words):
        if stop_speaking or token != _playback_token:
            return i
        sentence_here = _find_sentence_for_index(i)
        if sentence_here:
            try:
                set_current_spoken_sentence(sentence_here)
            except Exception:
                pass
        size = _adaptive_chunk_size(words, i, phrase_size)
        phrase = " ".join(words[i:i+size])
        _offline_queue.put((token, phrase, profile_name))
        time.sleep(random.uniform(0.02, 0.06))
        i += size
    return len(words)

def _speak_offline_word_aware(text: str, token: int, profile_name: Optional[str] = None) -> bool:
    global _resume_text, _resume_word_index
    _resume_text = text
    words = _current_words if _current_words else _split_into_words(text)
    played_to = _play_offline_phrases(words, _resume_word_index, phrase_size=OFFLINE_PHRASE_WORDS, token=token, profile_name=profile_name)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    return False

# Resume will clear paused state and attempt to play using current token and profile
def _resume_word_if_any() -> bool:
    """
    Resume saved TTS from last saved index, but avoid duplicate/responsive concurrent resumes.
    Returns True if resumed/completed, False otherwise.

    This implementation acquires a non-blocking lock so only one resume can run at once.
    It also checks `_paused_for_barge_in` and `speaking` to avoid duplicate or spurious resumes.
    """
    global stop_speaking, _paused_for_barge_in

    # quick pre-checks
    if not _resume_text:
        append_hud_console("▶️ Resume requested but no resume text available.")
        return False

    # Trace who asked to resume (useful when debugging duplicate triggers)
    _trace_resume_caller("resume_request")

    # try to acquire the resume lock without blocking (if already running, skip)
    if not _resume_lock.acquire(blocking=False):
        append_hud_console("▶️ Resume already in progress — skipping duplicate resume call.")
        return False

    try:
        # If already speaking, skip (this is defensive; speaking should be False when resuming)
        if speaking:
            append_hud_console("▶️ Resume requested but speaking already True — skipping.")
            return False

        # Require that we were paused for barge-in; otherwise it's likely a duplicate/spurious resume
        if not _paused_for_barge_in:
            append_hud_console("▶️ Resume requested but not in paused-for-barge-in state — skipping.")
            return False

        # mark paused/resume state BEFORE starting playback to prevent races
        _paused_for_barge_in = False
        stop_speaking = False
        _mark_speaking(True)   # set speaking True immediately to prevent other resumes
        append_hud_console("▶️ Resuming previous speech from last saved index...")

        token = _playback_token
        stored_profile = _current_voice_profile

        try:
            if is_connected():
                result = _speak_online_word_aware(_resume_text, token, profile_name=stored_profile)
            else:
                result = _speak_offline_word_aware(_resume_text, token, profile_name=stored_profile)

            # If we completed immediately, clear speaking flag; otherwise the playback flow will clear it.
            if result:
                _mark_speaking(False)
                append_hud_console("▶️ Resume completed (finished immediately).")
                return True

            append_hud_console("▶️ Resume started (playing).")
            return result

        except Exception as e:
            append_hud_console(f"[Resume Error] {e}")
            _mark_speaking(False)
            return False

    finally:
        # keep lock held while playback is active; release only when resume function returns.
        # Note: because the playback functions are synchronous here, the finally will run after playback ends.
        try:
            if _resume_lock.locked():
                _resume_lock.release()
        except Exception:
            pass

# Prepare resume maps
def _prepare_resume_maps(text: str):
    global _current_words, _sentence_spans, _resume_text
    _resume_text = text
    _current_words = _split_into_words(text)
    _sentence_spans = _build_sentence_spans(text, _current_words)

# --- Main speak / human_speak entrypoints now accept a voice override --------------------------------
def speak(text: str, voice: Optional[str] = None):
    global stop_speaking, _tts_thread, _resume_word_index, _playback_token
    if not text or not text.strip():
        return
    with _session_lock:
        token = _next_playback_token()
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

        _mark_speaking(True)
        set_last_spoken_text(text)

        try:
            if not ALLOW_BARGE_IN:
                pause_listening()
        except Exception:
            pass

        def run_tts(my_token=token, profile_name=voice or _current_voice_profile):
            try:
                if is_connected():
                    append_hud_console(f"🗣️ (online) {text}")
                    _speak_online_word_aware(text, my_token, profile_name=profile_name)
                else:
                    append_hud_console(f"🗣️ (offline) {text}")
                    _speak_offline_word_aware(text, my_token, profile_name=profile_name)
            finally:
                _mark_speaking(False)
                try:
                    if not ALLOW_BARGE_IN:
                        resume_listening()
                except Exception:
                    pass

        _tts_thread = threading.Thread(target=run_tts, daemon=True)
        _tts_thread.start()

# Human-sounding filler + reply with optional voice
def human_speak(answer: str, voice: Optional[str] = None):
    filler = random.choice([
        "Hmm...",
        "Got it...",
        "Let me think...",
        "One second...",
        "Alright...",
    ])
    def run_human(my_voice=voice):
        global stop_speaking
        try:
            stop_speaking = False
            speak(filler, voice=my_voice)
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
            time.sleep(random.uniform(0.06, 0.18))
            speak(final, voice=my_voice)
        except Exception:
            traceback.print_exc()
    threading.Thread(target=run_human, daemon=True).start()
