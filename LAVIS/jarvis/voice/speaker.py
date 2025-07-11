# speaker.py (TTS Manager)
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

# === Globals ===
stop_speaking = False
voice_name = "en-US-AriaNeural"
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)
engine.setProperty('voice', engine.getProperty('voices')[1].id)


def speak_offline(text):
    print("🗣️ (offline)", text)
    engine.say(text)
    engine.runAndWait()


def speak(text):
    global stop_speaking
    stop_speaking = False

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

            print("🗣️", text)
            buffer.seek(0)
            audio = AudioSegment.from_file(buffer, format="mp3")

            # ✅ Play entire audio at once for smoothness
            if not stop_speaking:
                play(audio)

        except Exception as e:
            print("⚠️ edge-tts failed, using fallback:", e)
            speak_offline(text)

    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_tts())

    threading.Thread(target=run_async).start()

def stop_speech():
    global stop_speaking
    stop_speaking = True
    engine.stop()
    print("⛔ Speech stopped")

def human_speak(answer):
    filler = random.choice([
        "Let me check that...",
        "Give me a second...",
        "Thinking...",
        "Here's what I found:",
        "Got it..."
    ])

    def run_human_speak():
        global stop_speaking
        stop_speaking = False

        speak(filler)
        time.sleep(1.5)

        # ✅ Reset stop_speaking before actual answer
        stop_speaking = False

        if not answer or len(answer.strip()) < 5:
            speak("Sorry, I don't have anything useful.")
        else:
            speak(answer.strip())

    threading.Thread(target=run_human_speak).start()
