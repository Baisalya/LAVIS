# ✅ speaker.py — Hybrid Edge TTS (online) + pyttsx3 (offline)
# Full-featured: word-aware barge-in, smart resume, sentence pings for echo suppression,
# echo-mitigation pings to recognizer, mic pause/resume shield, HUD logs, and no-overlap guard.

import asyncio
import threading
import re
import time
import random
import traceback
import io
from typing import List, Tuple, Optional

import edge_tts
import pyttsx3
from pydub import AudioSegment
import pyaudio

# ---- Integration points into the rest of the stack ---------------------------------------------

# Network signal to decide online/offline TTS path
from LAVIS.jarvis.network import is_connected

# Recognizer helpers: last text (for echo filtering) + resume + (optional) mic pause
# We try to import pause_listening (if present in your recognizer patch) but fall back if not available.
try:
    from LAVIS.jarvis.voice.recognizer import (
        set_last_spoken_text,
        resume_listening,
        pause_listening,
        tts_playback_ping,        # recognizer ping for echo masking
        set_current_spoken_sentence,
    )
except Exception:
    # graceful fallbacks if some helpers are not present yet
    def set_last_spoken_text(_t): pass
    def resume_listening(): pass
    def pause_listening(): pass
    def tts_playback_ping(): pass
    def set_current_spoken_sentence(_t): pass

# HUD console (safe fallback to print)
try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

# =================================================================================================
#                                       CONFIG / TUNABLES
# =================================================================================================

# MS Edge voice name (valid examples: en-US-AriaNeural, en-US-GuyNeural, hi-IN-NeerjaNeural, etc.)
VOICE_NAME = "en-US-AriaNeural"

# Offline engine settings (pyttsx3)
OFFLINE_RATE = 190           # slightly faster to reduce perceived latency
OFFLINE_VOLUME = 1.0
OFFLINE_VOICE_INDEX = 1      # try a non-default voice if available

# Online chunking (Edge TTS): send short phrases to keep latency low and allow barge-in regularly
ONLINE_CHUNK_WORDS = 12

# Offline chunking (pyttsx3): say short phrases for better prosody and barge-in
OFFLINE_PHRASE_WORDS = 5

# pydub/pyaudio streaming
PY_AUDIO_CHUNK = 2048

# How long to wait for a filler to end before we start the final message (sec)
FILLER_MAX_WAIT = 5.0

# =================================================================================================
#                                GLOBAL RUNTIME STATE / LOCKS
# =================================================================================================

_engine: Optional[pyttsx3.Engine] = None

# Speaking state
stop_speaking = False
speaking = False
_tts_thread: Optional[threading.Thread] = None
_session_lock = threading.RLock()

# Resume state
_resume_text: Optional[str] = None
_resume_word_index: int = 0
_current_words: List[str] = []

# For mapping current word index -> sentence, we keep sentence spans
# Each span is (sentence_text, start_word_idx, end_word_idx_exclusive)
_sentence_spans: List[Tuple[str, int, int]] = []

# =================================================================================================
#                                      ENGINE INITIALIZATION
# =================================================================================================

def _init_pyttsx3():
    """Initialize the offline pyttsx3 engine (once)."""
    global _engine
    if _engine is not None:
        return _engine
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', OFFLINE_RATE)
        engine.setProperty('volume', OFFLINE_VOLUME)
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

# =================================================================================================
#                                         SMALL HELPERS
# =================================================================================================

def _mark_speaking(active: bool):
    """Flip public speaking flag (read by recognizer too)."""
    global speaking
    speaking = active

def _reset_resume_buffers():
    """Clear resume buffers."""
    global _resume_text, _resume_word_index, _current_words, _sentence_spans
    _resume_text = None
    _resume_word_index = 0
    _current_words = []
    _sentence_spans = []

def clear_resume():
    """Public API to clear resume state."""
    _reset_resume_buffers()

def _split_into_words(text: str) -> List[str]:
    return re.findall(r"\S+", text or "")

_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

def _split_into_sentences(text: str) -> List[str]:
    """Simple sentence split. Keeps punctuation as part of each sentence."""
    t = (text or "").strip()
    if not t:
        return []
    parts = _SENTENCE_RE.split(t)
    # Remove empty parts & normalize spaces
    return [re.sub(r'\s+', ' ', p).strip() for p in parts if p.strip()]

def _build_sentence_spans(text: str, words: List[str]) -> List[Tuple[str, int, int]]:
    """
    Map sentences to word-index spans so we can tell recognizer exactly which sentence we start.
    We do a best-effort mapping by greedy consumption of words per sentence.
    """
    sentences = _split_into_sentences(text)
    spans: List[Tuple[str, int, int]] = []
    wi = 0
    for sent in sentences:
        sent_words = _split_into_words(sent)
        start = wi
        wi += len(sent_words)
        end = wi
        spans.append((sent, start, end))
    # If text didn't end with punctuation, we may still have trailing words; ensure coverage
    if wi < len(words):
        # Bundle remaining words into a pseudo sentence
        tail_text = " ".join(words[wi:])
        spans.append((tail_text, wi, len(words)))
    return spans

def _find_sentence_for_index(word_index: int) -> str:
    """Return the sentence text that contains the given word index."""
    for sent, start, end in _sentence_spans:
        if start <= word_index < end:
            return sent
    # If not found, return last sentence or empty
    return _sentence_spans[-1][0] if _sentence_spans else ""

# =================================================================================================
#                                   PUBLIC INTERRUPT/CONTROL API
# =================================================================================================

def stop_speech():
    """Hard stop for barge-in; cancels playback and clears speaking flag."""
    global stop_speaking
    stop_speaking = True

    # Try to stop pyttsx3 immediately if it's in a run loop
    try:
        eng = _init_pyttsx3()
        if eng is not None:
            eng.stop()
    except Exception as e:
        append_hud_console(f"[TTS] engine.stop() failed: {e}")

    _mark_speaking(False)
    append_hud_console("⛔ Speech stopped")

def resume_if_ignored_interruption() -> bool:
    """If an interruption was ignored (noise), resume from last stored word index."""
    return _resume_word_if_any()

# =================================================================================================
#                                         AUDIO OUTPUT
# =================================================================================================

def _play_audio_segment(audio_segment: AudioSegment):
    """Low-latency write of an AudioSegment to the default output device."""
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
            # ping recognizer to help it mask echo
            tts_playback_ping()
            stream.write(raw[i:i+PY_AUDIO_CHUNK])
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        p.terminate()

# =================================================================================================
#                                         ONLINE (EDGE TTS)
# =================================================================================================

async def _edge_tts_fetch_audio(text: str) -> AudioSegment:
    """Fetch MP3 audio for the given text using Microsoft Edge TTS."""
    buf = io.BytesIO()
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return AudioSegment.from_file(buf, format="mp3")

def _play_online_phrases(words: List[str], start_index: int = 0, chunk_size: int = ONLINE_CHUNK_WORDS) -> int:
    """
    Fetch and play Edge TTS audio in short phrases (chunk_size words).
    Returns the next word index to speak (or len(words) if finished).
    """
    global stop_speaking
    i = start_index
    while i < len(words):
        if stop_speaking:
            append_hud_console(f"⏸️ Interrupted at word {i}: {words[i] if i < len(words) else ''}")
            return i

        # If we’re crossing into a new sentence, inform the recognizer
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
    """
    Online path (Edge TTS). Returns True if all words were spoken, False if interrupted.
    Uses _resume_word_index to resume mid-utterance after a barge-in.
    """
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

# =================================================================================================
#                                       OFFLINE (pyttsx3)
# =================================================================================================

def _play_offline_phrases(words: List[str], start_index: int = 0, phrase_size: int = OFFLINE_PHRASE_WORDS) -> int:
    """
    Speak with pyttsx3 in short phrases for better prosody and frequent barge-in checkpoints.
    Returns the next word index to speak (or len(words) if finished).
    """
    global stop_speaking
    eng = _init_pyttsx3()
    if eng is None:
        # if pyttsx3 init failed, bail; nothing to do here
        return start_index

    i = start_index
    while i < len(words):
        if stop_speaking:
            append_hud_console(f"⏸️ Interrupted at word {i}: {words[i] if i < len(words) else ''}")
            return i

        # If we’re crossing into a new sentence, inform the recognizer
        sentence_here = _find_sentence_for_index(i)
        if sentence_here:
            try:
                set_current_spoken_sentence(sentence_here)
            except Exception:
                pass

        phrase = " ".join(words[i:i+phrase_size])
        try:
            # ping the recognizer before and during output
            tts_playback_ping()
            eng.say(phrase + " ")
            eng.runAndWait()
        except Exception:
            traceback.print_exc()
            return i
        i += phrase_size
    return len(words)

def _speak_offline_word_aware(text: str) -> bool:
    """
    Offline path (pyttsx3). Returns True if all words were spoken, False if interrupted.
    """
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

# =================================================================================================
#                                             RESUME
# =================================================================================================

def _resume_word_if_any() -> bool:
    """
    Resume after an ignored interruption (noise), picking up from _resume_word_index.
    Returns True if speech completed, False if we still have remainder.
    """
    if not _resume_text:
        return False
    if is_connected():
        return _speak_online_word_aware(_resume_text)
    else:
        return _speak_offline_word_aware(_resume_text)

# =================================================================================================
#                                          TOP-LEVEL SPEAK
# =================================================================================================

def _prepare_resume_maps(text: str):
    """Compute _current_words + sentence spans for accurate sentence pings & word resume."""
    global _current_words, _sentence_spans, _resume_text
    _resume_text = text
    _current_words = _split_into_words(text)
    _sentence_spans = _build_sentence_spans(text, _current_words)

def speak(text: str):
    """
    Main TTS entry — runs in a single speaking session.
    - Cancels any previous TTS to prevent overlap
    - Pauses recognizer mic (if available) for clean echo behavior
    - Streams online or offline with barge-in check points
    - Resumes mic when done
    """
    global stop_speaking, _tts_thread, _resume_word_index

    if not text or not text.strip():
        return

    with _session_lock:
        # Kill any ongoing TTS to avoid double-voice
        if _tts_thread and _tts_thread.is_alive():
            stop_speaking = True
            try:
                eng = _init_pyttsx3()
                if eng is not None:
                    eng.stop()
            except Exception:
                pass
            _tts_thread.join(timeout=0.25)

        # Prepare state for this utterance
        stop_speaking = False
        _resume_word_index = 0
        _prepare_resume_maps(text)
        _mark_speaking(True)
        set_last_spoken_text(text)

        # Pause mic input (if recognizer supports it)
        try:
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
                _mark_speaking(False)
                # Allow recognizer to resume mic listening
                try:
                    resume_listening()
                except Exception:
                    pass

        _tts_thread = threading.Thread(target=run_tts, daemon=True)
        _tts_thread.start()

# =================================================================================================
#                                      HUMAN-SPEAK WRAPPER
# =================================================================================================

def human_speak(answer: str):
    """
    Speak a short filler, then the final answer without overlap/double-voice.
    This helps the user feel a "natural" hand-off (Alexa/Assistant style).
    """
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
            # 1) Filler
            stop_speaking = False
            speak(filler)

            # 2) Wait for filler to finish or timeout
            t0 = time.time()
            while speaking and (time.time() - t0) < FILLER_MAX_WAIT:
                time.sleep(0.05)

            # 3) Ensure no overlap
            stop_speaking = True
            try:
                eng = _init_pyttsx3()
                if eng is not None:
                    eng.stop()
            except Exception:
                pass
            time.sleep(0.02)
            stop_speaking = False

            # 4) Final message
            final = (answer or "").strip() or "Sorry, I don't have anything useful."
            speak(final)
        except Exception:
            traceback.print_exc()

    threading.Thread(target=run_human, daemon=True).start()

