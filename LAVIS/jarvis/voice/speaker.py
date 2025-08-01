# ✅ Fully patched speaker.py with offline logging and crash resilience
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
from LAVIS.jarvis.voice.controllers.tts_guard import guard_microphone

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

stop_speaking = False
voice_name = "en-US-AriaNeural"
engine = pyttsx3.init()

engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)
try:
    voices = engine.getProperty('voices')
    if len(voices) > 1:
        engine.setProperty('voice', voices[1].id)
except Exception as e:
    print(f"[TTS] Voice setup error: {e}")

@guard_microphone
def speak_offline(text):
    try:
        print("🗣️ (offline)", text)
        append_hud_console(f"🗣️ (offline) {text}")
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        import traceback
        print("🔇 Offline TTS error:", e)
        traceback.print_exc()
        try:
            engine.stop()
        except Exception:
            pass
    finally:
        resume_listening()  # ✅ Ensure resume even if offline TTS fails

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

def play_with_guard(audio_segment):
    pause_listening()
    try:
        play_interruptible(audio_segment)
        time.sleep(0.2)
    finally:
        resume_listening()

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
                    print("🚩 Interrupted during streaming.")
                    return
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])

            if buffer.tell() == 0:
                print("❌ TTS audio buffer is empty.")
                speak_offline(text)
                return

            try:
                buffer.seek(0)
                audio = AudioSegment.from_file(buffer, format="mp3")
            except Exception as decode_error:
                print("❌ Error decoding MP3 from TTS buffer:", decode_error)
                speak_offline(text)
                return

            if not stop_speaking:
                try:
                    play_with_guard(audio)
                except Exception as playback_error:
                    print("🔊 Playback error:", playback_error)
                    speak_offline(text)

        except Exception as tts_error:
            print("⚠️ edge-tts failed, using offline fallback:", tts_error)
            speak_offline(text)

    def run_async():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_tts())
        except Exception as e:
            import traceback
            print(f"[TTS Thread Error] {e}")
            traceback.print_exc()
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
    except Exception as e:
        print("⚠️ engine.stop() failed:", e)
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
            try:
                speak(filler)
                time.sleep(1.5)
            except Exception as filler_error:
                print("⚠️ Filler speak failed:", filler_error)
                speak_offline(filler)

            stop_speaking = False
            final = answer.strip() if answer else "Sorry, I don't have anything useful."
            try:
                speak(final)
            except Exception as final_error:
                print("❌ Final response failed:", final_error)
                speak_offline(final)

        except Exception as e:
            import traceback
            print("❌ human_speak crashed:")
            traceback.print_exc()
            speak_offline("Sorry, something went wrong.")

    try:
        threading.Thread(target=run_human_speak, daemon=True).start()
    except Exception as e:
        print("[human_speak Thread Error]", e)
        speak_offline(answer or "Sorry, something went wrong.")
