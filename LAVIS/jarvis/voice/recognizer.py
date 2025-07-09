import traceback
import threading
import time
from queue import Queue
import json
import pyaudio
from vosk import Model, KaldiRecognizer

# === Global variables ===
recognizer = None
microphone = None
stop_listening = None
command_queue = Queue()

_listening = False
_paused = False
_in_session = False  # 🔐 Session lock
_indicator_thread = None
audio_stream = None

# === Load Vosk model ===
import os
model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vosk-model-en-in-0.5", "vosk-model-en-in-0.5"))
model = Model(model_path)
vosk_recognizer = KaldiRecognizer(model, 16000)

# === Session mode control ===
def set_session_mode(active: bool):
    global _in_session
    _in_session = active
    print("🧠 Session mode:", "ON" if active else "OFF")

# === Pause/resume listening ===
def pause_listening():
    global _paused
    _paused = True
    print("⏸️ Listening paused.")

def resume_listening():
    global _paused
    _paused = False
    print("▶️ Listening resumed.")

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

        print(f"\r{status} 🎙️", end='', flush=True)
        idx += 1
        time.sleep(0.2)
    print("\r🔴 Stopped background listening.       ")

# === Voice input loop ===
def _vosk_listen_loop():
    global audio_stream
    try:
        p = pyaudio.PyAudio()
        audio_stream = p.open(format=pyaudio.paInt16,
                              channels=1,
                              rate=16000,
                              input=True,
                              frames_per_buffer=8000)
        audio_stream.start_stream()

        # Create recognizer per session
        rec = KaldiRecognizer(model, 16000)

        while _listening:
            if _paused:
                time.sleep(0.1)
                continue

            data = audio_stream.read(4000, exception_on_overflow=False)

            if rec.AcceptWaveform(data):
                try:
                    result = json.loads(rec.Result())
                    query = result.get("text", "").strip().lower()

                    if query:
                        print(f"\n🎧 You said: {query}")

                        if query in ["read it", "read the answer", "tell me", "repeat"]:
                            print("🎯 Trigger phrase detected for reading fallback.")

                        command_queue.put(query)
                    else:
                        print("\n⛔ Ignored (empty result)")

                    # 🔄 Reinitialize recognizer for the next utterance
                    rec = KaldiRecognizer(model, 16000)

                except Exception:
                    print("\n⚠️ Error processing speech")
                    traceback.print_exc()

            else:
                partial_result = json.loads(rec.PartialResult())
                partial = partial_result.get("partial", "").strip().lower()
                if partial:
                    print(f"\r🔎 Partial: {partial}", end='', flush=True)

    except Exception:
        print("\n🚫 Mic or audio stream error:")
        traceback.print_exc()

# === Start background listening ===
def start_background_listening():
    global _listening, _indicator_thread, stop_listening
    print("🎤 Calibrating mic...")
    _listening = True

    _indicator_thread = threading.Thread(target=_listening_indicator)
    _indicator_thread.start()

    listener_thread = threading.Thread(target=_vosk_listen_loop)
    listener_thread.daemon = True
    listener_thread.start()

    def stop():
        global _listening
        _listening = False
    stop_listening = stop

# === Stop listening ===
def stop_background_listening():
    global stop_listening, _listening, _indicator_thread, audio_stream
    _listening = False
    if stop_listening:
        stop_listening()
        stop_listening = None
    if _indicator_thread:
        _indicator_thread.join()
    if audio_stream:
        audio_stream.stop_stream()
        audio_stream.close()
        audio_stream = None
