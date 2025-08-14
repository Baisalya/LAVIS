# ✅ Recognizer with barge-in: keeps listening during TTS and cuts it off on user speech
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
from LAVIS.jarvis.voice.auth.voice_auth import check_long_audio_for_match, is_tts_voice

from LAVIS.jarvis.voice.controllers.watchdog import VoiceWatchdog  # ✅ modular watchdog

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

# ===== Shared state =====
command_queue = Queue()
audio_stream = None
_listening = False
_paused = False  # still supported for manual pause; not used by TTS anymore
_in_session = False
_indicator_thread = None
_listener_thread = None
_recognizer_watchdog = None
stop_listening = None

last_spoken_text = ""
last_spoken_time = 0

def set_last_spoken_text(text):
    global last_spoken_text, last_spoken_time
    last_spoken_text = (text or "").lower().strip()
    last_spoken_time = time.time()

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

def pause_listening():
    """Manual pause (not used by TTS any more)."""
    global _paused
    if not _paused:
        _paused = True
        append_hud_console("⏸️ Listening paused.")
        _update_hud_text("⏸️ Listening paused 🎙️")

def resume_listening():
    global _paused
    if _paused:
        print("🔊 Resuming listening...")
        _paused = False
        append_hud_console("▶️ Listening resumed.")
        _update_hud_text("🟢 Listening resumed 🎙️")

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

def _vosk_listen_loop():
    global audio_stream
    _last_partial = ""
    p = None

    # Import speaking + stop function for barge-in
    from LAVIS.jarvis.voice.speaker import stop_speech, speaking

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
            # === Read mic ===
            try:
                data = audio_stream.read(2000, exception_on_overflow=False)
            except Exception as e:
                print(f"🔇 Audio read error: {e}")
                continue

            # === Metering (for HUD) ===
            rms_level = calculate_rms(data)
            if controller and hasattr(controller.hud, "mic_controller"):
                try:
                    controller.hud.mic_controller.update_level(rms_level)
                except Exception:
                    pass

            now = time.time()

            # === If manually paused, still allow "stop" voice command ===
            if _paused:
                try:
                    if freeform_recognizer.AcceptWaveform(data):
                        result = json.loads(freeform_recognizer.Result())
                        query = (result.get("text") or "").strip().lower()
                        if query in ["stop", "stop it", "cancel", "mute", "enough"]:
                            append_hud_console("🛑 Voice stop detected while paused.")
                            stop_speech()
                            set_last_spoken_text("")
                except Exception:
                    pass
                time.sleep(0.05)
                continue

            # === Ignore assistant's own TTS audio (self-voice) ===
            if is_tts_voice(data):
                # assistant speaking: we ignore synthesized voice completely
                # BUT we keep recognizer alive for barge-in detection on real user voice chunks
                continue

            # === BARge-in: if assistant is speaking and we hear real voice, cut TTS ===
            if speaking:
                # Try to get a quick accept to confirm human speech started
                if freeform_recognizer.AcceptWaveform(data):
                    try:
                        result = json.loads(freeform_recognizer.Result())
                        query = (result.get("text") or "").strip().lower()
                        if query:
                            append_hud_console("⚡ Barge-in detected! Stopping TTS.")
                            stop_speech()  # immediate cut
                            set_last_spoken_text("")  # don’t treat as echo
                            if controller:
                                Clock.schedule_once(lambda dt: controller.update(query, category="fallback", typing=True))
                            command_queue.put_nowait(query)
                            set_session_mode(True)
                            last_speech_time = now
                            # reset recognizers to clean buffer
                            command_recognizer.Reset()
                            freeform_recognizer.Reset()
                            continue
                    except Exception as e:
                        append_hud_console(f"[Barge-in parse error] {e}")
                else:
                    # Not a full accept yet; try partial for HUD feedback
                    try:
                        partial = (json.loads(freeform_recognizer.PartialResult()).get("partial") or "").strip().lower()
                        if partial:
                            _update_hud_text(f"🗣️ {partial}")
                            last_speech_time = now
                    except Exception:
                        pass
                # continue pipeline below (command/freeform) for normal flow, too

            # === Command grammar path ===
            if command_recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(command_recognizer.Result())
                    query = (result.get("text") or "").strip().lower()
                    if fuzz.ratio(query, last_spoken_text) > 85:
                        continue
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

            # === Freeform path ===
            if freeform_recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(freeform_recognizer.Result())
                    query = (result.get("text") or "").strip().lower()

                    if fuzz.ratio(query, last_spoken_text) > 85:
                        continue

                    if query in ["mute", "enough", "stop it", "cancel", "stop"]:
                        append_hud_console("🛑 Voice stop detected (freeform).")
                        stop_speech()
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

            # === Partial (for live HUD) ===
            try:
                partial_result = json.loads(freeform_recognizer.PartialResult())
                partial = (partial_result.get("partial") or "").strip().lower()
                if partial:
                    if partial != _last_partial:
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

    except Exception as e:
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

# === Watchdog handlers ===
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

# === Startup/shutdown ===
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
    global stop_listening, _indicator_thread, _listener_thread, audio_stream, _recognizer_watchdog
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
        _recognizer_watchdog.stop()
