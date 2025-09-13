# recognizer.py (refactored with pluggable STT)

import os
import json
import time
import threading
import traceback
from queue import Queue

import numpy as np
import pyaudio
from kivy.clock import Clock
from fuzzywuzzy import fuzz

from jarvis_hud.components.hud_controller import HUDController
from LAVIS.utils.hud_utils import get_hud_controller
from LAVIS.jarvis.voice.auth.voice_auth import is_tts_voice
from LAVIS.jarvis.voice.controllers.watchdog import VoiceWatchdog
from LAVIS.jarvis.voice.controllers.VadSilero import VadSilero
from LAVIS.jarvis.voice.controllers.AdaptiveAEC import MicEchoCancellingTrack, PyAudioStreamTrack


try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(message): print(message)

# Import STT plugin
from LAVIS.jarvis.voice.stt.stt_vosk import VoskSTT   # <<-- Swap this out in future
from LAVIS.jarvis.voice.stt.stt_google import GoogleSTT
from LAVIS.jarvis.voice.stt.stt_fasterwhisper import FasterWhisperSTT


# ===== Settings =====
AUTHENTICATION_ENABLED = False

# === New debounce globals ===
_last_auto_resume_ms = 0
_AUTO_RESUME_DEBOUNCE_MS = 500
# Initialize once
vad = VadSilero(sample_rate=16000)
# ===== Auto-resume helpers =====
def _safe_resume_call(resume_func=None):
    global _last_auto_resume_ms
    now_ms = int(time.time() * 1000)
    if now_ms - _last_auto_resume_ms < _AUTO_RESUME_DEBOUNCE_MS:
        append_hud_console("⏯️ Skipping rapid duplicate auto-resume (debounced).")
        return False
    _last_auto_resume_ms = now_ms

    try:
        if resume_func is None:
            from LAVIS.jarvis.voice import speaker as speaker_mod
            return speaker_mod.resume_if_ignored_interruption()
        else:
            return resume_func()
    except Exception as e:
        append_hud_console(f"[Auto-resume error] {e}")
        return False

def schedule_auto_resume(delay: float = 1.5):
    def _check_and_resume():
        time.sleep(delay)
        try:
            from LAVIS.jarvis.voice import speaker as speaker_mod
            if not speaker_mod.speaking:
                resumed = _safe_resume_call(speaker_mod.resume_if_ignored_interruption)
                if resumed:
                    append_hud_console("▶️ Auto-resumed after brief silence.")
        except Exception as e:
            append_hud_console(f"[Auto-resume error] {e}")
    threading.Thread(target=_check_and_resume, daemon=True).start()

def handle_auto_resume(barge_paused, now, last_speech_time, AUTO_RESUME_SILENCE):
    from LAVIS.jarvis import speaker as speaker_mod
    if barge_paused and not speaker_mod.speaking:
        if now - last_speech_time > AUTO_RESUME_SILENCE:
            append_hud_console("⏯️ Auto-resuming previous speech after brief silence...")
            resumed = _safe_resume_call()
            if resumed:
                append_hud_console("▶️ Auto-resume successful.")
            barge_paused = False
            last_speech_time = now
    return barge_paused, last_speech_time

def schedule_resume_after_noise():
    Clock.schedule_once(lambda dt: _safe_resume_call(), 0.05)

# ===== Mic Shield for TTS =====
_listening_paused = False

def pause_listening():
    global _listening_paused
    _listening_paused = True
    print("[Recognizer] 🔇 Mic paused (TTS speaking)")

def resume_listening():
    global _listening_paused
    _listening_paused = False
    print("[Recognizer] 🎤 Mic resumed")

def is_listening_active():
    return not _listening_paused

# ===== Public queue + API =====
command_queue = Queue()

def inject_typed_query(text: str):
    if not text:
        return
    try:
        append_hud_console("⌨️ Typed barge-in received.")
        from LAVIS.jarvis.voice.speaker import stop_speech, clear_resume
        stop_speech()
        clear_resume()
        command_queue.put_nowait(text.strip())
        controller = get_hud_controller()
        if controller:
            Clock.schedule_once(lambda dt: controller.update(text.strip(), category="fallback", typing=True))
    except Exception:
        traceback.print_exc()

# ===== Shared state =====
audio_stream = None
_listening = False
_paused = False
_in_session = False
_indicator_thread = None
_listener_thread = None
_recognizer_watchdog = None
stop_listening = None

last_spoken_text = ""
last_spoken_time = 0

_last_tts_ping_ms = 0
current_spoken_sentence = ""
current_sentence_time = 0

def tts_playback_ping():
    global _last_tts_ping_ms
    _last_tts_ping_ms = int(time.time() * 1000)

def set_last_spoken_text(text):
    global last_spoken_text, last_spoken_time
    last_spoken_text = (text or "").lower().strip()
    last_spoken_time = time.time()

def set_current_spoken_sentence(text):
    global current_spoken_sentence, current_sentence_time
    current_spoken_sentence = (text or "").lower().strip()
    current_sentence_time = time.time()

def _update_hud_text(text: str):
    controller = get_hud_controller()
    if controller:
        Clock.schedule_once(lambda dt: controller.type_live_text(text), 0)

def set_session_mode(active: bool):
    global _in_session
    _in_session = active
    msg = f"🧠 Session mode: {'ON' if active else 'OFF'}"
    print(msg)
    append_hud_console(msg)
    _update_hud_text(f"{'SL:' if active else 'L:'} {'💬 Chatting' if active else '🟢 Listening'} 🎙️")

def toggle_auth(enabled: bool):
    global AUTHENTICATION_ENABLED
    AUTHENTICATION_ENABLED = enabled
    append_hud_console(f"🔁 Voice authentication {'enabled ✅' if enabled else 'disabled ❌'}")

def _listening_indicator():
    animation = ['|', '/', '-', '\\']
    idx = 0
    while _listening:
        status = "⏸️ Paused" if _paused else (
            f"SL: 💬 Chatting... {animation[idx % len(animation)]}"
            if _in_session else f"L: 🟢 Listening {animation[idx % len(animation)]}"
        )
        _update_hud_text(f"{status} 🎙️")
        idx += 1
        time.sleep(0.2)
    append_hud_console("🔴 Listening indicator thread exited.")

def calculate_rms(audio_data):
    try:
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(np.square(samples)))
        rms_int = int(rms if np.isfinite(rms) else 0)
        return max(rms_int, 10)
    except Exception as e:
        print(f"[RMS] Error: {e}")
        return 0

# ===== Interruption classification =====
_STOP_WORDS = {"stop", "cancel", "mute", "enough", "shut up", "be quiet", "quiet", "hush", "stop it"}

def classify_interruption(text: str) -> str:
    if not text:
        return "ignore"
    t = text.lower().strip()
    if t in _STOP_WORDS or any(t.startswith(w) for w in _STOP_WORDS):
        return "stop"
    if len(t) <= 2:
        return "ignore"
    if sum(c.isalpha() for c in t) < max(3, len(t)//3):
        return "ignore"
    return "valuable"

# ===== Barge-in tuning =====
BARGE_IN_RMS_THRESHOLD = 1400
BARGE_IN_RMS_SUSTAIN = 3
BARGE_IN_MIN_PARTIAL_CHARS = 2
BARGE_IN_MIN_PARTIAL_ALPHA = 2
AUTO_RESUME_SILENCE = 0.9

# ===== Main listen loop =====
def _vosk_listen_loop():
    global audio_stream
    _last_partial = ""
    p = None

    import LAVIS.jarvis.voice.speaker as speaker_mod
    stop_speech = speaker_mod.stop_speech
    pause_speech = getattr(speaker_mod, 'pause_speech', None)
    clear_resume = speaker_mod.clear_resume

    # Keep existing debounce but use timestamp from speaker module if available
    TTS_MASK_DEBOUNCE_MS = 700
    _rms_sustain_count = 0
    barge_pause_start = 0.0

    try:
        # Use a smaller buffer for lower-latency VAD (30 ms)
        FRAME_MS = 30
        SAMPLE_RATE = 16000
        FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)   # 480 samples
        FRAME_BYTES = FRAME_SAMPLES * 2                     # 16-bit -> 2 bytes/sample

        # === Replace raw PyAudio with AEC pipeline ===
        import asyncio

        mic_track = PyAudioStreamTrack(rate=SAMPLE_RATE, chunk=FRAME_SAMPLES)
        aec_track = MicEchoCancellingTrack(mic_track)

        # === Init VAD lazily (only once) ===
        try:
            vad  # if already exists at module level
        except NameError:
            from LAVIS.jarvis.voice.controllers.VadSilero import VadSilero
            vad = VadSilero(sample_rate=SAMPLE_RATE)

        # === Create recognizers once ===
        from LAVIS.jarvis.network import is_connected
        append_hud_console("📴 Offline: Using VoskSTT (single).")
        recognizer = VoskSTT(mode="freeform")
        #recognizer = FasterWhisperSTT(model_name="small", device="cpu", compute_type="int8")
        last_speech_time = time.time()
        silence_timeout = 2.0
        controller = get_hud_controller()
        barge_paused = False

        while _listening:
            try:
                data = aec_track.recv_pcm16_sync()
            except Exception as e:
                append_hud_console(f"🔇 Audio read error: {e}")
                time.sleep(0.01)
                continue

            # quick path: if listening is disabled we still want to catch STOP words
            if not is_listening_active():
                try:
                    if recognizer.accept_waveform(data):
                        query, category = recognizer.get_result()
                        if query in _STOP_WORDS:
                            append_hud_console("🛑 STOP detected while TTS paused")
                            stop_speech()
                            clear_resume()
                            set_last_spoken_text("")
                except Exception:
                    pass
                continue

            now = time.time()
            now_ms = int(now * 1000)

            rms_level = calculate_rms(data)
            if controller and hasattr(controller.hud, "mic_controller"):
                try:
                    controller.hud.mic_controller.update_level(rms_level)
                except Exception:
                    pass

            if _paused:
                try:
                    if recognizer.accept_waveform(data):
                        query, category = recognizer.get_result()
                        if query in _STOP_WORDS:
                            append_hud_console("🛑 Voice stop detected while paused.")
                            stop_speech()
                            set_last_spoken_text("")
                except Exception:
                    pass
                time.sleep(0.05)
                continue

            # --- Mask TTS ---
            try:
                tts_like = is_tts_voice(data)
            except Exception:
                tts_like = False

            last_tts_ping_ms = getattr(speaker_mod, "_last_tts_ping_ms", 0)
            try:
                tts_recent = (now_ms - int(last_tts_ping_ms)) < TTS_MASK_DEBOUNCE_MS
            except Exception:
                tts_recent = False

            is_tts_frame = (tts_like or tts_recent) and getattr(speaker_mod, "speaking", False)
            if is_tts_frame:
                continue

            # --- VAD check ---
            try:
                speech_here = vad.is_speech(data)
            except Exception:
                speech_here = (rms_level >= BARGE_IN_RMS_THRESHOLD)

            # --- Feed recognizer ---
            if speech_here:
                recognizer.accept_waveform(data)

            if recognizer.accept_waveform(data):
                try:
                    query, category = recognizer.get_result()
                    if query:
                        if fuzz.ratio(query, last_spoken_text) > 85 or fuzz.ratio(query, current_spoken_sentence) > 85:
                            continue
                        if query in _STOP_WORDS:
                            append_hud_console("🛑 Voice stop detected.")
                            stop_speech()
                            clear_resume()
                            set_last_spoken_text("")
                            continue

                        if controller:
                            Clock.schedule_once(lambda dt: controller.update(query, category=category, typing=True))
                        command_queue.put_nowait(query)
                        set_last_spoken_text(query)
                        recognizer.reset()
                        last_speech_time = now
                        continue
                except Exception as e:
                    append_hud_console(f"[Recognizer Error] {e}")

            # --- Partials ---
            try:
                partial = recognizer.get_partial()
                if partial and partial != _last_partial:
                    _last_partial = partial
                    append_hud_console(f"🔎 Partial: {partial}")
                    _update_hud_text(f"🗣️ {partial}")
                    last_speech_time = now
            except Exception:
                pass

            # --- Reset on silence ---
            if now - last_speech_time > silence_timeout:
                _last_partial = ""
                recognizer.reset()
                last_speech_time = now

    except Exception:
        append_hud_console("🚫 Mic or recognition failed:")
        traceback.print_exc()

# ===== Watchdog =====
def _recognizer_health_check():
    try:
        controller = get_hud_controller()
        if controller and hasattr(controller.hud, "mic_controller"):
            return controller.hud.mic_controller.current_level > 10
    except Exception:
        pass
    return True

def _recognizer_restart():
    stop_background_listening()
    time.sleep(0.5)
    start_background_listening()

# ===== Startup/shutdown =====
def start_background_listening():
    global _listening, _indicator_thread, _listener_thread, stop_listening, _recognizer_watchdog
    if _listening:
        append_hud_console("⚠️ Already listening.")
        return

    append_hud_console("🎤 Starting background listening...")
    _listening = True

    def safe_vosk_loop():
        while _listening:
            try:
                _vosk_listen_loop()
            except Exception as e:
                append_hud_console(f"💥 Listener crashed: {e}")
                traceback.print_exc()
                time.sleep(1)
            else:
                break

    _indicator_thread = threading.Thread(target=_listening_indicator, daemon=True)
    _indicator_thread.start()

    _listener_thread = threading.Thread(target=safe_vosk_loop, daemon=True)
    _listener_thread.start()

    stop_listening = lambda: globals().__setitem__('_listening', False)

    _recognizer_watchdog = VoiceWatchdog(
        name="Recognizer",
        target_thread_func=lambda: _listener_thread,
        health_check_func=_recognizer_health_check,
        restart_func=_recognizer_restart
    )
    _recognizer_watchdog.start()

def stop_background_listening():
    global stop_listening, _indicator_thread, _listener_thread, audio_stream, _recognizer_watchdog, _listening
    _listening = False
    if stop_listening:
        stop_listening()
        stop_listening = None
    if _indicator_thread and _indicator_thread.is_alive():
        _indicator_thread.join(timeout=1)
    if _listener_thread and _listener_thread.is_alive():
        _listener_thread.join(timeout=1)
    if audio_stream:
        try:
            audio_stream.stop_stream()
            audio_stream.close()
        except Exception:
            pass
    if _recognizer_watchdog:
        try:
            _recognizer_watchdog.stop()
        except Exception:
            pass
