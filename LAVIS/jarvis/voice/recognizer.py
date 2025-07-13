import os
import json
import time
import threading
import traceback
from queue import Queue, Full

import pyaudio
from vosk import Model, KaldiRecognizer
from kivy.clock import Clock

from jarvis_hud.components.hud_controller import HUDController
from LAVIS.utils.hud_utils import get_hud_controller
from LAVIS.jarvis.voice.auth.voice_auth import check_long_audio_for_match

# === Configuration ===
AUTHENTICATION_ENABLED = False  # Toggle speaker verification
VOSK_MODEL_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "vosk-model-en-in-0.5", "vosk-model-en-in-0.5"
))

# === Globals ===
command_queue = Queue()
audio_stream = None
_listening = False
_paused = False
_in_session = False

_indicator_thread = None
_listener_thread = None
stop_listening = None

# === Load Vosk model ===
os.environ["VOSK_LOG_LEVEL"] = "0"
model = Model(VOSK_MODEL_PATH)


# === Control Functions ===
def set_session_mode(active: bool):
    global _in_session
    _in_session = active
    prefix = "SL:" if active else "L:"
    status = "💬 Session Chatting..." if active else "🟢 Listening"
    print(f"🧠 Session mode: {'ON' if active else 'OFF'}")
    _update_hud_text(f"{prefix} {status} 🎙️")

def pause_listening():
    global _paused
    _paused = True
    print("⏸️ Listening paused.")
    _update_hud_text("⏸️ Listening paused 🎙️")

def resume_listening():
    global _paused
    _paused = False
    print("▶️ Listening resumed.")
    _update_hud_text("🟢 Listening resumed 🎙️")

def toggle_auth(enabled: bool):
    global AUTHENTICATION_ENABLED
    AUTHENTICATION_ENABLED = enabled
    print(f"🔁 Voice authentication {'enabled ✅' if enabled else 'disabled ❌'}")

def _update_hud_text(text: str):
    controller = get_hud_controller()
    if controller:
        Clock.schedule_once(lambda dt: controller.type_live_text(text), 0)


# === Listening HUD Animation Thread ===
def _listening_indicator():
    animation = ['|', '/', '-', '\\']
    idx = 0
    while _listening:
        if _paused:
            status = "⏸️ Paused"
        elif _in_session:
            status = f"SL: 💬 Session Chatting... {animation[idx % len(animation)]}"
        else:
            status = f"L: 🟢 Listening {animation[idx % len(animation)]}"

        _update_hud_text(f"{status} 🎙️")
        idx += 1
        time.sleep(0.2)
    print("🔴 Listening indicator thread exited.")


# === Vosk Listener Thread ===
def _vosk_listen_loop():
    global audio_stream
    pcm_buffer = bytearray()
    _last_partial = ""
    p = None

    try:
        p = pyaudio.PyAudio()
        audio_stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=8000
        )
        audio_stream.start_stream()
        recognizer = KaldiRecognizer(model, 16000)

        while _listening:
            if _paused:
                time.sleep(0.1)
                continue

            data = audio_stream.read(4000, exception_on_overflow=False)
            if not data:
                continue

            pcm_buffer.extend(data)
            if len(pcm_buffer) > 10 * 16000 * 2:
                pcm_buffer = pcm_buffer[-5 * 16000 * 2:]

            if recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(recognizer.Result())
                    query = result.get("text", "").strip().lower()

                    if not query:
                        print("⛔ Ignored (empty result)")
                        _last_partial = ""
                        pcm_buffer.clear()
                        recognizer.Reset()
                        continue

                    controller = get_hud_controller()

                    if not AUTHENTICATION_ENABLED:
                        print(f"⚠️ Skipped authentication: {query}")
                        if controller:
                            Clock.schedule_once(lambda dt: controller.update(query, category="command", typing=True))
                        try:
                            command_queue.put_nowait(query)
                        except Full:
                            print("⚠️ Command queue full. Ignoring...")

                    else:
                        print("🔐 Authenticating voice...")
                        _update_hud_text("🔐 Checking identity... 🎙️")

                        if check_long_audio_for_match(bytes(pcm_buffer), threshold=0.65):
                            print(f"✅ Authenticated: {query}")
                            if controller:
                                Clock.schedule_once(lambda dt: controller.update(query, category="command", typing=True))
                            command_queue.put_nowait(query)
                        else:
                            print(f"❌ Authentication failed for: {query}")
                            _update_hud_text("❌ Unauthorized voice")

                    pcm_buffer.clear()
                    _last_partial = ""
                    recognizer.Reset()

                except Exception:
                    print("⚠️ Error processing speech:")
                    traceback.print_exc()
                    pcm_buffer.clear()
                    recognizer.Reset()

            else:
                # Live partial feedback
                partial_result = json.loads(recognizer.PartialResult())
                partial = partial_result.get("partial", "").strip().lower()

                if partial and partial != _last_partial:
                    _last_partial = partial
                    print(f"🔎 Partial: {partial}")
                    _update_hud_text(f"🗣️ {partial}")

        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
            audio_stream = None

    except Exception as e:
        print("🚫 Audio device or recognition error:")
        traceback.print_exc()

    finally:
        if p:
            p.terminate()


# === Start Background Listening ===
def start_background_listening():
    global _listening, _indicator_thread, _listener_thread, stop_listening

    if _listening:
        print("⚠️ Already listening.")
        return

    print("🎤 Starting background listening...")
    _listening = True

    _indicator_thread = threading.Thread(target=_listening_indicator, daemon=True)
    _indicator_thread.start()

    _listener_thread = threading.Thread(target=_vosk_listen_loop, daemon=True)
    _listener_thread.start()

    def stop():
        global _listening
        _listening = False

    stop_listening = stop


# === Stop Background Listening ===
def stop_background_listening():
    global stop_listening, _indicator_thread, _listener_thread, audio_stream
    _listening = False

    if stop_listening:
        stop_listening()
        stop_listening = None

    if _indicator_thread and _indicator_thread.is_alive():
        _indicator_thread.join(timeout=1)
        _indicator_thread = None

    if _listener_thread and _listener_thread.is_alive():
        _listener_thread.join(timeout=1)
        _listener_thread = None

    if audio_stream:
        audio_stream.stop_stream()
        audio_stream.close()
        audio_stream = None
