# ✅ recognizer.py — Continuous listening with smart barge-in + resume decisions + real-time sentence tracking

import os
import json
import time
import threading
import traceback
from queue import Queue

import numpy as np
import pyaudio
from vosk import Model, KaldiRecognizer
from kivy.clock import Clock
from fuzzywuzzy import fuzz

from jarvis_hud.components.hud_controller import HUDController
from LAVIS.utils.hud_utils import get_hud_controller
from LAVIS.jarvis.voice.auth.voice_auth import is_tts_voice
from LAVIS.jarvis.voice.controllers.watchdog import VoiceWatchdog

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(message): print(message)

# ===== Settings =====
AUTHENTICATION_ENABLED = False

COMMAND_MODEL_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "vosk-model-en-in-0.5", "vosk-model-small-en-us-0.15"
))
FREEFORM_MODEL_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "vosk-model-en-in-0.5", "vosk-model-en-us-daanzu-20200905"
))
COMMANDS_JSON_PATH = os.path.join(os.path.dirname(__file__), "commands.json")

# ===== Mic Shield for TTS =====
_listening_paused = False

def pause_listening():
    """Temporarily mute mic while TTS is speaking."""
    global _listening_paused
    _listening_paused = True
    print("[Recognizer] 🔇 Mic paused (TTS speaking)")

def resume_listening():
    """Unmute mic after TTS is done or interrupted."""
    global _listening_paused
    _listening_paused = False
    print("[Recognizer] 🎤 Mic resumed")

def is_listening_active():
    """Check if recognizer should process mic input."""
    return not _listening_paused

# ===== Public queue + API =====
command_queue = Queue()

def inject_typed_query(text: str):
    """Typing interrupt API: call from UI/main to inject a query that should interrupt speech exactly like a spoken barge-in."""
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
_paused = False        # kept for compatibility with HUD text; not used to gate mic (we use is_listening_active)
_in_session = False
_indicator_thread = None
_listener_thread = None
_recognizer_watchdog = None
stop_listening = None

last_spoken_text = ""
last_spoken_time = 0

# ===== TTS echo-mitigation (ping from speaker.py) =====
_last_tts_ping_ms = 0

def tts_playback_ping():
    """Called by speaker.py right before pushing audio to speakers."""
    global _last_tts_ping_ms
    _last_tts_ping_ms = int(time.time() * 1000)

# ===== Sentence-level awareness =====
current_spoken_sentence = ""
current_sentence_time = 0

def set_last_spoken_text(text):
    global last_spoken_text, last_spoken_time
    last_spoken_text = (text or "").lower().strip()
    last_spoken_time = time.time()

def set_current_spoken_sentence(text):
    """
    Called by speaker.py before each sentence starts speaking.
    Allows recognizer to suppress echo & resume from exact point.
    """
    global current_spoken_sentence, current_sentence_time
    current_spoken_sentence = (text or "").lower().strip()
    current_sentence_time = time.time()

os.environ["VOSK_LOG_LEVEL"] = "0"
command_model = Model(COMMAND_MODEL_PATH)
freeform_model = Model(FREEFORM_MODEL_PATH)

def load_command_grammar():
    try:
        with open(COMMANDS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        append_hud_console(f"❌ Failed to load grammar: {e}")
        return []

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
# ===== Main =====
def _vosk_listen_loop():
    global audio_stream
    _last_partial = ""
    p = None

    from LAVIS.jarvis.voice.speaker import stop_speech, speaking, resume_if_ignored_interruption, clear_resume

    last_tts_frame_time = 0.0
    TTS_MASK_DEBOUNCE_MS = 150

    try:
        p = pyaudio.PyAudio()
        audio_stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=2000
        )
        audio_stream.start_stream()

        command_phrases = load_command_grammar()
        grammar_json = json.dumps(command_phrases)

        command_recognizer = KaldiRecognizer(command_model, 16000, grammar_json)
        command_recognizer.SetWords(True)

        freeform_recognizer = KaldiRecognizer(freeform_model, 16000)
        freeform_recognizer.SetWords(True)

        last_speech_time = time.time()
        silence_timeout = 2.0
        controller = get_hud_controller()

        while _listening:
            try:
                data = audio_stream.read(2000, exception_on_overflow=False)
            except Exception as e:
                print(f"🔇 Audio read error: {e}")
                continue

            # 🔒 If muted by TTS, skip processing
            if not is_listening_active():
                try:
                    if freeform_recognizer.AcceptWaveform(data):
                        result = json.loads(freeform_recognizer.Result())
                        query = (result.get("text") or "").strip().lower()
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
                    if freeform_recognizer.AcceptWaveform(data):
                        result = json.loads(freeform_recognizer.Result())
                        query = (result.get("text") or "").strip().lower()
                        if query in _STOP_WORDS:
                            append_hud_console("🛑 Voice stop detected while paused.")
                            stop_speech()
                            set_last_spoken_text("")
                except Exception:
                    pass
                time.sleep(0.05)
                continue

            # === TTS-likeness gate (FIXED: still allow barge-in while speaking) ===
            tts_like = is_tts_voice(data)
            if tts_like and not speaking:
                continue

            # === While assistant is speaking: barge-in handling (FIXED) ===
            if speaking:
                if freeform_recognizer.AcceptWaveform(data):
                    try:
                        result = json.loads(freeform_recognizer.Result())
                        query = (result.get("text") or "").strip().lower()

                        if query:
                            # Suppress echo
                            if fuzz.ratio(query, last_spoken_text) > 85 or fuzz.ratio(query, current_spoken_sentence) > 85:
                                continue

                            print(f"[BARGE-IN LISTENING] Heard while speaking → {query}")

                            category = classify_interruption(query)

                            if category == "stop":
                                append_hud_console("🛑 Barge-in: STOP detected. Cutting TTS (no resume).")
                                append_hud_console(f"(was speaking sentence: '{current_spoken_sentence}')")
                                stop_speech()
                                clear_resume()
                                set_last_spoken_text("")
                                continue

                            if category == "valuable":
                                append_hud_console(f"⚡ Barge-in: valuable input → '{query}'")
                                append_hud_console(f"(was speaking sentence: '{current_spoken_sentence}')")
                                stop_speech()

                                if controller:
                                    Clock.schedule_once(lambda dt: controller.update(query, category="fallback", typing=True))

                                command_queue.put_nowait(query)
                                set_session_mode(True)

                                def _resume_after_query(dt):
                                    from LAVIS.jarvis.voice.speaker import resume_if_ignored_interruption
                                    resumed = resume_if_ignored_interruption()
                                    if resumed:
                                        append_hud_console("▶️ Resumed previous speech after handling query.")

                                Clock.schedule_once(_resume_after_query, 0.5)

                                last_speech_time = now
                                command_recognizer.Reset()
                                freeform_recognizer.Reset()
                                continue

                            append_hud_console("🔄 Interruption ignored (noise). Resuming speech.")
                            resume_if_ignored_interruption()
                            continue

                    except Exception as e:
                        append_hud_console(f"[Barge-in parse error] {e}")
                else:
                    try:
                        partial = (json.loads(freeform_recognizer.PartialResult()).get("partial") or "").strip().lower()
                        if partial:
                            print(f"[BARGE-IN PARTIAL] {partial}")
                            _update_hud_text(f"🗣️ {partial}")
                            last_speech_time = now
                    except Exception:
                        pass

            # === Command grammar lane ===
            if command_recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(command_recognizer.Result())
                    query = (result.get("text") or "").strip().lower()
                    if fuzz.ratio(query, last_spoken_text) > 85 or fuzz.ratio(query, current_spoken_sentence) > 85:
                        continue
                    if query:
                        if query in command_phrases:
                            if controller:
                                Clock.schedule_once(lambda dt: controller.update(query, category="command", typing=True))
                            command_queue.put_nowait(query)
                            set_last_spoken_text(query)
                            command_recognizer.Reset()
                            freeform_recognizer.Reset()
                            last_speech_time = now
                            continue
                except Exception as e:
                    append_hud_console(f"[Command Error] {e}")

            # === Freeform lane ===
            if freeform_recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(freeform_recognizer.Result())
                    query = (result.get("text") or "").strip().lower()
                    if fuzz.ratio(query, last_spoken_text) > 85 or fuzz.ratio(query, current_spoken_sentence) > 85:
                        continue

                    if query in _STOP_WORDS:
                        append_hud_console("🛑 Voice stop detected (freeform).")
                        stop_speech()
                        clear_resume()
                        set_last_spoken_text("")
                        continue

                    if query:
                        set_session_mode(True)
                        if controller:
                            Clock.schedule_once(lambda dt: controller.update(query, category="fallback", typing=True))
                        command_queue.put_nowait(query)
                        set_last_spoken_text(query)
                        Clock.schedule_once(lambda dt: set_session_mode(False), 10)
                        if controller:
                            Clock.schedule_once(lambda dt: controller.clear_live_text(), 0)
                        command_recognizer.Reset()
                        freeform_recognizer.Reset()
                        last_speech_time = now
                        continue
                except Exception as e:
                    append_hud_console(f"[Freeform Error] {e}")

            # === Partial updates ===
            try:
                partial_result = json.loads(freeform_recognizer.PartialResult())
                partial = (partial_result.get("partial") or "").strip().lower()
                if partial and partial != _last_partial:
                    _last_partial = partial
                    append_hud_console(f"🔎 Partial: {partial}")
                    _update_hud_text(f"🗣️ {partial}")
                    last_speech_time = now
            except Exception:
                pass

            # === Silence reset ===
            if now - last_speech_time > silence_timeout:
                _last_partial = ""
                command_recognizer.Reset()
                freeform_recognizer.Reset()
                last_speech_time = now

    except Exception:
        append_hud_console("🚫 Mic or recognition failed:")
        traceback.print_exc()
    finally:
        if audio_stream:
            try:
                audio_stream.stop_stream()
                audio_stream.close()
            except Exception:
                pass
        if p:
            try:
                p.terminate()
            except Exception:
                pass

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
