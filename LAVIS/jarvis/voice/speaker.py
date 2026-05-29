# ✅ speaker.py — Humanized playback + multi-voice support (v6 FINAL with smart resume fix)
# - Multiple voice profiles (Edge TTS + pyttsx3) with runtime switching and per-call overrides
# - Keeps previous token-based double-play prevention and humanized cadence
# - Fix: Resume now continues exactly from the last played word, prevents duplicate resumes.
# - Added: _trace_resume_caller, _last_played_word_index tracking, resume guards.
# - Public API:
#     set_voice_profile(name)           -> set default voice profile
#     list_voice_profiles()             -> list available profiles
#     speak(text, voice=None, emotion=None)
#     human_speak(answer, voice=None, emotion=None)

import asyncio
import threading
import re
import time
import random
import traceback
import io
import pyttsx3
import queue
import inspect
import shutil
from typing import List, Tuple, Optional, Dict

import edge_tts
import torch
import numpy as np
from pydub import AudioSegment
import os
_ffmpeg_dir = r"C:\ffmpeg\bin"
if os.path.isdir(_ffmpeg_dir) and _ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + _ffmpeg_dir
_ffmpeg_exe = shutil.which("ffmpeg") or os.path.join(_ffmpeg_dir, "ffmpeg.exe")
_ffprobe_exe = shutil.which("ffprobe") or os.path.join(_ffmpeg_dir, "ffprobe.exe")
_ffmpeg_available = os.path.exists(_ffmpeg_exe)
if os.path.exists(_ffmpeg_exe):
    AudioSegment.converter = _ffmpeg_exe
if os.path.exists(_ffprobe_exe):
    AudioSegment.ffprobe = _ffprobe_exe

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
_resume_lock = threading.Lock()
_resume_in_progress = False
_last_played_word_index = 0

# Debug helper
def _trace_resume_caller(tag: str):
    try:
        frm = inspect.stack()[2]
        caller = f"{frm.filename}:{frm.lineno}"
    except Exception:
        caller = "unknown"
    append_hud_console(f"[TTS-TRACE] {tag} called by {caller} @ {int(time.time()*1000)}")

# === Voice profile system ===
VOICE_PROFILES: Dict[str, Dict] = {
    "aria_female": {
        "edge": "en-US-AriaNeural",
        "silero_speaker": "en_0",
        "rate": 190,
        "volume": 1.0
    },
    "guy_male": {
        "edge": "en-US-GuyNeural",
        "silero_speaker": "en_14",
        "rate": 185,
        "volume": 1.0
    },
    "neutral": {
        "edge": "en-US-JennyNeural",
        "silero_speaker": "en_21",
        "rate": 188,
        "volume": 1.0
    }
}
_current_voice_profile = "aria_female"

EMOTION_TTS_STYLES: Dict[str, Dict] = {
    "neutral": {
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "offline_rate_delta": 0,
        "pause": (0.08, 0.22),
        "sentence_pause": (0.32, 0.62),
        "chunk_words": 40,
        "filler": ["Hmm...", "Got it...", "Let me think...", "One second..."],
    },
    "positive": {
        "rate": "+5%",
        "pitch": "+8Hz",
        "volume": "+3%",
        "offline_rate_delta": 8,
        "pause": (0.05, 0.16),
        "sentence_pause": (0.24, 0.48),
        "chunk_words": 34,
        "filler": ["Nice...", "Alright...", "I like that...", "Got it..."],
    },
    "excited": {
        "rate": "+11%",
        "pitch": "+15Hz",
        "volume": "+6%",
        "offline_rate_delta": 18,
        "pause": (0.03, 0.12),
        "sentence_pause": (0.18, 0.38),
        "chunk_words": 28,
        "filler": ["Oh, nice...", "Yes...", "Alright...", "I have it..."],
    },
    "curious": {
        "rate": "+2%",
        "pitch": "+10Hz",
        "volume": "+0%",
        "offline_rate_delta": 3,
        "pause": (0.10, 0.26),
        "sentence_pause": (0.34, 0.7),
        "chunk_words": 30,
        "filler": ["Hmm...", "Let me see...", "Interesting...", "One thought..."],
    },
    "sad": {
        "rate": "-11%",
        "pitch": "-8Hz",
        "volume": "-4%",
        "offline_rate_delta": -22,
        "pause": (0.18, 0.36),
        "sentence_pause": (0.55, 1.0),
        "chunk_words": 24,
        "filler": ["Hey...", "I hear you...", "I'm here...", "Okay..."],
    },
    "negative": {
        "rate": "-8%",
        "pitch": "-5Hz",
        "volume": "-2%",
        "offline_rate_delta": -16,
        "pause": (0.16, 0.32),
        "sentence_pause": (0.48, 0.9),
        "chunk_words": 26,
        "filler": ["I hear you...", "Okay...", "Let me be careful here...", "I'm with you..."],
    },
    "anxious": {
        "rate": "-5%",
        "pitch": "+2Hz",
        "volume": "-1%",
        "offline_rate_delta": -10,
        "pause": (0.13, 0.28),
        "sentence_pause": (0.42, 0.78),
        "chunk_words": 24,
        "filler": ["Okay...", "Breathe a second...", "I'm here...", "Let's slow it down..."],
    },
    "angry": {
        "rate": "-4%",
        "pitch": "-2Hz",
        "volume": "+1%",
        "offline_rate_delta": -8,
        "pause": (0.12, 0.26),
        "sentence_pause": (0.38, 0.72),
        "chunk_words": 24,
        "filler": ["Okay...", "I understand...", "Let's handle this cleanly...", "I'm listening..."],
    },
    "affectionate": {
        "rate": "-3%",
        "pitch": "+6Hz",
        "volume": "-1%",
        "offline_rate_delta": -6,
        "pause": (0.14, 0.3),
        "sentence_pause": (0.42, 0.82),
        "chunk_words": 26,
        "filler": ["Hey...", "Of course...", "I'm here...", "Mm..."],
    },
    "serious": {
        "rate": "-6%",
        "pitch": "-4Hz",
        "volume": "+0%",
        "offline_rate_delta": -12,
        "pause": (0.12, 0.28),
        "sentence_pause": (0.42, 0.78),
        "chunk_words": 26,
        "filler": ["Understood...", "Carefully...", "One moment...", "Let me check..."],
    },
}

_EMOTION_ALIASES = {
    "happy": "positive",
    "joy": "positive",
    "joyful": "positive",
    "calm": "neutral",
    "question": "curious",
    "negative": "negative",
    "upset": "sad",
    "sadness": "sad",
    "worried": "anxious",
    "worry": "anxious",
    "love": "affectionate",
    "caring": "affectionate",
    "error": "serious",
    "warning": "serious",
    "command": "serious",
}

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

def _resolve_edge_voice(profile_name: Optional[str]) -> str:
    if profile_name and profile_name in VOICE_PROFILES:
        return VOICE_PROFILES[profile_name]["edge"]
    return VOICE_PROFILES.get(_current_voice_profile, VOICE_PROFILES["aria_female"])["edge"]


def _normalize_emotion(emotion: Optional[str]) -> str:
    if not emotion:
        return "neutral"
    key = re.sub(r"[^a-z_]+", "", str(emotion).lower().strip())
    key = _EMOTION_ALIASES.get(key, key)
    return key if key in EMOTION_TTS_STYLES else "neutral"


def _detect_tts_emotion(text: str) -> str:
    t = (text or "").lower()
    if not t.strip():
        return "neutral"

    angry = ["angry", "furious", "irritated", "annoyed", "hate", "mad", "stop it", "shut up"]
    anxious = ["worried", "scared", "anxious", "panic", "stressed", "nervous", "afraid", "tense"]
    sad = ["sad", "lonely", "depressed", "cry", "hurt", "broken", "tired of", "not okay", "miss you"]
    affectionate = ["dear", "love", "sweet", "proud of you", "i'm here", "i am here", "with you"]
    excited = ["amazing", "awesome", "excellent", "great news", "let's go", "perfect!", "yes!", "wow"]
    serious = ["error", "failed", "warning", "careful", "danger", "risk", "blocked", "unavailable", "couldn't"]
    positive = ["happy", "good", "great", "nice", "thanks", "thank you", "done", "ready", "perfect"]

    if any(w in t for w in angry):
        return "angry"
    if any(w in t for w in anxious):
        return "anxious"
    if any(w in t for w in sad):
        return "sad"
    if any(w in t for w in affectionate):
        return "affectionate"
    if any(w in t for w in excited) or t.count("!") >= 2:
        return "excited"
    if any(w in t for w in serious):
        return "serious"
    if "?" in t:
        return "curious"
    if any(w in t for w in positive):
        return "positive"
    return "neutral"


def _resolve_tts_style(text: str, emotion: Optional[str] = None) -> Tuple[str, Dict]:
    resolved = _normalize_emotion(emotion) if emotion else _detect_tts_emotion(text)
    return resolved, EMOTION_TTS_STYLES.get(resolved, EMOTION_TTS_STYLES["neutral"])


def _clamp_pyttsx3_rate(rate: int) -> int:
    return max(120, min(235, int(rate)))


def _percent_to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value).replace("%", "")) / 100.0
    except Exception:
        return default


def _humanize_for_tts(text: str, emotion_name: str) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return clean

    clean = re.sub(r"^(okay|ok|alright|right|sure|yes|no)\s+", lambda m: m.group(1).capitalize() + ", ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(hmm|mm|uhm|um)\b[,.]*", lambda m: m.group(1).capitalize() + "...", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(?<!\.)\.\.\.(?!\.)", "...", clean)

    if emotion_name in {"sad", "negative", "anxious", "affectionate"}:
        clean = re.sub(r"([.!?])\s+(I hear you|I'm here|I understand|Let's)", r"\1 ... \2", clean)
    elif emotion_name in {"excited", "positive"}:
        clean = re.sub(r"([.!?])\s+(And|Now|Also)\b", r"\1 \2", clean)

    return clean


def _pause_after_phrase(phrase: str, style: Dict):
    pause_min, pause_max = style.get("pause", (0.05, 0.22))
    sentence_min, sentence_max = style.get("sentence_pause", (0.32, 0.62))
    time.sleep(random.uniform(pause_min, pause_max))
    if phrase.rstrip().endswith((".", "!", "?")):
        time.sleep(random.uniform(sentence_min, sentence_max))


def _can_use_online_tts() -> bool:
    if not _ffmpeg_available:
        return False
    try:
        return is_connected()
    except Exception:
        return False

VOICE_NAME = _resolve_edge_voice(None)
OFFLINE_RATE = 190
OFFLINE_VOLUME = 1.0
OFFLINE_VOICE_INDEX = 1
ONLINE_CHUNK_WORDS = 40
OFFLINE_PHRASE_WORDS = 30
PY_AUDIO_CHUNK = 2048
FILLER_MAX_WAIT = 5.0

stop_speaking = False
speaking = False
_tts_thread: Optional[threading.Thread] = None
_session_lock = threading.RLock()

_offline_queue: "queue.Queue[Tuple[int, str]]" = queue.Queue()
_offline_thread: Optional[threading.Thread] = None
_engine_ready = threading.Event()

_engine = None
_resume_text: Optional[str] = None
_resume_style: Optional[Dict] = None
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

def _configure_pyttsx3_voice(engine, profile_name: Optional[str], style: Optional[Dict] = None):
    try:
        profile = VOICE_PROFILES.get(profile_name or _current_voice_profile)
        if not profile:
            return
        voices = engine.getProperty('voices')
        idx = profile.get('pyttsx3_index', 0)
        if isinstance(idx, int) and idx < len(voices):
            engine.setProperty('voice', voices[idx].id)
        base_rate = profile.get('rate', 190)
        rate_delta = (style or {}).get("offline_rate_delta", 0)
        engine.setProperty('rate', _clamp_pyttsx3_rate(base_rate + rate_delta))

        base_volume = float(profile.get('volume', 1.0))
        volume_delta = _percent_to_float((style or {}).get("volume", "+0%"))
        engine.setProperty('volume', max(0.45, min(1.0, base_volume + volume_delta)))
    except Exception as e:
        append_hud_console(f"[TTS] pyttsx3 voice config failed: {e}")

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
            if len(item) == 4:
                token, phrase, profile_name, style = item
            else:
                token, phrase, profile_name = item
                style = EMOTION_TTS_STYLES["neutral"]
            # if playback token changed, discard this queued phrase
            if token != _playback_token:
                continue
            if stop_speaking:
                continue
            tts_playback_ping()
            try:
                # configure voice before speaking
                _configure_pyttsx3_voice(eng, profile_name, style)
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
    global _resume_text, _resume_style, _resume_word_index, _current_words, _sentence_spans
    _resume_text = None
    _resume_style = None
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
    except Exception as e:
        append_hud_console(f"[TTS] stop failed: {e}")
    try:
        if _engine is not None:
            _engine.stop()
    except Exception:
        pass
    _mark_speaking(False)
    try:
        if not ALLOW_BARGE_IN:
            resume_listening()
    except Exception:
        pass
    append_hud_console("⛔ Speech stopped")

def pause_speech():
    global stop_speaking, _paused_for_barge_in, _resume_word_index, _playback_token, _tts_thread
    _paused_for_barge_in = True
    stop_speaking = True

    # Snapshot where playback left off (for resume)
    _resume_word_index = _last_played_word_index

    # Bump playback token to force any in-flight playback loops to stop quickly.
    # This prevents the old playback from continuing while a resume starts.
    try:
        with _playback_lock:
            _playback_token += 1
            append_hud_console(f"[TTS] playback token bumped -> {_playback_token}")
    except Exception:
        _playback_token += 1
        append_hud_console(f"[TTS] playback token bumped (no lock available) -> {_playback_token}")

    # If a TTS thread exists, give it a short grace period to terminate so audio device is released.
    try:
        if _tts_thread is not None and isinstance(_tts_thread, threading.Thread):
            if _tts_thread.is_alive():
                append_hud_console("[TTS] waiting for previous TTS thread to finish (short join)")
                _tts_thread.join(timeout=0.5)
                if _tts_thread.is_alive():
                    append_hud_console("[TTS] previous TTS thread still alive after join; continuing anyway.")
                else:
                    append_hud_console("[TTS] previous TTS thread joined successfully.")
    except Exception as e:
        append_hud_console(f"[TTS] error while joining TTS thread: {e}")

    # Reflect paused state
    _mark_speaking(False)
    append_hud_console("⏸️ Speech paused (barge-in)")

def resume_if_ignored_interruption() -> bool:
    return _resume_word_if_any()

def _play_pcm_bytes(pcm_data: bytes, token: int, sample_rate: int = 16000):
    if token != _playback_token or not pcm_data:
        return
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)

    for i in range(0, len(pcm_data), PY_AUDIO_CHUNK):
        if stop_speaking or token != _playback_token:
            break
        tts_playback_ping()
        stream.write(pcm_data[i:i+PY_AUDIO_CHUNK])

    stream.stop_stream()
    stream.close()
    p.terminate()

# --- Playback helpers that check token and accept a profile_name ---------------------------------
def _play_audio_bytes(audio_bytes: bytes, token: int):
    if token != _playback_token or not audio_bytes:
        return
    import subprocess
    try:
        ffmpeg_cmd = getattr(AudioSegment, 'converter', 'ffmpeg')
        process = subprocess.Popen(
            [ffmpeg_cmd, "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        pcm_data, _ = process.communicate(audio_bytes)
        _play_pcm_bytes(pcm_data, token, 16000)
    except FileNotFoundError as e:
        append_hud_console("⚠️ FFmpeg is missing! Please install FFmpeg (and add to PATH) for Edge TTS.")
        raise RuntimeError("FFmpeg missing") from e

async def _edge_tts_fetch_audio(text: str, voice_name: str, style: Optional[Dict] = None):
    style = style or EMOTION_TTS_STYLES["neutral"]
    communicate = edge_tts.Communicate(
        text,
        voice_name,
        rate=style.get("rate", "+0%"),
        volume=style.get("volume", "+0%"),
        pitch=style.get("pitch", "+0Hz"),
    )
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes

# adaptive chunk size
def _adaptive_chunk_size(words: List[str], index: int, default: int, style: Optional[Dict] = None) -> int:
    if style and style.get("chunk_words"):
        default = min(default, int(style["chunk_words"]))
    w = words[index] if index < len(words) else ""
    if w.endswith(('.', '!', '?')):
        return max(3, default//2)
    if w.endswith(','):
        return max(4, default//2)
    if random.random() < 0.08:
        return max(3, default//2)
    return default

# Online play that checks token and adds short pauses, accepts profile_name
def _play_online_phrases(
    words: List[str],
    start_index: int = 0,
    chunk_size: int = ONLINE_CHUNK_WORDS,
    token: int = 0,
    profile_name: Optional[str] = None,
    style: Optional[Dict] = None,
) -> int:
    global stop_speaking, _last_played_word_index, _resume_word_index
    i = start_index
    voice_name = _resolve_edge_voice(profile_name)
    style = style or EMOTION_TTS_STYLES["neutral"]

    while i < len(words):
        if stop_speaking or token != _playback_token:
            _last_played_word_index = i
            return i

        # Highlight current sentence (for HUD / transcript display)
        sentence_here = _find_sentence_for_index(i)
        if sentence_here:
            try:
                set_current_spoken_sentence(sentence_here)
            except Exception:
                pass

        adaptive = _adaptive_chunk_size(words, i, chunk_size, style)
        phrase = " ".join(words[i:i+adaptive])

        try:
            audio = asyncio.run(_edge_tts_fetch_audio(phrase, voice_name, style))

            # ✅ FIXED indentation here
            if audio is None or (hasattr(audio, "duration_seconds") and audio.duration_seconds == 0):
                append_hud_console("[TTS] _edge_tts_fetch_audio returned empty audio for phrase. Aborting playback for this chunk.")
                _last_played_word_index = i
                return i

            _play_audio_bytes(audio, token)

            if token == _playback_token and not stop_speaking:
                _pause_after_phrase(phrase, style)

        except Exception as e:
            append_hud_console(f"⚠️ Online TTS error: {e}. Falling back to offline TTS.")
            _resume_word_index = i
            _speak_offline_word_aware(" ".join(words), token, profile_name, style)
            return len(words)

        i += adaptive
        _last_played_word_index = i

    return len(words)

def _speak_online_word_aware(text: str, token: int, profile_name: Optional[str] = None, style: Optional[Dict] = None) -> bool:
    global _resume_text, _resume_style, _resume_word_index
    style = style or _resume_style or EMOTION_TTS_STYLES["neutral"]
    _resume_text = text
    _resume_style = style
    words = _current_words if _current_words else _split_into_words(text)
    played_to = _play_online_phrases(words, _resume_word_index, chunk_size=ONLINE_CHUNK_WORDS, token=token, profile_name=profile_name, style=style)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    _resume_style = style
    return False

# Offline: queue (token, phrase, profile_name)
def _play_offline_phrases(
    words: List[str],
    start_index: int = 0,
    phrase_size: int = OFFLINE_PHRASE_WORDS,
    token: int = 0,
    profile_name: Optional[str] = None,
    style: Optional[Dict] = None,
) -> int:
    global stop_speaking, _last_played_word_index
    eng = _init_pyttsx3()
    if eng is None:
        return len(words)
    style = style or EMOTION_TTS_STYLES["neutral"]
    i = start_index
    while i < len(words):
        if stop_speaking or token != _playback_token:
            _last_played_word_index = i
            return i
        sentence_here = _find_sentence_for_index(i)
        if sentence_here:
            try:
                set_current_spoken_sentence(sentence_here)
            except Exception:
                pass
        size = _adaptive_chunk_size(words, i, phrase_size, style)
        phrase = " ".join(words[i:i+size])
        try:
            _configure_pyttsx3_voice(eng, profile_name, style)
            tts_playback_ping()
            eng.say(phrase + " ")
            eng.runAndWait()
        except Exception:
            traceback.print_exc()
            return i
        _pause_after_phrase(phrase, style)
        i += size
        _last_played_word_index = i
    return len(words)

def _speak_offline_word_aware(text: str, token: int, profile_name: Optional[str] = None, style: Optional[Dict] = None) -> bool:
    global _resume_text, _resume_style, _resume_word_index
    style = style or _resume_style or EMOTION_TTS_STYLES["neutral"]
    _resume_text = text
    _resume_style = style
    words = _current_words if _current_words else _split_into_words(text)
    played_to = _play_offline_phrases(words, _resume_word_index, phrase_size=OFFLINE_PHRASE_WORDS, token=token, profile_name=profile_name, style=style)
    if played_to >= len(words):
        _reset_resume_buffers()
        return True
    _resume_word_index = played_to
    _resume_text = text
    _resume_style = style
    return False

# Resume will clear paused state and attempt to play using current token and profile
def _resume_word_if_any() -> bool:
    global stop_speaking, _paused_for_barge_in, _resume_in_progress
    if not _resume_text:
        append_hud_console("▶️ Resume requested but no resume text available.")
        return False

    # Try to acquire resume lock; if not available, skip.
    if not _resume_lock.acquire(blocking=False):
        append_hud_console("▶️ Resume already locked — skipping.")
        return False

    _resume_in_progress = True
    try:
        # Double-check runtime guards while we hold the lock so no race can slip in.
        if speaking:
            append_hud_console("▶️ Resume requested but speaking already True — skipping.")
            return False
        if not _paused_for_barge_in:
            append_hud_console("▶️ Resume requested but not paused-for-barge-in — skipping.")
            return False

        # Clear paused-for-barge-in and start resume playback
        _paused_for_barge_in = False
        stop_speaking = False
        _mark_speaking(True)
        _trace_resume_caller("resume_request")
        token = _playback_token
        stored_profile = _current_voice_profile

        try:
            if _can_use_online_tts():
                result = _speak_online_word_aware(_resume_text, token, profile_name=stored_profile, style=_resume_style)
            else:
                result = _speak_offline_word_aware(_resume_text, token, profile_name=stored_profile, style=_resume_style)

            if result:
                # played to end immediately
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
        _resume_in_progress = False
        try:
            # release the lock (safe even if already unlocked in rare cases)
            if _resume_lock.locked():
                _resume_lock.release()
        except Exception:
            pass

# Prepare resume maps
def _prepare_resume_maps(text: str, style: Optional[Dict] = None):
    global _current_words, _sentence_spans, _resume_text, _resume_style
    _resume_text = text
    _resume_style = style
    _current_words = _split_into_words(text)
    _sentence_spans = _build_sentence_spans(text, _current_words)

# --- Main speak / human_speak entrypoints accept voice + emotion overrides --------------------------
def speak(text: str, voice: Optional[str] = None, emotion: Optional[str] = None):
    global stop_speaking, _tts_thread, _resume_word_index, _playback_token
    if not text or not text.strip():
        return
    with _session_lock:
        emotion_name, style = _resolve_tts_style(text, emotion)
        spoken_text = _humanize_for_tts(text, emotion_name)
        token = _next_playback_token()
        if _tts_thread and _tts_thread.is_alive():
            stop_speaking = True
            try:
                with _offline_queue.mutex:
                    _offline_queue.queue.clear()
            except Exception:
                pass
            _tts_thread.join(timeout=0.25)
        stop_speaking = False
        _resume_word_index = 0
        _prepare_resume_maps(spoken_text, style)

        _mark_speaking(True)
        set_last_spoken_text(spoken_text)

        try:
            if not ALLOW_BARGE_IN:
                pause_listening()
        except Exception:
            pass

        def run_tts(my_token=token, profile_name=voice or _current_voice_profile):
            try:
                if _can_use_online_tts():
                    append_hud_console(f"🗣️ (online/{emotion_name}) {text}")
                    _speak_online_word_aware(spoken_text, my_token, profile_name=profile_name, style=style)
                else:
                    append_hud_console(f"🗣️ (offline/{emotion_name}) {text}")
                    _speak_offline_word_aware(spoken_text, my_token, profile_name=profile_name, style=style)
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
def human_speak(answer: str, voice: Optional[str] = None, emotion: Optional[str] = None):
    emotion_name, style = _resolve_tts_style(answer, emotion)
    filler = random.choice(style.get("filler", EMOTION_TTS_STYLES["neutral"]["filler"]))
    def run_human(my_voice=voice):
        global stop_speaking
        try:
            stop_speaking = False
            speak(filler, voice=my_voice, emotion=emotion_name)
            t0 = time.time()
            while speaking and (time.time() - t0) < FILLER_MAX_WAIT:
                time.sleep(0.05)
            stop_speaking = True
            try:
                with _offline_queue.mutex:
                    _offline_queue.queue.clear()
            except Exception:
                pass
            time.sleep(0.02)
            stop_speaking = False
            final = (answer or "").strip() or "Sorry, I don't have anything useful."
            time.sleep(random.uniform(*style.get("pause", (0.06, 0.18))))
            speak(final, voice=my_voice, emotion=emotion_name)
        except Exception:
            traceback.print_exc()
    threading.Thread(target=run_human, daemon=True).start()


def emotion_speak(text: str, emotion: Optional[str] = None, voice: Optional[str] = None):
    """Convenience wrapper for callers that want the emotion-first API."""
    speak(text, voice=voice, emotion=emotion)
