#recognizr.py
import traceback
import threading
import time
import json
from queue import Queue, Full

import pyaudio
from vosk import Model, KaldiRecognizer
import os
os.environ["VOSK_LOG_LEVEL"] = "0"

from kivy.clock import Clock
from jarvis_hud.main import hud_interface
from jarvis_hud.components.hud_controller import HUDController
from LAVIS.utils.hud_utils import get_hud_controller
from LAVIS.jarvis.voice.auth.voice_auth import is_authenticated_from_bytes
# === Global variables ===
recognizer = None
stop_listening = None
command_queue = Queue()
audio_stream = None

_listening = False
_paused = False
_in_session = False
_indicator_thread = None
_listener_thread = None

# === Load Vosk model ===
model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vosk-model-en-in-0.5", "vosk-model-en-in-0.5"))
model = Model(model_path)

# === Session mode control ===
def set_session_mode(active: bool):
    global _in_session
    _in_session = active
    print("🧠 Session mode:", "ON" if active else "OFF")
    status = "💬 Session Chatting..." if active else "🟢 Listening"
    controller = get_hud_controller()
    if controller:
        Clock.schedule_once(lambda dt: controller.type_live_text(f"{status} 🎙️"))

# === Pause/resume listening ===
def pause_listening():
    global _paused
    _paused = True
    print("⏸️ Listening paused.")
    controller = get_hud_controller()
    if controller:
        Clock.schedule_once(lambda dt: controller.type_live_text("⏸️ Listening paused 🎙️"))

def resume_listening():
    global _paused
    _paused = False
    print("▶️ Listening resumed.")
    controller = get_hud_controller()
    if controller:
        Clock.schedule_once(lambda dt: controller.type_live_text("🟢 Listening resumed 🎙️"))

# === Listening indicator ===
def _listening_indicator():
    animation = ['|', '/', '-', '\\']
    idx = 0
    while _listening:
        if _paused:
            status = "⏸️ Paused"
        elif _in_session:
            status = "💬 Session Chatting..."
        else:
            status = f"🟢 Listening {animation[idx % len(animation)]}"

        controller = get_hud_controller()
        if controller:
            Clock.schedule_once(lambda dt, text=status: controller.type_live_text(f"{text} 🎙️"), 0)

        idx += 1
        time.sleep(0.2)
    print("\r🔴 Stopped background listening.")

# === Voice input loop (no authentication) ===
def _vosk_listen_loop():
    global audio_stream
    import json
    import io
    import threading
    import traceback
    import pyaudio
    from LAVIS.utils.hud_utils import get_hud_controller

    p = None
    _last_partial = ""
    pcm_buffer = bytearray()  # 🔐 Authentication buffer

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
        rec = KaldiRecognizer(model, 16000)

        while _listening:
            if _paused:
                time.sleep(0.1)
                continue

            data = audio_stream.read(4000, exception_on_overflow=False)
            if not data:
                continue

            pcm_buffer.extend(data)  # 🔐 Add to buffer

            if rec.AcceptWaveform(data):
                try:
                    result = json.loads(rec.Result())
                    query = result.get("text", "").strip().lower()

                    if not query:
                        print("\n⛔ Ignored (empty result)")
                        _last_partial = ""
                        pcm_buffer.clear()
                        rec.Reset()
                        continue

                    # 🔐 Authenticate speaker voice
                    print(f"🔐 Authenticating voice...")
                    if is_authenticated_from_bytes(bytes(pcm_buffer)):
                        print(f"\n✅ Authenticated: {query}")
                        controller = get_hud_controller()
                        if controller:
                            Clock.schedule_once(lambda dt: controller.update(query, category="command", typing=True))

                        try:
                            command_queue.put(query, block=False)
                        except Full:
                            print("⚠️ Command queue full. Ignoring...")
                    else:
                        
                        print(f"\n❌ Authentication failed. Ignored: {query}")
                        controller = get_hud_controller()
                        if controller:
                            Clock.schedule_once(lambda dt: controller.type_live_text("❌ Unauthorized voice"), 0)

                    pcm_buffer.clear()
                    _last_partial = ""
                    rec.Reset()

                except Exception:
                    print("\n⚠️ Error processing speech")
                    traceback.print_exc()
                    pcm_buffer.clear()

            else:
                # === Partial feedback ===
                partial_result = json.loads(rec.PartialResult())
                partial = partial_result.get("partial", "").strip().lower()
                if partial and partial != _last_partial:
                    _last_partial = partial
                    print(f"\r🔎 Partial: {partial}", end='', flush=True)
                    controller = get_hud_controller()
                    if controller:
                        Clock.schedule_once(lambda dt: controller.type_live_text(f"🗣️ {partial}"), 0)

        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
            audio_stream = None

    except Exception:
        print("\n🚫 Mic or audio stream error:")
        traceback.print_exc()

    finally:
        if p is not None:
            p.terminate()

# === Start background listening ===
def start_background_listening():
    global _listening, _indicator_thread, _listener_thread, stop_listening
    print("🎤 Calibrating mic...")
    _listening = True

    _indicator_thread = threading.Thread(target=_listening_indicator)
    _indicator_thread.start()

    _listener_thread = threading.Thread(target=_vosk_listen_loop)
    _listener_thread.daemon = True
    _listener_thread.start()

    def stop():
        global _listening
        _listening = False

    stop_listening = stop

# === Stop listening ===
def stop_background_listening():
    global stop_listening, _indicator_thread, _listener_thread, audio_stream
    _listening = False
    if stop_listening:
        stop_listening()
        stop_listening = None

    if _indicator_thread:
        _indicator_thread.join()
        _indicator_thread = None

    if _listener_thread:
        _listener_thread.join()
        _listener_thread = None

    if audio_stream:
        audio_stream.stop_stream()
        audio_stream.close()
        audio_stream = None
