import traceback
import threading
import time
import json
from queue import Queue, Full

import pyaudio
from vosk import Model, KaldiRecognizer
import os
import os
os.environ["VOSK_LOG_LEVEL"] = "0"

from kivy.clock import Clock
from jarvis_hud.main import hud_interface
from jarvis_hud.components.hud_controller import HUDController
from LAVIS.utils.hud_utils import get_hud_controller

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

# === Voice input loop ===
def _vosk_listen_loop():
    global audio_stream
    import wave
    from LAVIS.jarvis.voice.auth.voice_auth import is_authenticated

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
        rec = KaldiRecognizer(model, 16000)

        full_audio = bytearray()  # For authentication chunk

        while _listening:
            if _paused:
                time.sleep(0.1)
                continue

            data = audio_stream.read(4000, exception_on_overflow=False)
            if not data:
                continue

            full_audio.extend(data)  # Accumulate audio

            if rec.AcceptWaveform(data):
                try:
                    result = json.loads(rec.Result())
                    query = result.get("text", "").strip().lower()

                    # Skip if empty speech
                    if not query:
                        print("\n⛔ Ignored (empty result)")
                        rec.Reset()
                        full_audio.clear()
                        continue

                    # Save full audio for authentication
                    with wave.open("temp_input.wav", "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(full_audio)

                    full_audio.clear()  # Reset for next utterance

                    # Run authentication in thread
                    def process_query(query_text):
                        if not is_authenticated("temp_input.wav"):
                            print("⛔ Unauthorized voice. Ignored.")
                            controller = get_hud_controller()
                            if controller:
                                Clock.schedule_once(lambda dt: controller.type_live_text("⛔ Unauthorized voice 🎙️"), 0)
                            return

                        print(f"\n🎧 You said: {query_text}")
                        controller = get_hud_controller()
                        if controller:
                            Clock.schedule_once(lambda dt: controller.update(query_text, category="command", typing=True))

                        try:
                            command_queue.put(query_text, block=False)
                        except Full:
                            print("⚠️ Command queue full. Ignoring...")

                    threading.Thread(target=process_query, args=(query,)).start()

                    rec.Reset()

                except Exception:
                    print("\n⚠️ Error processing speech")
                    traceback.print_exc()

            else:
                # Show partial results for UI feedback
                partial_result = json.loads(rec.PartialResult())
                partial = partial_result.get("partial", "").strip().lower()
                if partial:
                    print(f"\r🔎 Partial: {partial}", end='', flush=True)
                    controller = get_hud_controller()
                    if controller:
                        Clock.schedule_once(lambda dt: controller.type_live_text(f"🗣️ {partial}"), 0)

        # Cleanup
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
