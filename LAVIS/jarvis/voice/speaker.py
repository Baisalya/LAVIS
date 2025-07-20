# speaker.py (TTS Manager - Optimized)
import asyncio
import threading
import io
import edge_tts
from pydub import AudioSegment
from pydub.playback import play
import pyttsx3
from LAVIS.jarvis.network import is_connected
import random
import time

from LAVIS.jarvis.voice.recognizer import set_last_spoken_text

# === Globals ===
stop_speaking = False
voice_name = "en-US-AriaNeural"
engine = pyttsx3.init()

# Configure offline engine
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)
try:
    voices = engine.getProperty('voices')
    if len(voices) > 1:
        engine.setProperty('voice', voices[1].id)
except Exception as e:
    print(f"[TTS] Voice setup error: {e}")

def speak_offline(text):
    try:
        print("🗣️ (offline)", text)
        set_last_spoken_text(text)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"🔇 Offline TTS error: {e}")

def speak(text):
    global stop_speaking
    stop_speaking = False
    set_last_spoken_text(text)

    if not is_connected():
        speak_offline(text)
        return

    async def run_tts():
        global stop_speaking
        try:
            communicate = edge_tts.Communicate(text, voice_name)
            buffer = io.BytesIO()

            async for chunk in communicate.stream():
                if stop_speaking:
                    print("🛑 Interrupted during streaming.")
                    return
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])

            if stop_speaking:
                print("🛑 Interrupted before playback.")
                return

            print("[TTS] Speaking, recognizer paused.")
            buffer.seek(0)
            audio = AudioSegment.from_file(buffer, format="mp3")

            if not stop_speaking:
                try:
                    play(audio)
                except Exception as e:
                    print("🔊 Playback error:", e)

        except Exception as e:
            print("⚠️ edge-tts failed, falling back to offline:", e)
            speak_offline(text)

    def run_async():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_tts())
        except Exception as e:
            print(f"[TTS Thread Error] {e}")
            speak_offline(text)

    threading.Thread(target=run_async, daemon=True).start()

def stop_speech():
    global stop_speaking
    stop_speaking = True
    try:
        engine.stop()
    except Exception:
        pass
    print("⛔ Speech stopped")

def human_speak(answer):
    filler = random.choice([
        "Got it...",
        "Let me respond...",
        "One second...",
        "Alright...",
        "Okay, here's what I found..."
    ])

    def run_human_speak():
        global stop_speaking
        stop_speaking = False

        speak(filler)
        time.sleep(1.5)
        stop_speaking = False

        if not answer or len(answer.strip()) < 5:
            speak("Sorry, I don't have anything useful.")
        else:
            speak(answer.strip())

    threading.Thread(target=run_human_speak, daemon=True).start()
