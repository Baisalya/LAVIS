# speaker.py (patched)
import asyncio
import threading
import io
import edge_tts
from pydub import AudioSegment
import pyttsx3
import pyaudio
import random
import time

from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.voice.recognizer import set_last_spoken_text, pause_listening, resume_listening

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
        pause_listening()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"🔇 Offline TTS error: {e}")
    finally:
        # ✅ Ensure mic resumes after speaking, no matter what
        resume_listening()

def play_interruptible(audio_segment):
    global stop_speaking
    p = pyaudio.PyAudio()
    stream = p.open(
        format=p.get_format_from_width(audio_segment.sample_width),
        channels=audio_segment.channels,
        rate=audio_segment.frame_rate,
        output=True,
    )

    chunk_size = 1024
    data = audio_segment.raw_data
    for i in range(0, len(data), chunk_size):
        if stop_speaking:
            break
        stream.write(data[i:i+chunk_size])

    stream.stop_stream()
    stream.close()
    p.terminate()

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

            buffer.seek(0)
            audio = AudioSegment.from_file(buffer, format="mp3")

            if not stop_speaking:
                try:
                    pause_listening()
                    play_interruptible(audio)
                    time.sleep(0.2)
                    resume_listening()
                except Exception as e:
                    print("🔊 Playback error:", e)
                    speak_offline(text)

        except Exception as e:
            print("⚠️ edge-tts failed, using offline fallback:", e)
            speak_offline(text)

    def run_async():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_tts())
        except Exception as e:
            print(f"[TTS Thread Error] {e}")
            speak_offline(text)

    try:
        threading.Thread(target=run_async, daemon=True).start()
    except Exception as e:
        print("[TTS Startup Error]", e)
        speak_offline(text)

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
        try:
            stop_speaking = False
            speak(filler)
            time.sleep(1.5)
            stop_speaking = False

            if not answer or len(answer.strip()) < 5:
                speak("Sorry, I don't have anything useful.")
            else:
                speak(answer.strip())
        except Exception as e:
            print("❌ human_speak failed:", e)
            speak_offline("Sorry, something went wrong.")

    try:
        threading.Thread(target=run_human_speak, daemon=True).start()
    except Exception as e:
        print("[human_speak Thread Error]", e)
        speak_offline(answer)
