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

# === Try importing HUD logging ===
try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(message): pass

# === Configuration ===
AUTHENTICATION_ENABLED = False
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

# === Internal HUD Update ===
def _update_hud_text(text: str):
    controller = get_hud_controller()
    if controller:
        Clock.schedule_once(lambda dt: controller.type_live_text(text), 0)

# === State Control ===
def set_session_mode(active: bool):
    global _in_session
    _in_session = active
    prefix = "SL:" if active else "L:"
    status = "💬 Session Chatting..." if active else "🟢 Listening"
    msg = f"🧠 Session mode: {'ON' if active else 'OFF'}"
    print(msg)
    append_hud_console(msg)
    _update_hud_text(f"{prefix} {status} 🎙️")

def pause_listening():
    global _paused
    _paused = True
    msg = "⏸️ Listening paused."
    print(msg)
    append_hud_console(msg)
    _update_hud_text("⏸️ Listening paused 🎙️")

def resume_listening():
    global _paused
    _paused = False
    msg = "▶️ Listening resumed."
    print(msg)
    append_hud_console(msg)
    _update_hud_text("🟢 Listening resumed 🎙️")

def toggle_auth(enabled: bool):
    global AUTHENTICATION_ENABLED
    AUTHENTICATION_ENABLED = enabled
    msg = f"🔁 Voice authentication {'enabled ✅' if enabled else 'disabled ❌'}"
    print(msg)
    append_hud_console(msg)

# === Listening HUD Animation ===
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

    msg = "🔴 Listening indicator thread exited."
    print(msg)
    append_hud_console(msg)

# === Vosk Listening Thread ===
def _vosk_listen_loop():
    global audio_stream
    _last_partial = ""
    p = None

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
        recognizer = KaldiRecognizer(model, 16000, '["open browser", "shutdown", "hello jarvis"]')
        recognizer.SetWords(True)

        last_speech_time = time.time()
        silence_timeout = 2.0

        while _listening:
            if _paused:
                time.sleep(0.1)
                continue

            data = audio_stream.read(2000, exception_on_overflow=False)
            if not data:
                continue

            now = time.time()

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                query = result.get("text", "").strip().lower()

                if not query:
                    msg = "⛔ Ignored (empty result)"
                    print(msg)
                    append_hud_console(msg)
                    _last_partial = ""
                    recognizer.Reset()
                    continue

                controller = get_hud_controller()

                if not AUTHENTICATION_ENABLED:
                    msg = f"⚠️ Skipped authentication: {query}"
                    print(msg)
                    append_hud_console(msg)
                    if controller:
                        Clock.schedule_once(lambda dt: controller.update(query, category="command", typing=True))
                    try:
                        command_queue.put_nowait(query)
                    except Full:
                        msg = "⚠️ Command queue full. Ignoring..."
                        print(msg)
                        append_hud_console(msg)
                else:
                    msg = "🔐 Authenticating voice..."
                    print(msg)
                    append_hud_console(msg)
                    _update_hud_text("🔐 Checking identity... 🎙️")
                    if check_long_audio_for_match(data, threshold=0.65):
                        msg = f"✅ Authenticated: {query}"
                        print(msg)
                        append_hud_console(msg)
                        if controller:
                            Clock.schedule_once(lambda dt: controller.update(query, category="command", typing=True))
                        command_queue.put_nowait(query)
                    else:
                        msg = f"❌ Authentication failed for: {query}"
                        print(msg)
                        append_hud_console(msg)
                        _update_hud_text("❌ Unauthorized voice")

                _last_partial = ""
                recognizer.Reset()
                last_speech_time = now

            else:
                partial_result = json.loads(recognizer.PartialResult())
                partial = partial_result.get("partial", "").strip().lower()

                if partial and partial != _last_partial:
                    _last_partial = partial
                    msg = f"🔎 Partial: {partial}"
                    print(msg)
                    append_hud_console(msg)
                    _update_hud_text(f"🗣️ {partial}")
                    last_speech_time = now

                if now - last_speech_time > silence_timeout:
                    _last_partial = ""
                    recognizer.Reset()
                    last_speech_time = now

        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
            audio_stream = None

    except Exception:
        msg = "🚫 Audio device or recognition error:"
        print(msg)
        append_hud_console(msg)
        traceback.print_exc()
    finally:
        if p:
            p.terminate()

# === Background Listening Control ===
def start_background_listening():
    global _listening, _indicator_thread, _listener_thread, stop_listening

    if _listening:
        msg = "⚠️ Already listening."
        print(msg)
        append_hud_console(msg)
        return

    msg = "🎤 Starting background listening..."
    print(msg)
    append_hud_console(msg)

    _listening = True

    _indicator_thread = threading.Thread(target=_listening_indicator, daemon=True)
    _indicator_thread.start()

    _listener_thread = threading.Thread(target=_vosk_listen_loop, daemon=True)
    _listener_thread.start()

    def stop():
        global _listening
        _listening = False

    stop_listening = stop

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
